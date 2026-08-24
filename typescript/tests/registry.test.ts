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

  it("omits retry from request payload (DA-1955)", () => {
    const payload = buildRegistryPayload(testDef);
    expect(payload).not.toHaveProperty("retry");
    expect(payload).not.toHaveProperty("default_retry");
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

  it("omits node_role from request payload (DA-1955)", () => {
    const payload = buildRegistryPayload(testDef);
    expect(payload).not.toHaveProperty("node_role");
    expect(payload).not.toHaveProperty("node_status");
  });

  it("omits deprecation when null (DA-1582)", () => {
    const payload = buildRegistryPayload(testDef);
    expect(payload).not.toHaveProperty("deprecation");
  });

  it("omits deprecation from request payload when set (DA-1955)", () => {
    const deprecated = {
      ...testDef,
      deprecation: {
        deprecated_at: "2026-08-01",
        sunset_date: "2027-01-01",
        replacement_slug: "echo-v2",
        migration_url: "https://example.com/migrate",
        notice: "use echo-v2",
      },
    };
    const payload = buildRegistryPayload(deprecated);
    expect(payload).not.toHaveProperty("deprecation");
  });

  it("merges manifest compat fields into constraints (DA-1955)", () => {
    const def = {
      ...testDef,
      minimum_sdk_version: "0.22.0",
      maximum_sdk_version: "1.0.0",
      docs_url: "https://example.com/docs",
      changelog_url: "https://example.com/changelog",
    };
    const payload = buildRegistryPayload(def);
    expect(payload.constraints).toMatchObject({
      minimum_sdk_version: "0.22.0",
      maximum_sdk_version: "1.0.0",
      docs_url: "https://example.com/docs",
      changelog_url: "https://example.com/changelog",
    });
  });

  it("caller constraints win on key collision (DA-1955)", () => {
    const def = { ...testDef, minimum_sdk_version: "0.22.0" };
    const payload = buildRegistryPayload(def, {
      constraints: { minimum_sdk_version: "0.21.0", gpu_required: true },
    });
    expect(payload.constraints).toEqual({
      minimum_sdk_version: "0.21.0",
      gpu_required: true,
    });
  });

  it("omits constraints when nothing set (DA-1955)", () => {
    const payload = buildRegistryPayload(testDef);
    expect(payload).not.toHaveProperty("constraints");
  });

  it("payload keys are a subset of engine request fields (DA-1955)", () => {
    const def = {
      ...testDef,
      minimum_sdk_version: "0.22.0",
      docs_url: "https://example.com/docs",
      deprecation: { notice: "soon" },
    };
    const payload = buildRegistryPayload(def, {
      invokeUrl: "https://node.example.com",
      invokeConfig: { region: "us-east-1" },
      constraints: { gpu: true },
    });
    // Mirrors fastapi_app/schemas/api/nodes.py RegisterWorkflowNodeRequest
    // (extra='forbid') in canvastekk-workflow-engine.
    const engineRequestFields = new Set([
      "name", "version", "label", "description",
      "input_schema", "output_schema", "invoke_type", "invoke_url",
      "invoke_config", "category", "tags", "styles", "constraints",
      "token_cost", "timeout_seconds",
    ]);
    for (const key of Object.keys(payload)) {
      expect(engineRequestFields.has(key)).toBe(true);
    }
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
