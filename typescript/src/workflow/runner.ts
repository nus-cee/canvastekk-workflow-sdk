import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { WorkflowSpec } from "./models.js";
import type { NodeExecutor } from "./executor.js";
import { computeLevels } from "./level.js";
import { resolveInputs } from "./resolver.js";
import { CONTROL_FLOW_HANDLERS } from "./control-flow.js";
import { ExecutionContext } from "../context.js";

/** Error handling policy for workflow execution. */
export type ErrorPolicy = "fail_fast" | "continue";

/** Result of a single node execution. */
export interface NodeResult {
  node_id: string;
  slug: string;
  status: string;
  outputs?: Record<string, unknown> | null;
  duration_ms: number;
  error?: string | null;
  skipped_reason?: string | null;
}

/** Result of a complete workflow run. */
export interface WorkflowRunResult {
  status: string;
  final_outputs: Record<string, unknown>;
  node_results: NodeResult[];
  duration_ms: number;
  output_dir: string | null;
}

/**
 * Executes workflows locally with configurable error policy.
 */
export class WorkflowRunner {
  private _executor: NodeExecutor;
  private _errorPolicy: ErrorPolicy;
  private _outputDir: string | null;
  private _cleanup: boolean;

  /**
   * Creates a new workflow runner.
   * @param executor - Node execution strategy
   * @param opts - Runner options
   */
  constructor(
    executor: NodeExecutor,
    opts?: {
      errorPolicy?: ErrorPolicy;
      outputDir?: string;
      cleanup?: boolean;
    },
  ) {
    this._executor = executor;
    this._errorPolicy = opts?.errorPolicy ?? "fail_fast";
    this._outputDir = opts?.outputDir ?? null;
    this._cleanup = opts?.cleanup ?? true;
  }

  /**
   * Runs a workflow specification.
   * @param spec - Workflow specification
   * @param inputs - Initial workflow inputs
   * @returns Workflow run result
   */
  async run(
    spec: WorkflowSpec,
    inputs?: Record<string, unknown>,
  ): Promise<WorkflowRunResult> {
    const startTime = performance.now();
    const nodeMap = new Map(spec.nodes.map((n) => [n.id, n]));
    const nodeOutputs: Record<string, Record<string, unknown>> = {};
    const node_results: NodeResult[] = [];
    const failedNodes = new Set<string>();

    let runOutputDir: string;
    let autoCreated = false;

    if (this._outputDir) {
      runOutputDir = this._outputDir;
    } else {
      runOutputDir = mkdtempSync(join(tmpdir(), "wf-runner-"));
      autoCreated = true;
    }

    let status = "failed";
    let final_outputs: Record<string, unknown> = {};
    let duration_ms = 0;
    let result_output_dir: string | null = null;

    try {
      // Set initial inputs as start node outputs before processing levels
      const startNodes = spec.nodes.filter((n) => n.slug === "__start__");
      if (startNodes.length > 0) {
        const startNode = startNodes[0];
        const startInputs = inputs ?? {};
        // Use the control flow handler to set initial inputs as start node outputs
        const context = new ExecutionContext({ runId: "local", nodeId: startNode.id, outputDir: runOutputDir });
        const handler = CONTROL_FLOW_HANDLERS[startNode.slug];
        const startOutputs = handler(startInputs, context);
        nodeOutputs[startNode.id] = startOutputs;
      }

      const levels = computeLevels(spec);

      for (const level of levels) {
        const controlIds: string[] = [];
        const userIds: string[] = [];

        for (const nid of level) {
          const slug = nodeMap.get(nid)!.slug;
          if (slug in CONTROL_FLOW_HANDLERS) {
            controlIds.push(nid);
          } else {
            userIds.push(nid);
          }
        }

        for (const nid of controlIds) {
          const node = nodeMap.get(nid)!;
          const handler = CONTROL_FLOW_HANDLERS[node.slug];
          const resolved = resolveInputs(nid, spec, nodeOutputs);
          const context = new ExecutionContext({ runId: "local", nodeId: nid, outputDir: runOutputDir });
          const t0 = performance.now();
          try {
            const outputs = handler(resolved, context);
            nodeOutputs[nid] = outputs;
            node_results.push({
              node_id: nid,
              slug: node.slug,
              status: "completed",
              outputs,
              duration_ms: Math.round(performance.now() - t0),
            });
          } catch (exc) {
            failedNodes.add(nid);
            node_results.push({
              node_id: nid,
              slug: node.slug,
              status: "failed",
              duration_ms: Math.round(performance.now() - t0),
              error: String(exc),
            });
          }
        }

        const tasks: Promise<Record<string, unknown>>[] = [];
        const taskNodeIds: string[] = [];

        for (const nid of userIds) {
          const upstreamFailed = spec.edges.some(
            (e) => e.toNode === nid && failedNodes.has(e.fromNode),
          );
          if (upstreamFailed || failedNodes.has(nid)) {
            const node = nodeMap.get(nid)!;
            node_results.push({
              node_id: nid,
              slug: node.slug,
              status: "skipped",
              skipped_reason: "upstream_failed",
              duration_ms: 0,
            });
            failedNodes.add(nid);
            continue;
          }

          const node = nodeMap.get(nid)!;
          if (!this._executor.has(node.slug)) {
            node_results.push({
              node_id: nid,
              slug: node.slug,
              status: "failed",
              error: `No executor registered for slug '${node.slug}'`,
              duration_ms: 0,
            });
            failedNodes.add(nid);
            if (this._errorPolicy === "fail_fast") break;
            continue;
          }

          const resolved = resolveInputs(nid, spec, nodeOutputs);
          const context = new ExecutionContext({ runId: "local", nodeId: nid, outputDir: runOutputDir });
          tasks.push(this._executor.execute(node.slug, resolved, context));
          taskNodeIds.push(nid);
        }

        if (tasks.length > 0) {
          const results = await Promise.allSettled(tasks);
          for (let i = 0; i < results.length; i++) {
            const nid = taskNodeIds[i];
            const node = nodeMap.get(nid)!;
            const r = results[i];
            if (r.status === "rejected") {
              failedNodes.add(nid);
              node_results.push({
                node_id: nid,
                slug: node.slug,
                status: "failed",
                error: String(r.reason),
                duration_ms: 0,
              });
            } else {
              nodeOutputs[nid] = r.value;
              node_results.push({
                node_id: nid,
                slug: node.slug,
                status: "completed",
                outputs: r.value,
                duration_ms: 0,
              });
            }
          }
        }

        if (this._errorPolicy === "fail_fast" && failedNodes.size > 0) {
          break;
        }
      }

      final_outputs = {};
      for (const n of spec.nodes) {
        if (n.slug === "__end__" && n.id in nodeOutputs) {
          Object.assign(final_outputs, nodeOutputs[n.id]);
        }
      }

      duration_ms = Math.round(performance.now() - startTime);
      status = failedNodes.size === 0 ? "completed" : "failed";
    } finally {
      if (autoCreated && this._cleanup) {
        try {
          rmSync(runOutputDir, { recursive: true, force: true });
        } catch {
          // ignore cleanup errors
        }
        result_output_dir = null;
      } else {
        result_output_dir = runOutputDir;
      }
    }

    return {
      status,
      final_outputs,
      node_results,
      duration_ms,
      output_dir: result_output_dir,
    };
  }
}
