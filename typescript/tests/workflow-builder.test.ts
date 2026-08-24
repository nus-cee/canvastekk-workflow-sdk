import { describe, it, expect } from "vitest";
import { WorkflowBuilder } from "../src/workflow/builder.js";

describe("WorkflowBuilder", () => {
  describe("basic building", () => {
    it("builds a valid spec with start, node, and end", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start", { outputs: ["input_file"] })
        .addNode("process", { slug: "echo-v1.0.0" })
        .addEnd("end")
        .connect("start", "process", { fromOutput: "input_file", toInput: "message" })
        .connect("process", "end", { fromOutput: "result", toInput: "output" })
        .build();

      expect(spec.nodes).toHaveLength(3);
      expect(spec.edges).toHaveLength(2);
      expect(spec.nodes[0].slug).toBe("__start__");
      expect(spec.nodes[1].slug).toBe("echo-v1.0.0");
      expect(spec.nodes[2].slug).toBe("__end__");
    });

  	it("converts outputs: string[] to configSchema correctly", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start", { outputs: ["file1", "file2"] })
        .addNode("n1", { slug: "test-v1" })
        .addEnd("end")
        .connect("start", "n1")
        .connect("n1", "end")
        .build();

      const startNode = spec.nodes.find((n) => n.id === "start");
      expect(startNode?.config_schema).toEqual({
        type: "object",
        properties: {
          file1: { type: "string" },
          file2: { type: "string" },
        },
      });
    });

    it("rejects duplicate node IDs", async () => {
      const builder = new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", { slug: "test-v1" });
      expect(() => builder.addNode("n1", { slug: "another-v1" })).toThrow(
        "Duplicate node ID: 'n1'"
      );
    });

    it("rejects reserved slugs (__start__, __end__) in addNode", () => {
      const builder = new WorkflowBuilder().addStart("start");
      expect(() => builder.addNode("n1", { slug: "__start__" })).toThrow(
        "Cannot use reserved slug '__start__'. Use addStart() or addEnd() instead."
      );
      expect(() => builder.addNode("n2", { slug: "__end__" })).toThrow(
        "Cannot use reserved slug '__end__'. Use addStart() or addEnd() instead."
      );
    });

    it("enforces exactly 1 START node", async () => {
      const builder = new WorkflowBuilder().addStart("start");
      expect(() => builder.addStart("start2")).toThrow(
        "Workflow already has a START node. Only one is allowed."
      );
    });

    it("allows multiple END nodes", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", { slug: "test-v1" })
        .addEnd("end1")
        .addEnd("end2")
        .connect("start", "n1")
        .connect("n1", "end1")
        .connect("n1", "end2")
        .build();

      const endNodes = spec.nodes.filter((n) => n.slug === "__end__");
      expect(endNodes).toHaveLength(2);
      expect(endNodes.map((n) => n.id)).toContain("end1");
      expect(endNodes.map((n) => n.id)).toContain("end2");
    });

    it("rejects unknown source in connect()", () => {
      const builder = new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", { slug: "test-v1" })
        .addEnd("end");
      expect(() => builder.connect("unknown", "n1")).toThrow(
        "Unknown source node: 'unknown'"
      );
    });

    it("rejects unknown target in connect()", () => {
      const builder = new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", { slug: "test-v1" })
        .addEnd("end");
      expect(() => builder.connect("start", "unknown")).toThrow(
        "Unknown target node: 'unknown'"
      );
    });

    it("builds without validation when validate: false", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", { slug: "test-v1" })
        .addEnd("end")
        .connect("start", "n1")
        .build({ validate: false });

      expect(spec.nodes).toHaveLength(3);
      expect(spec.edges).toHaveLength(1);
    });

    it("sets edge options (from_output, to_input, edge_type, condition)", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", { slug: "test-v1" })
        .addEnd("end")
        .connect("start", "n1", {
          fromOutput: "data",
          toInput: "input",
          edgeType: "success",
          condition: "value > 0",
        })
        .connect("n1", "end")
        .build();

      const edge = spec.edges[0];
      expect(edge.from_output).toBe("data");
      expect(edge.to_input).toBe("input");
      expect(edge.edge_type).toBe("success");
      expect(edge.condition).toBe("value > 0");
    });

  it("spec includes metadata fields", async () => {
    const spec = await new WorkflowBuilder()
      .addStart("start")
      .addNode("n1", { slug: "test-v1" })
      .addEnd("end")
      .connect("start", "n1")
      .connect("n1", "end")
      .build();

    expect(spec).toHaveProperty("metadata");
    expect(spec.metadata).toEqual({});
  });

    it("defaults edge from_output/to_input to empty string when not provided", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", { slug: "test-v1" })
        .addEnd("end")
        .connect("start", "n1")
        .connect("n1", "end")
        .build();

      expect(spec.edges[0].from_output).toBe("");
      expect(spec.edges[0].to_input).toBe("");
    });

    it("defaults edge_type when not provided", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", { slug: "test-v1" })
        .addEnd("end")
        .connect("start", "n1", { fromOutput: "out", toInput: "in" })
        .connect("n1", "end")
        .build();

      expect(spec.edges[0].edge_type).toBe("default");
      expect(spec.edges[0].condition).toBe(null);
    });

    it("sets node name and version when provided", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", {
          slug: "test-v1.0.0",
          name: "Test Node",
          version: "1.0.0",
        })
        .addEnd("end")
        .connect("start", "n1")
        .connect("n1", "end")
        .build();

      const node = spec.nodes.find((n) => n.id === "n1");
      expect(node?.name).toBe("Test Node");
      expect(node?.version).toBe("1.0.0");
    });

    it("defaults node name to null, version to null when omitted", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", { slug: "test-v1" })
        .addEnd("end")
        .connect("start", "n1")
        .connect("n1", "end")
        .build();

      const node = spec.nodes.find((n) => n.id === "n1");
      expect(node?.name).toBe(null);
      expect(node?.version).toBe(null);
    });

    it("adds start with default ID 'start' when omitted", async () => {
      const spec = await new WorkflowBuilder()
        .addStart()
        .addNode("n1", { slug: "test-v1" })
        .addEnd("end")
        .connect("start", "n1")
        .connect("n1", "end")
        .build();

      expect(spec.nodes[0].id).toBe("start");
      expect(spec.nodes[0].slug).toBe("__start__");
    });

    it("adds end with default ID 'end' when omitted", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", { slug: "test-v1" })
        .addEnd()
        .connect("start", "n1")
        .connect("n1", "end")
        .build();

      expect(spec.nodes[2].id).toBe("end");
      expect(spec.nodes[2].slug).toBe("__end__");
    });

    it("adds node with inputs when provided", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", { slug: "test-v1", inputs: { param: 42 } })
        .addEnd("end")
        .connect("start", "n1")
        .connect("n1", "end")
        .build();

      const node = spec.nodes.find((n) => n.id === "n1");
      expect(node?.inputs).toEqual({ param: 42 });
    });

    it("addNode passes workflowNodeId and configSchema", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", {
          slug: "test-v1",
          workflowNodeId: "wn-123",
          configSchema: { type: "object", properties: { x: { type: "number" } } },
        })
        .addEnd("end")
        .connect("start", "n1")
        .connect("n1", "end")
        .build();

      const node = spec.nodes.find((n) => n.id === "n1");
      expect(node?.workflow_node_id).toBe("wn-123");
      expect(node?.config_schema).toEqual({ type: "object", properties: { x: { type: "number" } } });
    });

    it("slug is optional in addNode", async () => {
      const spec = await new WorkflowBuilder()
        .addStart("start")
        .addNode("n1", {})
        .addEnd("end")
        .connect("start", "n1")
        .connect("n1", "end")
        .build();

      const node = spec.nodes.find((n) => n.id === "n1");
      expect(node?.slug).toBe(null);
    });
  });
});
