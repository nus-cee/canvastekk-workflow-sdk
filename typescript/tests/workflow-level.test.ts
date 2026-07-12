import { describe, it, expect } from "vitest";
import { computeLevels } from "../src/workflow/level.js";

describe("computeLevels", () => {
  it("linear chain (start → node → end) produces correct levels", () => {
    const spec = {
      nodes: [
        { id: "start", slug: "__start__", name: "START", inputs: {} },
        { id: "n1", slug: "node-v1", inputs: {} },
        { id: "end", slug: "__end__", name: "END", inputs: {} },
      ],
      edges: [
        { id: "1", from_node: "start", to_node: "n1", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "2", from_node: "n1", to_node: "end", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const levels = computeLevels(spec);
    expect(levels).toEqual([["start"], ["n1"], ["end"]]);
  });

  it("diamond/parallel graph produces correct levels", () => {
    const spec = {
      nodes: [
        { id: "start", slug: "__start__", name: "START", inputs: {} },
        { id: "n1", slug: "node-v1", inputs: {} },
        { id: "n2", slug: "node-v2", inputs: {} },
        { id: "end", slug: "__end__", name: "END", inputs: {} },
      ],
      edges: [
        { id: "1", from_node: "start", to_node: "n1", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "2", from_node: "start", to_node: "n2", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "3", from_node: "n1", to_node: "end", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "4", from_node: "n2", to_node: "end", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const levels = computeLevels(spec);
    expect(levels).toHaveLength(3);
    expect(levels[0]).toEqual(["start"]);
    expect(new Set(levels[1])).toEqual(new Set(["n1", "n2"]));
    expect(levels[2]).toEqual(["end"]);
  });

  it("empty spec returns []", () => {
    const spec = {
      nodes: [],
      edges: [],
      metadata: {},
    };
    const levels = computeLevels(spec);
    expect(levels).toEqual([]);
  });

  it("cycle throws Error", () => {
    const spec = {
      nodes: [
        { id: "n1", slug: "node-v1", inputs: {} },
        { id: "n2", slug: "node-v2", inputs: {} },
        { id: "n3", slug: "node-v3", inputs: {} },
      ],
      edges: [
        { id: "1", from_node: "n1", to_node: "n2", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "2", from_node: "n2", to_node: "n3", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "3", from_node: "n3", to_node: "n1", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    expect(() => computeLevels(spec)).toThrow("Workflow contains a cycle involving node(s):");
  });

  it("multiple parallel branches produce correct level counts", () => {
    const spec = {
      nodes: [
        { id: "start", slug: "__start__", name: "START", inputs: {} },
        { id: "a", slug: "node-a", inputs: {} },
        { id: "b", slug: "node-b", inputs: {} },
        { id: "c", slug: "node-c", inputs: {} },
        { id: "d", slug: "node-d", inputs: {} },
        { id: "end", slug: "__end__", name: "END", inputs: {} },
      ],
      edges: [
        { id: "1", from_node: "start", to_node: "a", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "2", from_node: "start", to_node: "b", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "3", from_node: "a", to_node: "c", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "4", from_node: "b", to_node: "d", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "5", from_node: "c", to_node: "end", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "6", from_node: "d", to_node: "end", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const levels = computeLevels(spec);
    expect(levels).toHaveLength(4);
    expect(levels[0]).toEqual(["start"]);
    expect(new Set(levels[1])).toEqual(new Set(["a", "b"]));
    expect(new Set(levels[2])).toEqual(new Set(["c", "d"]));
    expect(levels[3]).toEqual(["end"]);
  });

  it("returns levels with node IDs sorted within each level", () => {
    const spec = {
      nodes: [
        { id: "z", slug: "node-z", inputs: {} },
        { id: "a", slug: "node-a", inputs: {} },
        { id: "b", slug: "node-b", inputs: {} },
      ],
      edges: [
        { id: "1", from_node: "a", to_node: "b", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
        { id: "2", from_node: "a", to_node: "z", from_output: "", to_input: "", edge_type: "default" as const, condition: null },
      ],
      metadata: {},
    };
    const levels = computeLevels(spec);
    expect(levels).toEqual([["a"], ["b", "z"]]);
  });
});
