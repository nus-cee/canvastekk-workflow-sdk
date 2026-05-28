import { describe, it, expect } from "vitest";
import { computeLevels } from "../src/workflow/level.js";

describe("computeLevels", () => {
  it("linear chain (start → node → end) produces correct levels", () => {
    const spec = {
      name: "linear",
      nodes: [
        { id: "start", slug: "__start__", name: "START", inputs: {} },
        { id: "n1", slug: "node-v1", inputs: {} },
        { id: "end", slug: "__end__", name: "END", inputs: {} },
      ],
      edges: [
        { id: "1", fromNode: "start", toNode: "n1", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "2", fromNode: "n1", toNode: "end", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
      ],
      metadata: {},
    };
    const levels = computeLevels(spec);
    expect(levels).toEqual([["start"], ["n1"], ["end"]]);
  });

  it("diamond/parallel graph produces correct levels", () => {
    const spec = {
      name: "diamond",
      nodes: [
        { id: "start", slug: "__start__", name: "START", inputs: {} },
        { id: "n1", slug: "node-v1", inputs: {} },
        { id: "n2", slug: "node-v2", inputs: {} },
        { id: "end", slug: "__end__", name: "END", inputs: {} },
      ],
      edges: [
        { id: "1", fromNode: "start", toNode: "n1", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "2", fromNode: "start", toNode: "n2", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "3", fromNode: "n1", toNode: "end", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "4", fromNode: "n2", toNode: "end", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
      ],
      metadata: {},
    };
    const levels = computeLevels(spec);
    // start is level 0, n1 and n2 are parallel (level 1), end is level 2
    expect(levels).toHaveLength(3);
    expect(levels[0]).toEqual(["start"]);
    expect(new Set(levels[1])).toEqual(new Set(["n1", "n2"]));
    expect(levels[2]).toEqual(["end"]);
  });

  it("empty spec returns []", () => {
    const spec = {
      name: "empty",
      nodes: [],
      edges: [],
      metadata: {},
    };
    const levels = computeLevels(spec);
    expect(levels).toEqual([]);
  });

  it("cycle throws Error", () => {
    const spec = {
      name: "cycle",
      nodes: [
        { id: "n1", slug: "node-v1", inputs: {} },
        { id: "n2", slug: "node-v2", inputs: {} },
        { id: "n3", slug: "node-v3", inputs: {} },
      ],
      edges: [
        { id: "1", fromNode: "n1", toNode: "n2", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "2", fromNode: "n2", toNode: "n3", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "3", fromNode: "n3", toNode: "n1", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
      ],
      metadata: {},
    };
    expect(() => computeLevels(spec)).toThrow("Workflow contains a cycle involving node(s):");
  });

  it("multiple parallel branches produce correct level counts", () => {
    const spec = {
      name: "multi-branch",
      nodes: [
        { id: "start", slug: "__start__", name: "START", inputs: {} },
        { id: "a", slug: "node-a", inputs: {} },
        { id: "b", slug: "node-b", inputs: {} },
        { id: "c", slug: "node-c", inputs: {} },
        { id: "d", slug: "node-d", inputs: {} },
        { id: "end", slug: "__end__", name: "END", inputs: {} },
      ],
      edges: [
        { id: "1", fromNode: "start", toNode: "a", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "2", fromNode: "start", toNode: "b", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "3", fromNode: "a", toNode: "c", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "4", fromNode: "b", toNode: "d", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "5", fromNode: "c", toNode: "end", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "6", fromNode: "d", toNode: "end", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
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
      name: "sorted-levels",
      nodes: [
        { id: "z", slug: "node-z", inputs: {} },
        { id: "a", slug: "node-a", inputs: {} },
        { id: "b", slug: "node-b", inputs: {} },
      ],
      edges: [
        { id: "1", fromNode: "a", toNode: "b", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
        { id: "2", fromNode: "a", toNode: "z", fromOutput: "", toInput: "", edgeType: "default" as const, resolutionStrategy: "auto" as const, condition: null },
      ],
      metadata: {},
    };
    const levels = computeLevels(spec);
    // a (in-degree 0) is level 0; b and z are level 1 (sorted)
    expect(levels).toEqual([["a"], ["b", "z"]]);
  });
});