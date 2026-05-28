import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { existsSync, rmSync, statSync } from "node:fs";
import { join } from "node:path";
import { ExecutionContext } from "../src/context.js";

describe("ExecutionContext", () => {
  const testDir = "/tmp/sdk-test-context";

  afterEach(() => {
    if (existsSync(testDir)) {
      rmSync(testDir, { recursive: true, force: true });
    }
  });

  it("creates output directory on construction", () => {
    const ctx = new ExecutionContext({ outputDir: join(testDir, "run-1/node-1") });
    expect(existsSync(ctx.outputDir)).toBe(true);
  });

  it("uses CANVASTEKK_OUTPUT_DIR env var", () => {
    process.env.CANVASTEKK_OUTPUT_DIR = testDir;
    const ctx = new ExecutionContext({ runId: "run-1", nodeId: "node-1" });
    expect(ctx.outputDir).toBe(join(testDir, "run-1", "node-1"));
    delete process.env.CANVASTEKK_OUTPUT_DIR;
  });

  it("defaults to /tmp when no env var", () => {
    delete process.env.CANVASTEKK_OUTPUT_DIR;
    const ctx = new ExecutionContext({ runId: "r", nodeId: "n" });
    expect(ctx.outputDir).toContain("/tmp/");
    expect(ctx.outputDir).toContain("r");
    expect(ctx.outputDir).toContain("n");
  });

  it("extracts runId from request", () => {
    const ctx = new ExecutionContext({
      request: { run_id: "run-abc", node_id: "node-1", inputs: {} },
    });
    expect(ctx.runId).toBe("run-abc");
  });

  it("extracts nodeId from request", () => {
    const ctx = new ExecutionContext({
      request: { run_id: "run-abc", node_id: "node-1", inputs: {} },
    });
    expect(ctx.nodeId).toBe("node-1");
  });

  it("returns outputPath with filename", () => {
    const ctx = new ExecutionContext({ outputDir: join(testDir, "run-1/node-1") });
    expect(ctx.outputPath("result.json")).toBe(join(testDir, "run-1/node-1/result.json"));
  });

  it("lazily creates downloadsDir", () => {
    const ctx = new ExecutionContext({ outputDir: join(testDir, "run-2/node-2") });
    expect(existsSync(join(testDir, "run-2/node-2/downloads"))).toBe(false);
    const dlDir = ctx.downloadsDir;
    expect(existsSync(dlDir)).toBe(true);
    expect(dlDir).toContain("downloads");
  });

  it("tracks metadata", () => {
    const ctx = new ExecutionContext({ outputDir: join(testDir, "run-3/node-3") });
    ctx.metadata["key"] = "value";
    expect(ctx.metadata["key"]).toBe("value");
  });

  it("records token usage", () => {
    const ctx = new ExecutionContext({ outputDir: join(testDir, "run-4/node-4") });
    ctx.recordTokenUsage({ promptTokens: 10, completionTokens: 5, totalTokens: 15 });
    expect(ctx.tokenUsage).toEqual({
      prompt_tokens: 10,
      completion_tokens: 5,
      total_tokens: 15,
    });
  });

  it("token_usage returns a copy", () => {
    const ctx = new ExecutionContext({ outputDir: join(testDir, "run-5/node-5") });
    ctx.recordTokenUsage({ totalTokens: 100 });
    const usage = ctx.tokenUsage;
    usage.total_tokens = 999;
    expect(ctx.tokenUsage.total_tokens).toBe(100);
  });

  it("reportProgress does not throw", () => {
    const ctx = new ExecutionContext({ outputDir: join(testDir, "run-6/node-6") });
    expect(() => ctx.reportProgress(0.5, "halfway")).not.toThrow();
  });
});
