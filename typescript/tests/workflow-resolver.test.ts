import { describe, it, expect } from "vitest";
import { resolveInputs } from "../src/workflow/resolver.js";

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
        { id: "e1", fromNode: "src", toNode: "dest", fromOutput: "result", toInput: "input", edgeType: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { result: 99 },
    };
    const resolved = resolveInputs("dest", spec, nodeOutputs);
    expect(resolved).toEqual({ input: 99 });
  });

  it("flat key returns undefined when fromOutput does not exist", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", fromNode: "src", toNode: "dest", fromOutput: "missing", toInput: "input", edgeType: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { result: 99 },
    };
    const resolved = resolveInputs("dest", spec, nodeOutputs);
    expect(resolved).toEqual({ input: undefined });
  });

  it("dot-path resolves nested values", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", fromNode: "src", toNode: "dest", fromOutput: "nested.key", toInput: "input", edgeType: "default" as const, condition: null },
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
        { id: "e1", fromNode: "src", toNode: "dest", fromOutput: "invalid.path", toInput: "input", edgeType: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { invalid: 42 },
    };
    expect(() => resolveInputs("dest", spec, nodeOutputs)).toThrow(
      "Cannot walk dot-path 'invalid.path': segment 'path' hits non-dict"
    );
  });

  it("dot-path throws on missing segment", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", fromNode: "src", toNode: "dest", fromOutput: "missing.segment", toInput: "input", edgeType: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: {},
    };
    expect(() => resolveInputs("dest", spec, nodeOutputs)).toThrow(
      "Dot-path 'missing.segment': segment 'missing' not found"
    );
  });

  it("dot-path throws on empty segment", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", fromNode: "src", toNode: "dest", fromOutput: "..", toInput: "input", edgeType: "default" as const, condition: null },
      ],
      metadata: {},
    };
    expect(() => resolveInputs("dest", spec, {})).toThrow(
      "Invalid dot-path '..' (empty segment)"
    );
  });

  it("flat lookup for simple keys, dot-path for dotted keys", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest1", slug: "node-dest1", inputs: {} },
        { id: "dest2", slug: "node-dest2", inputs: {} },
      ],
      edges: [
        { id: "e1", fromNode: "src", toNode: "dest1", fromOutput: "result", toInput: "flat", edgeType: "default" as const, condition: null },
        { id: "e2", fromNode: "src", toNode: "dest2", fromOutput: "nested.key", toInput: "dot", edgeType: "default" as const, condition: null },
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

  it("empty fromOutput returns entire source outputs", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", fromNode: "src", toNode: "dest", fromOutput: "", toInput: "input", edgeType: "default" as const, condition: null },
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
        { id: "e1", fromNode: "src1", toNode: "dest", fromOutput: "out1", toInput: "in1", edgeType: "default" as const, condition: null },
        { id: "e2", fromNode: "src2", toNode: "dest", fromOutput: "out2", toInput: "in2", edgeType: "default" as const, condition: null },
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

  it("when toInput is omitted, spreads object output into resolved inputs", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: {} },
      ],
      edges: [
        { id: "e1", fromNode: "src", toNode: "dest", fromOutput: "result", toInput: "", edgeType: "default" as const, condition: null },
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
  });

  it("preserves static inputs alongside resolved edge inputs", () => {
    const spec = {
      nodes: [
        { id: "src", slug: "node-src", inputs: {} },
        { id: "dest", slug: "node-dest", inputs: { static: "kept" } },
      ],
      edges: [
        { id: "e1", fromNode: "src", toNode: "dest", fromOutput: "result", toInput: "dynamic", edgeType: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const nodeOutputs = {
      src: { result: 42 },
    };
    const resolved = resolveInputs("dest", spec, nodeOutputs);
    expect(resolved).toEqual({ static: "kept", dynamic: 42 });
  });
});
