/**
 * Edge type for workflow connections.
 *
 * - `"default"` — Standard data flow edge
 * - `"success"` — Traversed only on upstream success
 * - `"failure"` — Traversed only on upstream failure
 * - `"conditional"` — Traversed based on a condition expression
 */
export type EdgeType = "default" | "success" | "failure" | "conditional";

/** Strategy for resolving output references. */
export type ResolutionStrategy = "auto" | "flat" | "dot_path";

/**
 * Edge connecting two workflow nodes.
 *
 * @property id - Unique edge identifier
 * @property fromNode - Source node ID
 * @property toNode - Target node ID
 * @property fromOutput - Output field name on the source node
 * @property toInput - Input field name on the target node
 * @property edgeType - Edge type for conditional routing
 * @property resolutionStrategy - How to resolve the output reference
 * @property condition - Optional condition expression for conditional edges
 */
export interface WorkflowEdge {
  id: string;
  fromNode: string;
  toNode: string;
  fromOutput: string;
  toInput: string;
  edgeType: EdgeType;
  resolutionStrategy: ResolutionStrategy;
  condition?: string | null;
}

/**
 * Node instance within a workflow definition.
 *
 * @property id - Unique node identifier within the workflow
 * @property slug - Node type slug (e.g., "segmentation-v1.0.0")
 * @property version - Optional version override
 * @property name - Human-readable display name
 * @property x - Optional X position for visual layout
 * @property y - Optional Y position for visual layout
 * @property inputs - Static input values for this node instance
 */
export interface WorkflowNode {
  id: string;
  slug: string;
  version?: string | null;
  name?: string | null;
  x?: number | null;
  y?: number | null;
  inputs: Record<string, unknown>;
}

/**
 * Complete workflow specification (DAG of nodes and edges).
 *
 * @property name - Optional workflow name
 * @property nodes - Ordered list of workflow nodes
 * @property edges - List of connections between nodes
 * @property metadata - Arbitrary metadata for the workflow
 */
export interface WorkflowSpec {
  name?: string | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  metadata: Record<string, unknown>;
}
