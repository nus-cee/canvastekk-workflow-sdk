import type { ExecutionContext } from "../context.js";
import type { WorkflowSpec } from "./models.js";

/**
 * Abstract base for node execution strategies.
 */
export abstract class NodeExecutor {
  /**
   * Executes a node by slug.
   * @param slug - Node slug
   * @param inputs - Node inputs
   * @param context - Execution context
   * @returns Node outputs
   */
  abstract execute(
    slug: string,
    inputs: Record<string, unknown>,
    context: ExecutionContext,
  ): Promise<Record<string, unknown>>;
  abstract has(slug: string): boolean;
}

/**
 * Executes nodes in-process without HTTP calls.
 */
export class InProcessExecutor extends NodeExecutor {
  private _registry: Map<string, { execute: (inputs: Record<string, unknown>, ctx: ExecutionContext) => Record<string, unknown> | Promise<Record<string, unknown>> }> = new Map();

  /**
   * Registers a node executor function.
   * @param slug - Node slug
   * @param node - Node with execute method
   * @returns This executor for chaining
   */
  register(slug: string, node: { execute: (inputs: Record<string, unknown>, ctx: ExecutionContext) => Record<string, unknown> | Promise<Record<string, unknown>> }): this {
    this._registry.set(slug, node);
    return this;
  }

  override async execute(slug: string, inputs: Record<string, unknown>, context: ExecutionContext): Promise<Record<string, unknown>> {
    const node = this._registry.get(slug);
    if (!node) throw new Error(`No node registered for slug '${slug}'`);
    return node.execute(inputs, context);
  }

  has(slug: string): boolean {
    return this._registry.has(slug);
  }
}

/**
 * Executes nodes via HTTP requests to remote services.
 */
export class HttpExecutor extends NodeExecutor {
  private _urls: Map<string, string> = new Map();
  private _timeout: number;

  /**
   * Creates a new HTTP executor.
   * @param opts - Executor options
   */
  constructor(opts?: { timeout?: number }) {
    super();
    this._timeout = opts?.timeout ?? 300_000;
  }

  /**
   * Registers a node URL.
   * @param slug - Node slug
   * @param url - Node base URL
   * @returns This executor for chaining
   */
  registerUrl(slug: string, url: string): this {
    this._urls.set(slug, url.replace(/\/$/, ""));
    return this;
  }

  override async execute(slug: string, inputs: Record<string, unknown>, context: ExecutionContext): Promise<Record<string, unknown>> {
    const url = this._urls.get(slug);
    if (!url) throw new Error(`No URL registered for slug '${slug}'`);

    const payload = {
      run_id: context.runId,
      node_id: context.nodeId,
      inputs,
    };

    const resp = await fetch(`${url}/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(this._timeout),
    });

    if (!resp.ok) {
      throw new Error(`Node '${slug}' returned HTTP ${resp.status}`);
    }

    const data = await resp.json() as Record<string, unknown>;
    if (data.status === "pass") {
      return (data.outputs ?? {}) as Record<string, unknown>;
    }
    throw new Error(`Node '${slug}' returned failure: ${data.error ?? "unknown"}`);
  }

  has(slug: string): boolean {
    return this._urls.has(slug);
  }
}
