/** Edge type for workflow connections. */
export type EdgeType = "default" | "success" | "failure" | "conditional";

/** Strategy for resolving output references. */
export type ResolutionStrategy = "auto" | "flat" | "dot_path";

/** Edge connecting two workflow nodes. */
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

/** Node in a workflow. */
export interface WorkflowNode {
  id: string;
  slug: string;
  version?: string | null;
  name?: string | null;
  x?: number | null;
  y?: number | null;
  inputs: Record<string, unknown>;
}

/** Complete workflow specification. */
export interface WorkflowSpec {
  name?: string | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  metadata: Record<string, unknown>;
}
