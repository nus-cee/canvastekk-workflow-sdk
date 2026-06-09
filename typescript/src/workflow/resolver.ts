import type { WorkflowDefinitionSpec } from "./models.js";

export function resolveInputs(
  nodeId: string,
  spec: WorkflowDefinitionSpec,
  nodeOutputs: Record<string, Record<string, unknown>>,
): Record<string, unknown> {
  const node = spec.nodes.find((n) => n.id === nodeId);
  if (!node) throw new Error(`Node not found: ${nodeId}`);

  const resolved: Record<string, unknown> = { ...node.inputs };

  const incoming = spec.edges.filter((e) => e.toNode === nodeId);
  for (const edge of incoming) {
    const sourceOutputs = nodeOutputs[edge.fromNode] ?? {};
    const value = resolveOutput(sourceOutputs, edge.fromOutput);
    if (edge.toInput) {
      resolved[edge.toInput] = value;
    } else if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      Object.assign(resolved, value);
    }
  }

  return resolved;
}

function resolveOutput(
  sourceOutputs: Record<string, unknown>,
  fromOutput: string,
): unknown {
  if (!fromOutput) return sourceOutputs;

  if (fromOutput.includes(".")) {
    return walkDotPath(sourceOutputs, fromOutput);
  }

  return sourceOutputs[fromOutput];
}

function walkDotPath(data: Record<string, unknown>, path: string): unknown {
  let current: unknown = data;
  for (const segment of path.split(".")) {
    if (!segment) throw new Error(`Invalid dot-path '${path}' (empty segment)`);
    if (typeof current !== "object" || current === null) {
      throw new Error(`Cannot walk dot-path '${path}': segment '${segment}' hits non-dict`);
    }
    if (!(segment in (current as Record<string, unknown>))) {
      throw new Error(`Dot-path '${path}': segment '${segment}' not found`);
    }
    current = (current as Record<string, unknown>)[segment];
  }
  return current;
}
