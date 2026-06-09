import { describe, it, expect } from "vitest";
import {
  buildRegistryPayload,
  extractNodeData,
  registerNodeResultGet,
  registerNodeResultHas,
} from "../src/registry.js";
import type { WorkflowNodeManifest } from "../src/definition.js";

const testDef: WorkflowNodeManifest = {
  name: "echo",
  version: "1.0.0",
  title: "Echo Node",
  description: "Returns input",
  input_schema: { type: "object" },
  output_schema: { type: "object" },
  token_cost: 0,
  default_retry: { max_attempts: 1, initial_delay_ms: 1000, backoff_multiplier: 2.0, max_delay_ms: 30000 },
  category: "utility",
  timeout_seconds: 30,
  role: "operation",
  styles: null,
};

describe("buildRegistryPayload", () => {
  it("maps title to label", () => {
    const payload = buildRegistryPayload(testDef);
    expect(payload.label).toBe("Echo Node");
    expect(payload.name).toBe("echo");
  });

  it("omits id from payload", () => {
    const payload = buildRegistryPayload(testDef);
    expect(payload).not.toHaveProperty("id");
  });

  it("maps default_retry to retry", () => {
    const payload = buildRegistryPayload(testDef);
    expect(payload.retry).toEqual({
      max_attempts: 1,
      initial_delay_ms: 1000,
      backoff_multiplier: 2.0,
      max_delay_ms: 30000,
    });
  });

  it("includes invoke_url when provided", () => {
    const payload = buildRegistryPayload(testDef, { invokeUrl: "https://example.com" });
    expect(payload.invoke_url).toBe("https://example.com");
  });

  it("omits invoke_url when not provided", () => {
    const payload = buildRegistryPayload(testDef);
    expect(payload).not.toHaveProperty("invoke_url");
  });

  it("defaults invoke_type to http", () => {
    const payload = buildRegistryPayload(testDef);
    expect(payload.invoke_type).toBe("http");
  });

  it("includes node_role in payload", () => {
    const payload = buildRegistryPayload(testDef);
    expect(payload.node_role).toBe("operation");
  });
});

describe("extractNodeData", () => {
  it("extracts from node key", () => {
    const data = extractNodeData({ node: { name: "test" }, action: "created" });
    expect(data).toEqual({ name: "test" });
  });

  it("extracts from data key", () => {
    const data = extractNodeData({ data: { name: "test" } });
    expect(data).toEqual({ name: "test" });
  });

  it("returns payload as-is when no node/data key", () => {
    const payload = { name: "test", version: "1.0" };
    const data = extractNodeData(payload);
    expect(data).toEqual(payload);
  });

  it("prefers node over data", () => {
    const data = extractNodeData({ node: { name: "from-node" }, data: { name: "from-data" } });
    expect(data.name).toBe("from-node");
  });
});

describe("RegisterNodeResult dict-like access", () => {
  const result = {
    node: { name: "echo", version: "1.0.0" },
    action: "created" as const,
  };

  it("get returns value", () => {
    expect(registerNodeResultGet(result, "name")).toBe("echo");
  });

  it("get returns default for missing key", () => {
    expect(registerNodeResultGet(result, "missing", "default")).toBe("default");
  });

  it("has returns true for existing key", () => {
    expect(registerNodeResultHas(result, "name")).toBe(true);
  });

  it("has returns false for missing key", () => {
    expect(registerNodeResultHas(result, "missing")).toBe(false);
  });
});
