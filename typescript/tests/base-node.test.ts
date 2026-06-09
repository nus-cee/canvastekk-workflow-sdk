import { describe, it, expect } from "vitest";
import { BaseNode } from "../src/base-node.js";
import type { WorkflowNodeManifest } from "../src/definition.js";
import type { ExecutionContext } from "../src/context.js";
import { NodeValidationError, NodeOutputValidationError } from "../src/exceptions.js";
import { TimingMiddleware } from "../src/middleware.js";

class EchoNode extends BaseNode {
  definition: WorkflowNodeManifest = {
    name: "echo",
    version: "1.0.0",
    title: "Echo",
    description: "Returns input unchanged",
    input_schema: {
      type: "object",
      properties: { message: { type: "string" } },
      required: ["message"],
    },
    output_schema: {
      type: "object",
      properties: { message: { type: "string" } },
      required: ["message"],
    },
  };

  execute(inputs: Record<string, unknown>, _context: ExecutionContext): Record<string, unknown> {
    return { message: inputs.message as string };
  }
}

class FailingNode extends BaseNode {
  definition: WorkflowNodeManifest = {
    name: "fail-node",
    version: "1.0.0",
    title: "Fail",
    description: "Always fails",
    input_schema: { type: "object" },
    output_schema: { type: "object" },
  };

  execute(): Record<string, unknown> {
    throw new Error("intentional failure");
  }
}

class ValidatingNode extends BaseNode {
  definition: WorkflowNodeManifest = {
    name: "validating",
    version: "1.0.0",
    title: "Validating",
    description: "Tests validation",
    input_schema: {
      type: "object",
      properties: {
        count: { type: "number" },
      },
      required: ["count"],
    },
    output_schema: {
      type: "object",
      properties: {
        result: { type: "string" },
      },
      required: ["result"],
    },
  };

  execute(inputs: Record<string, unknown>): Record<string, unknown> {
    return { result: `count is ${inputs.count}` };
  }
}

describe("BaseNode", () => {
  describe("run() success path", () => {
    it("executes and returns success response", async () => {
      const node = new EchoNode();
      const resp = await node.run({
        run_id: "run-1",
        node_id: "echo-1",
        inputs: { message: "hello" },
      });
      expect(resp.status).toBe("pass");
      expect(resp.outputs).toEqual({ message: "hello" });
      expect(resp.duration_ms).toBeGreaterThanOrEqual(0);
      expect(resp.execution_id).toBeDefined();
    });
  });

  describe("run() validation error", () => {
    it("returns fail for invalid inputs", async () => {
      const node = new ValidatingNode();
      const resp = await node.run({
        run_id: "run-2",
        node_id: "v-1",
        inputs: {}, // missing required "count"
      });
      expect(resp.status).toBe("fail");
      expect(resp.error_code).toBe("VALIDATION_ERROR");
      expect(resp.error).toContain("Input validation failed");
    });
  });

  describe("run() execution error", () => {
    it("returns fail for thrown errors", async () => {
      const node = new FailingNode();
      const resp = await node.run({
        run_id: "run-3",
        node_id: "f-1",
        inputs: {},
      });
      expect(resp.status).toBe("fail");
      expect(resp.error).toBe("intentional failure");
      expect(resp.error_type).toBe("Error");
    });
  });

  describe("addMiddleware", () => {
    it("returns this for chaining", () => {
      const node = new EchoNode();
      const result = node.addMiddleware(new TimingMiddleware());
      expect(result).toBe(node);
    });
  });

  describe("middleware hooks", () => {
    it("fires timing middleware hooks", async () => {
      const node = new EchoNode();
      const timing = new TimingMiddleware();
      node.addMiddleware(timing);

      await node.run({
        run_id: "run-4",
        node_id: "echo-2",
        inputs: { message: "test" },
      });

      expect(timing.timings).toHaveLength(1);
      expect(timing.timings[0].status).toBe("pass");
    });

    it("fires error hook on failure", async () => {
      const node = new FailingNode();
      const timing = new TimingMiddleware();
      node.addMiddleware(timing);

      await node.run({
        run_id: "run-5",
        node_id: "f-2",
        inputs: {},
      });

      expect(timing.timings).toHaveLength(1);
      expect(timing.timings[0].status).toBe("fail");
    });
  });

  describe("healthCheck", () => {
    it("returns empty dict by default", () => {
      const node = new EchoNode();
      expect(node.healthCheck()).toEqual({});
    });
  });

  describe("hook", () => {
    it("returns null by default", () => {
      const node = new EchoNode();
      expect(node.hook({})).toBeNull();
    });
  });

  describe("token usage fallback", () => {
    it("uses definition.token_cost when no context token usage", async () => {
      const node = new EchoNode();
      const resp = await node.run({
        run_id: "run-6",
        node_id: "echo-3",
        inputs: { message: "test" },
      });
      expect(resp.token_usage).toBe(0.0);
    });
  });
});
