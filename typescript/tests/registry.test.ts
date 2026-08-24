import { describe, it, expect } from "vitest";
import {
  buildRegistryPayload,
  extractNodeData,
  registerNodeResultGet,
  registerNodeResultHas,
} from "../src/registry.js";
import { RegistrationError } from "../src/exceptions.js";
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

describe("RegistrationError enrichment (DA-1955)", () => {
  it("extracts changed fields from node_version_immutable detail", () => {
    const detail = JSON.stringify({
      name: "test-node",
      version: "1.0.0",
      changed_fields: [
        { field: "input_schema", expected: {}, actual: { type: "object" } },
        { field: "invoke_url", expected: "http://old", actual: "http://new" },
      ],
    });
    const error = new RegistrationError(409, { error: "node_version_immutable", detail });

    expect(error.code).toBe("node_version_immutable");
    expect(error.guidance).toContain("input_schema");
    expect(error.guidance).toContain("invoke_url");
    expect(error.guidance).toContain("Bump");
  });

  it("maps other 409 to publish-higher guidance", () => {
    const error = new RegistrationError(409, { error: "resource_conflict", detail: "1.2.0 is newer" });

    expect(error.code).toBe("resource_conflict");
    expect(error.guidance).toContain("higher");
  });

  it("surfaces FastAPI 422 detail list", () => {
    const error = new RegistrationError(422, {
      detail: [{ loc: ["body", "name"], msg: "Field required", type: "missing" }],
    });

    expect(error.statusCode).toBe(422);
    expect(error.guidance).toContain("name");
    expect(error.guidance).toContain("Field required");
  });

  it("surfaces canonical 400 errors[] messages", () => {
    const error = new RegistrationError(400, {
      error: "bad_request",
      errors: [{ field: "version", message: "invalid semver" }],
    });

    expect(error.code).toBe("bad_request");
    expect(error.guidance).toContain("invalid semver");
  });

  it("unmapped codes get null guidance", () => {
    const error = new RegistrationError(418, { error: "teapot", detail: "short and stout" });

    expect(error.code).toBe("teapot");
    expect(error.guidance).toBeNull();
  });

  it("plain-text bodies keep null code", () => {
    const error = new RegistrationError(500, { detail: "Internal Server Error" });

    expect(error.code).toBeNull();
    expect(error.guidance).toBeNull();
  });
});
