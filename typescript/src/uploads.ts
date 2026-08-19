import { createReadStream, statSync } from "node:fs";
import type { Readable } from "node:stream";
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
// 600 s. AbortSignal.timeout is a TOTAL deadline (matches the Py SDK).
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
   * @param filePath - Local file path
   * @param presignedUrl - S3 presigned upload URL
   * @throws Error if upload fails
   */
  async uploadFile(filePath: string, presignedUrl: string): Promise<void> {
    const body = createReadStream(filePath) as Readable;
    const resp = await fetch(presignedUrl, {
      method: "PUT",
      // @ts-expect-error Node fetch accepts Node streams as bodies
      body,
      duplex: "half",
      headers: { "Content-Type": "application/octet-stream" },
      signal: AbortSignal.timeout(UPLOAD_TIMEOUT_MS),
    });
    if (!resp.ok) {
      throw new Error(`Upload failed: HTTP ${resp.status} ${resp.statusText}`);
    }
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
