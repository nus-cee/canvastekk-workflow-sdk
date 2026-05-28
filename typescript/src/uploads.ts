import { readFileSync, statSync } from "node:fs";
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

/**
 * Uploads output files to S3 using presigned URLs.
 */
export class S3PresignedUploader implements OutputUploader {
  /**
   * Uploads a single file to S3 via presigned URL.
   * @param filePath - Local file path
   * @param presignedUrl - S3 presigned upload URL
   * @throws Error if upload fails
   */
  async uploadFile(filePath: string, presignedUrl: string): Promise<void> {
    const data = readFileSync(filePath);
    const resp = await fetch(presignedUrl, {
      method: "PUT",
      body: data,
      headers: { "Content-Type": "application/octet-stream" },
    });
    if (!resp.ok) {
      throw new Error(`Upload failed: HTTP ${resp.status} ${resp.statusText}`);
    }
  }

  /**
   * Uploads all file outputs from a node response.
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

      const presignedUrl = uploadUrls[fieldName];
      try {
        await this.uploadFile(value, presignedUrl);
        const size = statSync(value).size;
        console.info(`Uploaded output '${fieldName}' to S3 (${size} bytes)`);
      } catch (err) {
        console.error(`Failed to upload output '${fieldName}' to S3: ${err}`);
      }
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
