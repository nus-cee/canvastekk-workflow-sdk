import { createReadStream, statSync } from "node:fs";
import { request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import type { NodeExecutionResponse } from "./response.js";

/**
 * Interface for uploading node output files.
 */
export interface OutputUploader {
  uploadFile(filePath: string, presignedUrl: string): Promise<void>;
  /**
   * Implementations MUST throw (not skip) when a file-output field that is
   * present in `response.outputs` and has a presigned URL holds a value
   * that is not an existing local file — silently skipping would report
   * success while the engine stamps a storage URI for the missing object,
   * corrupting downstream consumers (DA-2337).
   */
  uploadOutputs(
    response: NodeExecutionResponse,
    uploadUrls: Record<string, string>,
    fileOutputFields: string[],
  ): Promise<void>;
}

// Explicit generous timeout for output uploads — without it, a large
// multi-GB upload has no deadline at all; with it, slow links still get
// 600 s. Total deadline (matches the Py SDK).
const UPLOAD_TIMEOUT_MS = 600_000;

// Retry policy (DA-1955): transient failures only, exponential backoff.
const MAX_ATTEMPTS = 3;
const INITIAL_BACKOFF_MS = 500;

/**
 * HTTP-status upload failure carrying the status code so callers (and the
 * retry loop) can classify 4xx vs 5xx without regexing the message.
 */
export class UploadHttpError extends Error {
  readonly statusCode: number;

  constructor(statusCode: number, message: string) {
    super(message);
    this.name = "UploadHttpError";
    this.statusCode = statusCode;
  }
}

/** Node errno codes that are transient network failures worth retrying. */
const TRANSIENT_ERRNO_CODES = new Set([
  "ECONNRESET",
  "ETIMEDOUT",
  "ECONNREFUSED",
  "EPIPE",
  "EAI_AGAIN",
  "ENOTFOUND",
  "EHOSTUNREACH",
  "ENETUNREACH",
]);

function isTransientError(err: unknown): boolean {
  if (err instanceof UploadHttpError) {
    return err.statusCode >= 500;
  }
  // Only transient network errnos are retryable. Deterministic local errors
  // (ENOENT/EACCES from statSync/read stream) fail fast, matching python.
  const code = (err as NodeJS.ErrnoException)?.code;
  return typeof code === "string" && TRANSIENT_ERRNO_CODES.has(code);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Uploads output files to S3 using presigned URLs.
 */
export class S3PresignedUploader implements OutputUploader {
  /**
   * Uploads a single file to S3 via presigned URL.
   *
   * Streams the file from disk (never buffers the whole body in memory —
   * outputs in this domain are multi-GB point clouds).
   *
   * Uses Node's http/https core module instead of fetch: fetch cannot send
   * a fixed-length stream body (it forces `Transfer-Encoding: chunked`,
   * which S3 rejects with `501 Not Implemented`, and strips a
   * user-supplied `Content-Length`). http.request with an explicit
   * Content-Length pipes the stream with identity encoding.
   *
   * Retries transient failures (network/socket errors and HTTP 5xx) up to
   * 3 attempts with exponential backoff (0.5s, 1s). Deterministic client
   * errors (4xx) are never retried (DA-1955).
   *
   * @param filePath - Local file path
   * @param presignedUrl - S3 presigned upload URL
   * @throws UploadHttpError on HTTP status failure after retries
   * @throws Error on transport failure after retries
   */
  async uploadFile(filePath: string, presignedUrl: string): Promise<void> {
    let lastError: unknown;
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      try {
        await this.attemptUpload(filePath, presignedUrl);
        return;
      } catch (err) {
        lastError = err;
        if (!isTransientError(err) || attempt === MAX_ATTEMPTS) throw err;
        const backoffMs = INITIAL_BACKOFF_MS * 2 ** (attempt - 1);
        console.warn(
          `Upload attempt ${attempt}/${MAX_ATTEMPTS} failed (${err instanceof Error ? err.message : String(err)}); retrying in ${backoffMs} ms`,
        );
        await sleep(backoffMs);
      }
    }
    throw lastError;
  }

  private async attemptUpload(filePath: string, presignedUrl: string): Promise<void> {
    const { size } = statSync(filePath);
    const target = new URL(presignedUrl);
    const send = target.protocol === "http:" ? httpRequest : httpsRequest;

    await new Promise<void>((resolve, reject) => {
      const req = send(
        target,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/octet-stream",
            "Content-Length": String(size),
          },
        },
        (res) => {
          const code = res.statusCode ?? 0;
          if (code >= 200 && code < 300) {
            res.resume(); // drain so the socket is released
            clearTimeout(timer);
            resolve();
            return;
          }
          const chunks: Buffer[] = [];
          res.on("data", (c) => chunks.push(c as Buffer));
          res.on("end", () => {
            clearTimeout(timer);
            const detail = Buffer.concat(chunks).toString("utf8").slice(0, 200).trim();
            reject(new UploadHttpError(code, `Upload failed: HTTP ${code} ${res.statusMessage ?? ""} ${detail}`.trim()));
          });
        },
      );

      const timer = setTimeout(
        () =>
          req.destroy(
            // Tag the timeout with ETIMEDOUT so isTransientError retries it
            // (parity with python, where httpx timeouts are TransportErrors).
            Object.assign(new Error(`Upload timed out after ${UPLOAD_TIMEOUT_MS} ms`), {
              code: "ETIMEDOUT",
            }),
          ),
        UPLOAD_TIMEOUT_MS,
      );

      req.on("error", (err) => {
        clearTimeout(timer);
        reject(err);
      });

      const stream = createReadStream(filePath);
      stream.on("error", (err) => req.destroy(err));
      stream.pipe(req);
    });
  }

  /**
   * Uploads all file outputs from a node response.
   *
   * Upload failures PROPAGATE so the caller can fail the execution —
   * silently reporting success with local-only paths would strand
   * downstream consumers (DA-1711 4.1).
   *
   * A declared file-output field that HAS a presigned URL but whose value
   * is not a string referencing an existing regular file THROWS — the
   * engine stamps an `s3://` URI for every present output field on pass,
   * so skipping the upload would report success while corrupting every
   * downstream consumer (DA-2337). Fields ABSENT from the response are
   * skipped (omission is legal — the engine never stamps them).
   *
   * @param response - Node execution response
   * @param uploadUrls - Mapping of field names to presigned URLs
   * @param fileOutputFields - Names of file output fields
   * @throws Error when a present file-output field is not a local file
   */
  async uploadOutputs(
    response: NodeExecutionResponse,
    uploadUrls: Record<string, string>,
    fileOutputFields: string[],
  ): Promise<void> {
    if (!response.outputs) return;

    for (const fieldName of fileOutputFields) {
      if (!(fieldName in uploadUrls)) continue;

      if (!(fieldName in response.outputs)) {
        // Omitted output: the engine stamps s3:// URIs only for fields
        // present in the response, so omission is legal.
        continue;
      }

      const value = response.outputs[fieldName];
      if (typeof value !== "string") {
        throw new Error(`Output field '${fieldName}' value is not a string: ${typeof value}`);
      }

      let isRegularFile = false;
      try {
        isRegularFile = statSync(value).isFile();
      } catch {
        isRegularFile = false;
      }

      if (!isRegularFile) {
        console.error(`Output field '${fieldName}' value is not a local file: ${value}`);
        throw new Error(`Output field '${fieldName}' value is not a local file: ${value}`);
      }

      await this.uploadFile(value, uploadUrls[fieldName]);
      const size = statSync(value).size;
      console.info(`Uploaded output '${fieldName}' to S3 (${size} bytes)`);
    }
  }
}

let _defaultUploader: S3PresignedUploader | null = null;

/**
 * Gets the default S3 uploader instance (singleton).
 * @returns Default S3 presigned uploader
 */
export function getDefaultUploader(): S3PresignedUploader {
  if (!_defaultUploader) {
    _defaultUploader = new S3PresignedUploader();
  }
  return _defaultUploader;
}
