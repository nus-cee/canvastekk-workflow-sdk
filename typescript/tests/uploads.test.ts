import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { S3PresignedUploader } from "../src/uploads.js";

describe("S3PresignedUploader", () => {
  let tmpDir: string;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    tmpDir = mkdtempSync(join(tmpdir(), "sdk-uploads-"));
    // Drain the stream body so createReadStream opens before afterEach cleanup
    fetchMock = vi.fn().mockImplementation(async (_url: string, init?: RequestInit) => {
      if (init?.body) await new Response(init.body).arrayBuffer();
      return new Response(null, { status: 200, statusText: "OK" });
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    rmSync(tmpDir, { recursive: true, force: true });
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  describe("uploadFile", () => {
    it("sends the file as a PUT stream with duplex half (undici requirement)", async () => {
      const filePath = join(tmpDir, "out.frag");
      writeFileSync(filePath, Buffer.from("frag-bytes"));

      await new S3PresignedUploader().uploadFile(filePath, "https://s3/presigned");

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toBe("https://s3/presigned");
      expect(init.method).toBe("PUT");
      expect(init.headers).toEqual({ "Content-Type": "application/octet-stream" });
      // Node streams require duplex: "half" or undici throws
      // "RequestInit: duplex option is required when sending a body"
      expect(init.duplex).toBe("half");
      expect(init.body).toBeTruthy();
    });

    it("throws on non-2xx response", async () => {
      const filePath = join(tmpDir, "out.frag");
      writeFileSync(filePath, Buffer.from("frag-bytes"));
      fetchMock.mockImplementation(async (_u: string, init?: RequestInit) => {
        if (init?.body) await new Response(init.body).arrayBuffer();
        return new Response(null, { status: 403, statusText: "Forbidden" });
      });

      await expect(
        new S3PresignedUploader().uploadFile(filePath, "https://s3/presigned"),
      ).rejects.toThrow("Upload failed: HTTP 403 Forbidden");
    });
  });

  describe("uploadOutputs", () => {
    it("uploads local file outputs and skips non-file values", async () => {
      const fragPath = join(tmpDir, "converted.frag");
      writeFileSync(fragPath, Buffer.from("frag-bytes"));

      const response = {
        success: true,
        outputs: { frag_file: fragPath, note: "not-a-file" },
      } as Parameters<S3PresignedUploader["uploadOutputs"]>[0];

      await new S3PresignedUploader().uploadOutputs(
        response,
        { frag_file: "https://s3/frag", note: "https://s3/note" },
        ["frag_file", "note"],
      );

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toBe("https://s3/frag");
      expect(init.duplex).toBe("half");
    });
  });
});
