import { describe, it, expect } from "vitest";
import { resolveInputs, ResolverError } from "../src/workflow/resolver.js";

describe("resolveInputs", () => {
  it("resolves from static node inputs", () => {
    const spec = {
      nodes: [
        { id: "n1", slug: "node-v1", inputs: { static: 42 } },
      ],
      edges: [],
      metadata: {},
    };
    const nodeOutputs: Record<string, Record<string, unknown>> = {};
    const resolved = resolveInputs("n1", spec, nodeOutputs);
    expect(resolved).toEqual({ static: 42 });
  });

  it("resolves from incoming edge outputs (flat key)", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "result", to_input: "input", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { result: 99 },
    };
    const resolved = resolveInputs("dest", spec, nodeOutputs);
    expect(resolved).toEqual({ input: 99 });
  });

  it("flat key throws when from_output does not exist", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "missing", to_input: "input", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { result: 99 },
    };
    expect(() => resolveInputs("dest", spec, nodeOutputs)).toThrow("Cannot resolve from_output 'missing'");
    expect(() => resolveInputs("dest", spec, nodeOutputs)).toThrow(ResolverError);
  });

  it("dot-path resolves nested values", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "nested.key", to_input: "input", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { nested: { key: "value" } },
    };
    const resolved = resolveInputs("dest", spec, nodeOutputs);
    expect(resolved).toEqual({ input: "value" });
  });

  it("dot-path throws on non-dict mid-path", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "invalid.path", to_input: "input", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { invalid: 42 },
    };
    expect(() => resolveInputs("dest", spec, nodeOutputs)).toThrow(
      "Cannot walk dot-path 'invalid.path': segment 'path' hits non-dict"
    );
    expect(() => resolveInputs("dest", spec, nodeOutputs)).toThrow(ResolverError);
  });

  it("dot-path throws on missing segment", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "missing.segment", to_input: "input", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: {},
    };
    expect(() => resolveInputs("dest", spec, nodeOutputs)).toThrow(
      "Dot-path 'missing.segment': segment 'missing' not found"
    );
    expect(() => resolveInputs("dest", spec, nodeOutputs)).toThrow(ResolverError);
  });

  it("dot-path throws on empty segment", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "..", to_input: "input", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    expect(() => resolveInputs("dest", spec, {})).toThrow(
      "Invalid dot-path '..' (empty segment)"
    );
    expect(() => resolveInputs("dest", spec, {})).toThrow(ResolverError);
  });

  it("flat lookup for simple keys, dot-path for dotted keys", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest1", slug: "node-dest1", inputs: {} },
        { id: "dest2", slug: "node-dest2", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest1", from_output: "result", to_input: "flat", edge_type: "default" as const, condition: null },
        { id: "e2", from_node: "src", to_node: "dest2", from_output: "nested.key", to_input: "dot", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { result: 42, nested: { key: "value" } },
    };
    const resolved1 = resolveInputs("dest1", spec, nodeOutputs);
    const resolved2 = resolveInputs("dest2", spec, nodeOutputs);
    expect(resolved1).toEqual({ flat: 42 });
    expect(resolved2).toEqual({ dot: "value" });
  });

  it("empty from_output returns entire source outputs", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "", to_input: "input", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { a: 1, b: 2 },
    };
    const resolved = resolveInputs("dest", spec, nodeOutputs);
    expect(resolved).toEqual({ input: { a: 1, b: 2 } });
  });

  it("merges multiple incoming edges into resolved inputs", () => {
    const spec = {
      nodes: [
        { id: "src1", slug: "node-src1", inputs: {} },
        { id: "src2", slug: "node-src2", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src1", to_node: "dest", from_output: "out1", to_input: "in1", edge_type: "default" as const, condition: null },
        { id: "e2", from_node: "src2", to_node: "dest", from_output: "out2", to_input: "in2", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src1: { out1: "a" },
      src2: { out2: "b" },
    };
    const resolved = resolveInputs("dest", spec, nodeOutputs);
    expect(resolved).toEqual({ in1: "a", in2: "b" });
  });

  it("when to_input is omitted, spreads object output into resolved inputs", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "result", to_input: "", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { result: { x: 1, y: 2 } },
    };
    const resolved = resolveInputs("dest", spec, nodeOutputs);
    expect(resolved).toEqual({ x: 1, y: 2 });
  });

  it("throws if node not found in spec", () => {
    const spec = {
      nodes: [{ id: "n1", slug: "node-v1", inputs: {} }],
      edges: [],
      metadata: {},
    };
    expect(() => resolveInputs("unknown", spec, {})).toThrow(
      "Node not found: unknown"
    );
    expect(() => resolveInputs("unknown", spec, {})).toThrow(ResolverError);
  });

  it("preserves static inputs alongside resolved edge inputs", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: { static: "kept" } },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "result", to_input: "dynamic", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { result: 42 },
    };
    const resolved = resolveInputs("dest", spec, nodeOutputs);
    expect(resolved).toEqual({ static: "kept", dynamic: 42 });
  });

  it("flat key takes priority over dot-path for keys containing dots", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "metadata.version", to_input: "input", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { "metadata.version": "1.0.0" },
    };
    const resolved = resolveInputs("dest", spec, nodeOutputs);
    expect(resolved).toEqual({ input: "1.0.0" });
  });

  it("falls back to dot-path when dotted key is not a flat key", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "nested.key", to_input: "input", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { nested: { key: "deep_value" } },
    };
    const resolved = resolveInputs("dest", spec, nodeOutputs);
    expect(resolved).toEqual({ input: "deep_value" });
  });

  it("ResolverError has correct code for missing key", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "src", to_node: "dest", from_output: "nonexistent", to_input: "input", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = { src: { existing: 1 } };

    try {
      resolveInputs("dest", spec, nodeOutputs);
      expect.fail("Should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ResolverError);
      const err = e as ResolverError;
      expect(err.code).toBe("KEY_NOT_FOUND");
      expect(err.nodeId).toBe("src");
      expect(err.message).toContain("available keys");
    }
  });

  it("ResolverError has correct code for node not found", () => {
    const spec = {
      nodes: [{ id: "n1", slug: "node-v1", inputs: {} }],
      edges: [],
      metadata: {},
    };
    try {
      resolveInputs("ghost", spec, {});
      expect.fail("Should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ResolverError);
      const err = e as ResolverError;
      expect(err.code).toBe("NODE_NOT_FOUND");
      expect(err.nodeId).toBe("ghost");
    }
  });

  it("error message includes source node context and available keys", () => {
    const spec = {
      nodes: [
        { id: "producer", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", from_node: "producer", to_node: "dest", from_output: "typo_key", to_input: "input", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = { producer: { correct_key: 42 } };

    try {
      resolveInputs("dest", spec, nodeOutputs);
      expect.fail("Should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ResolverError);
      const msg = (e as Error).message;
      expect(msg).toContain("producer");
      expect(msg).toContain("correct_key");
    }
  });
});
