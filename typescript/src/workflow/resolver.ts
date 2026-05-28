import type { WorkflowSpec, ResolutionStrategy } from "./models.js";

/**
 * Resolves all inputs for a node from upstream outputs.
 * @param nodeId - Target node ID
 * @param spec - Workflow specification
 * @param nodeOutputs - Outputs from executed nodes
 * @returns Resolved input dictionary
 */
export function resolveInputs(
  nodeId: string,
  spec: WorkflowSpec,
  nodeOutputs: Record<string, Record<string, unknown>>,
): Record<string, unknown> {
  const node = spec.nodes.find((n) => n.id === nodeId);
  if (!node) throw new Error(`Node not found: ${nodeId}`);

  const resolved: Record<string, unknown> = { ...node.inputs };

  const incoming = spec.edges.filter((e) => e.toNode === nodeId);
  for (const edge of incoming) {
    const sourceOutputs = nodeOutputs[edge.fromNode] ?? {};
    const value = resolveOutput(sourceOutputs, edge.fromOutput, edge.resolutionStrategy);
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
  strategy: ResolutionStrategy,
): unknown {
  if (!fromOutput) return sourceOutputs;

  if (strategy === "flat") {
    return sourceOutputs[fromOutput];
  }

  if (strategy === "dot_path") {
    return walkDotPath(sourceOutputs, fromOutput);
  }

  // AUTO: flat first, dot-path fallback
  if (fromOutput in sourceOutputs) {
    return sourceOutputs[fromOutput];
  }
  if (fromOutput.includes(".")) {
    return walkDotPath(sourceOutputs, fromOutput);
  }
  throw new Error(`Cannot resolve from_output '${fromOutput}' with AUTO strategy`);
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
