import { describe, it, expect } from "vitest";
import {
  NodeExecutionRequestSchema,
} from "../src/request.js";

describe("NodeExecutionRequestSchema", () => {
  it("parses a full request", () => {
    const req = NodeExecutionRequestSchema.parse({
      run_id: "run-abc",
      node_id: "echo-1",
      inputs: { message: "hi" },
      callback_url: "https://example.com/callback",
      output_upload_url: { file: "https://s3.example.com/presigned" },
    });
    expect(req.run_id).toBe("run-abc");
    expect(req.node_id).toBe("echo-1");
    expect(req.inputs).toEqual({ message: "hi" });
    expect(req.callback_url).toBe("https://example.com/callback");
    expect(req.output_upload_url).toEqual({ file: "https://s3.example.com/presigned" });
  });

  it("defaults inputs to empty object", () => {
    const req = NodeExecutionRequestSchema.parse({
      run_id: "run-1",
      node_id: "node-1",
    });
    expect(req.inputs).toEqual({});
  });

  it("defaults callback_url and output_upload_url", () => {
    const req = NodeExecutionRequestSchema.parse({
      run_id: "run-1",
      node_id: "node-1",
    });
    expect(req.callback_url).toBeUndefined();
    expect(req.output_upload_url).toBeNull();
  });

  it("accepts null output_upload_url", () => {
    const req = NodeExecutionRequestSchema.parse({
      run_id: "run-1",
      node_id: "node-1",
      output_upload_url: null,
    });
    expect(req.output_upload_url).toBeNull();
  });
});
