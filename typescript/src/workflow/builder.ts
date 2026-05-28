import type { EdgeType, ResolutionStrategy, WorkflowEdge, WorkflowNode, WorkflowSpec } from "./models.js";
import { validate } from "./validation.js";

/**
 * Fluent API for building workflow specifications.
 */
export class WorkflowBuilder {
  private _name: string | null;
  private _nodes: WorkflowNode[] = [];
  private _edges: WorkflowEdge[] = [];
  private _nodeIds: Set<string> = new Set();
  private _hasStart = false;

  /**
   * Creates a new workflow builder.
   * @param name - Workflow name
   */
  constructor(name?: string | null) {
    this._name = name ?? null;
  }

  private checkDuplicate(nodeId: string): void {
    if (this._nodeIds.has(nodeId)) {
      throw new Error(`Duplicate node ID: '${nodeId}'`);
    }
  }

  /**
   * Adds a START node to the workflow.
   * @param nodeId - Node ID
   * @param opts - Start node options
   * @returns This builder for chaining
   */
  addStart(
    nodeId = "start",
    opts?: {
      outputs?: string[] | Record<string, unknown>;
      configSchema?: Record<string, unknown>;
    },
  ): this {
    if (this._hasStart) {
      throw new Error("Workflow already has a START node. Only one is allowed.");
    }
    this.checkDuplicate(nodeId);

    let configSchema = opts?.configSchema;
    if (configSchema === undefined && opts?.outputs) {
      const outputs = opts.outputs;
      const props = Array.isArray(outputs)
        ? Object.fromEntries(outputs.map((n) => [n, { type: "string" }]))
        : outputs;
      configSchema = { type: "object", properties: props };
    }

    this._nodes.push({
      id: nodeId,
      slug: "__start__",
      name: "START",
      inputs: configSchema ? { config_schema: configSchema } : {},
    });
    this._nodeIds.add(nodeId);
    this._hasStart = true;
    return this;
  }

  /**
   * Adds an END node to the workflow.
   * @param nodeId - Node ID
   * @returns This builder for chaining
   */
  addEnd(nodeId = "end"): this {
    this.checkDuplicate(nodeId);
    this._nodes.push({ id: nodeId, slug: "__end__", name: "END", inputs: {} });
    this._nodeIds.add(nodeId);
    return this;
  }

  /**
   * Adds a node to the workflow.
   * @param nodeId - Node ID
   * @param opts - Node options
   * @returns This builder for chaining
   */
  addNode(
    nodeId: string,
    opts: {
      slug: string;
      name?: string;
      inputs?: Record<string, unknown>;
      version?: string;
    },
  ): this {
    if (opts.slug === "__start__" || opts.slug === "__end__") {
      throw new Error(
        `Cannot use reserved slug '${opts.slug}'. Use addStart() or addEnd() instead.`,
      );
    }
    this.checkDuplicate(nodeId);
    this._nodes.push({
      id: nodeId,
      slug: opts.slug,
      name: opts.name ?? null,
      inputs: opts.inputs ?? {},
      version: opts.version ?? null,
    });
    this._nodeIds.add(nodeId);
    return this;
  }

  /**
   * Connects two nodes with an edge.
   * @param fromNode - Source node ID
   * @param toNode - Target node ID
   * @param opts - Edge options
   * @returns This builder for chaining
   */
  connect(
    fromNode: string,
    toNode: string,
    opts?: {
      fromOutput?: string;
      toInput?: string;
      edgeType?: EdgeType;
      resolutionStrategy?: ResolutionStrategy;
      condition?: string;
    },
  ): this {
    if (!this._nodeIds.has(fromNode)) {
      throw new Error(`Unknown source node: '${fromNode}'`);
    }
    if (!this._nodeIds.has(toNode)) {
      throw new Error(`Unknown target node: '${toNode}'`);
    }
    this._edges.push({
      id: crypto.randomUUID(),
      fromNode,
      toNode,
      fromOutput: opts?.fromOutput ?? "",
      toInput: opts?.toInput ?? "",
      edgeType: opts?.edgeType ?? "default",
      resolutionStrategy: opts?.resolutionStrategy ?? "auto",
      condition: opts?.condition ?? null,
    });
    return this;
  }

  /**
   * Builds the workflow specification.
   * @param opts - Build options
   * @returns Workflow specification
   */
  build(opts?: { validate?: boolean }): WorkflowSpec {
    const spec: WorkflowSpec = {
      name: this._name,
      nodes: [...this._nodes],
      edges: [...this._edges],
      metadata: {},
    };

    if (opts?.validate !== false) {
      const result = validate(spec);
      if (!result.isValid) {
        throw new Error(`Workflow validation failed: ${result.errors.join("; ")}`);
      }
    }

    return spec;
  }
}
