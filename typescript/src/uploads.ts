import { createReadStream, statSync } from "node:fs";
import { request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import type { NodeExecutionResponse } from "./response.js";

/**
 * Interface for uploading node output files.
 */
export interface OutputUploader {
  uploadFile(filePath: string, presignedUrl: string): Promise<void>;
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
   * @param filePath - Local file path
   * @param presignedUrl - S3 presigned upload URL
   * @throws Error if upload fails
   */
  async uploadFile(filePath: string, presignedUrl: string): Promise<void> {
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
            reject(new Error(`Upload failed: HTTP ${code} ${res.statusMessage ?? ""} ${detail}`.trim()));
          });
        },
      );

      const timer = setTimeout(
        () => req.destroy(new Error(`Upload timed out after ${UPLOAD_TIMEOUT_MS} ms`)),
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
   * @param response - Node execution response
   * @param uploadUrls - Mapping of field names to presigned URLs
   * @param fileOutputFields - Names of file output fields
   */
  async uploadOutputs(
    response: NodeExecutionResponse,
    uploadUrls: Record<string, string>,
    fileOutputFields: string[],
  ): Promise<void> {
    if (!response.outputs) return;

    for (const fieldName of fileOutputFields) {
      if (!(fieldName in uploadUrls)) continue;

      const value = response.outputs[fieldName];
      if (typeof value !== "string") continue;

      try {
        statSync(value);
      } catch {
        console.warn(`Output field '${fieldName}' value is not a local file: ${value}`);
        continue;
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
