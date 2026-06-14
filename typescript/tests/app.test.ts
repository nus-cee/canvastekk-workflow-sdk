import { describe, it, expect, beforeAll, afterAll } from "vitest";
import request from "supertest";
import { createNodeApp } from "../src/app.js";
import { BaseNode } from "../src/base-node.js";
import type { WorkflowNodeManifest } from "../src/definition.js";
import type { ExecutionContext } from "../src/context.js";
import { NodeAuth } from "../src/auth.js";

class TestNode extends BaseNode {
  definition: WorkflowNodeManifest = {
    name: "test-node",
    version: "1.0.0",
    title: "Test Node",
    description: "A test node",
    input_schema: {
      type: "object",
      properties: { message: { type: "string" } },
    },
    output_schema: {
      type: "object",
      properties: { result: { type: "string" } },
    },
  };

  execute(inputs: Record<string, unknown>, _context: ExecutionContext): Record<string, unknown> {
    return { result: `echo: ${inputs.message ?? ""}` };
  }
}

class HealthCheckNode extends BaseNode {
  definition: WorkflowNodeManifest = {
    name: "health-node",
    version: "2.0.0",
    title: "Health Node",
    description: "Node with health checks",
    input_schema: { type: "object" },
    output_schema: { type: "object" },
  };

  execute(): Record<string, unknown> {
    return {};
  }

  healthCheck(): Record<string, boolean> {
    return { db: true, cache: false };
  }
}

describe("Express endpoints", () => {
  const node = new TestNode();
  const app = createNodeApp(node);

  describe("POST /execute", () => {
    it("executes successfully", async () => {
      const resp = await request(app)
        .post("/execute")
        .send({ run_id: "run-1", node_id: "test-1", inputs: { message: "hello" } });

      expect(resp.status).toBe(200);
      expect(resp.body.status).toBe("pass");
      expect(resp.body.outputs.result).toBe("echo: hello");
      expect(resp.body.execution_id).toBeDefined();
      expect(resp.body.duration_ms).toBeGreaterThanOrEqual(0);
    });

    it("returns 400 for missing required fields", async () => {
      const resp = await request(app)
        .post("/execute")
        .send({});

      expect(resp.status).toBe(400);
      expect(resp.body.detail).toBeDefined();
    });
  });

  describe("GET /health", () => {
    it("returns healthy when no checks", async () => {
      const resp = await request(app).get("/health");
      expect(resp.status).toBe(200);
      expect(resp.body.status).toBe("healthy");
      expect(resp.body.node_id).toBe("test-node-v1.0.0");
      expect(resp.body.version).toBe("1.0.0");
    });

    it("returns degraded when some checks fail", async () => {
      const healthNode = new HealthCheckNode();
      const healthApp = createNodeApp(healthNode);
      const resp = await request(healthApp).get("/health");
      expect(resp.body.status).toBe("degraded");
      expect(resp.body.checks).toEqual({ db: true, cache: false });
    });
  });

  describe("GET /manifest", () => {
    it("returns node definition with sdk_version and mode", async () => {
      const resp = await request(app).get("/manifest");
      expect(resp.status).toBe(200);
      expect(resp.body.name).toBe("test-node");
      expect(resp.body.version).toBe("1.0.0");
      expect(resp.body.sdk_version).toBeDefined();
      expect(resp.body.mode).toBeDefined();
    });
  });

  describe("POST /hook", () => {
    it("returns 501 when not implemented", async () => {
      const resp = await request(app)
        .post("/hook")
        .send({ event: "test" });

      expect(resp.status).toBe(501);
      expect(resp.body.detail).toContain("not implemented");
    });
  });

  describe("GET /metrics", () => {
    it("returns metrics summary", async () => {
      const resp = await request(app).get("/metrics");
      expect(resp.status).toBe(200);
      expect(resp.body.total_executions).toBeDefined();
    });
  });

  describe("GET /live", () => {
    it("returns alive", async () => {
      const resp = await request(app).get("/live");
      expect(resp.status).toBe(200);
      expect(resp.body.status).toBe("alive");
    });
  });

  describe("GET /ready", () => {
    it("returns ready when checks pass", async () => {
      const resp = await request(app).get("/ready");
      expect(resp.status).toBe(200);
      expect(resp.body.status).toBe("ready");
    });

    it("returns 503 when checks fail", async () => {
      const healthNode = new HealthCheckNode();
      const healthApp = createNodeApp(healthNode);
      const resp = await request(healthApp).get("/ready");
      expect(resp.status).toBe(503);
      expect(resp.body.status).toBe("not_ready");
    });
  });
});

describe("X-SDK-Version header", () => {
  it("is present on all responses", async () => {
    const node = new TestNode();
    const app = createNodeApp(node);
    const resp = await request(app).get("/health");
    expect(resp.headers["x-sdk-version"]).toBeDefined();
  });
});

describe("Auth middleware", () => {
  it("rejects requests without API key", async () => {
    const node = new TestNode();
    process.env.CANVASTEKK_API_KEY = "test-secret-key";
    delete process.env.CANVASTEKK_DEV_MODE;
    const auth = NodeAuth.apiKey();
    const app = createNodeApp(node, { dependencies: [auth] });

    const resp = await request(app)
      .get("/health");

    expect(resp.status).toBe(401);
    delete process.env.CANVASTEKK_API_KEY;
  });

  it("accepts requests with valid API key", async () => {
    const node = new TestNode();
    process.env.CANVASTEKK_API_KEY = "test-secret-key";
    delete process.env.CANVASTEKK_DEV_MODE;
    const auth = NodeAuth.apiKey();
    const app = createNodeApp(node, { dependencies: [auth] });

    const resp = await request(app)
      .get("/health")
      .set("X-API-Key", "test-secret-key");

    expect(resp.status).toBe(200);
    delete process.env.CANVASTEKK_API_KEY;
  });

  it("bypasses auth in dev mode", async () => {
    const node = new TestNode();
    process.env.CANVASTEKK_API_KEY = "test-secret-key";
    process.env.CANVASTEKK_DEV_MODE = "true";
    const auth = NodeAuth.apiKey();
    const app = createNodeApp(node, { dependencies: [auth] });

    const resp = await request(app)
      .get("/health");

    expect(resp.status).toBe(200);
    delete process.env.CANVASTEKK_API_KEY;
    delete process.env.CANVASTEKK_DEV_MODE;
  });
});
