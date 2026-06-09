/**
 * Edge type for workflow connections.
 *
 * - `"default"` — Standard data flow edge
 * - `"success"` — Traversed only on upstream success
 * - `"failure"` — Traversed only on upstream failure
 * - `"conditional"` — Traversed based on a condition expression
 */
export type EdgeType = "default" | "success" | "failure" | "conditional";

/**
 * Edge connecting two workflow nodes.
 *
 * @property id - Unique edge identifier
 * @property fromNode - Source node ID
 * @property toNode - Target node ID
 * @property fromOutput - Output field name on the source node
 * @property toInput - Input field name on the target node
 * @property edgeType - Edge type for conditional routing
 * @property condition - Optional condition expression for conditional edges
 */
export interface WorkflowEdgeDefinition {
  id: string;
  fromNode: string;
  toNode: string;
  fromOutput: string;
  toInput: string;
  edgeType: EdgeType;
  condition?: string | null;
}

export type WorkflowEdge = WorkflowEdgeDefinition;

/**
 * Node instance within a workflow definition.
 *
 * @property id - Unique node identifier within the workflow
 * @property workflow_node_id - Optional reference to a registered node
 * @property slug - Node type slug (e.g., "segmentation-v1.0.0")
 * @property version - Optional version override
 * @property name - Human-readable display name
 * @property x - Optional X position for visual layout
 * @property y - Optional Y position for visual layout
 * @property inputs - Static input values for this node instance
 * @property config_schema - Optional node configuration schema
 */
export interface WorkflowDefinitionNode {
  id: string;
  workflow_node_id?: string | null;
  slug?: string | null;
  version?: string | null;
  name?: string | null;
  x?: number | null;
  y?: number | null;
  inputs: Record<string, unknown>;
  config_schema?: Record<string, unknown> | null;
}

export type WorkflowNode = WorkflowDefinitionNode;

/**
 * Complete workflow specification (DAG of nodes and edges).
 *
 * @property nodes - Ordered list of workflow nodes
 * @property edges - List of connections between nodes
 * @property metadata - Arbitrary metadata for the workflow
 */
export interface WorkflowDefinitionSpec {
  nodes: WorkflowDefinitionNode[];
  edges: WorkflowEdgeDefinition[];
  metadata: Record<string, unknown>;
}

export type WorkflowSpec = WorkflowDefinitionSpec;
