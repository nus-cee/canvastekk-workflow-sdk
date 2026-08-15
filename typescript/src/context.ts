import { mkdirSync } from "node:fs";
import { join, resolve, sep } from "node:path";
import type { NodeExecutionRequest } from "./request.js";
import { getNodeLogger, type SdkLogger } from "./logging.js";

/**
 * Context provided to node execute() method.
 *
 * Provides access to:
 * - Run and node identifiers (`runId`, `nodeId`)
 * - Output directory for writing result files (`outputDir`, `outputPath()`)
 * - Downloads directory for auto-downloaded file inputs (`downloadsDir`)
 * - Metadata dict for download tracking (`metadata`)
 * - Logger with run/node context (`logger`)
 * - Progress reporting for long-running operations (`reportProgress()`)
 * - Token usage tracking for LLM-based nodes (`recordTokenUsage()`)
 * - Cooperative cancellation (`cancelSignal`) — aborted by the server when
 *   the request deadline expires; checked between download chunks.
 *   `execute()` itself cannot be interrupted.
 */
export class ExecutionContext {
  private _request: NodeExecutionRequest | null;
  private _outputDir: string;
  private _logger: SdkLogger;
  private _tokenUsage: Record<string, number>;
  private _metadata: Record<string, unknown>;
  private _downloadsDir: string | null;
  private _cancelSignal: AbortSignal | null;

  /**
   * Creates a new execution context.
   * @param opts - Context options
   */
  constructor(opts: {
    request?: NodeExecutionRequest | null;
    outputDir?: string;
    runId?: string;
    nodeId?: string;
    cancelSignal?: AbortSignal | null;
  } = {}) {
    const { request = null, outputDir, runId, nodeId, cancelSignal = null } = opts;

    this._request = request;
    const resolvedRunId = runId ?? request?.run_id ?? "local";
    const resolvedNodeId = nodeId ?? request?.node_id ?? "unknown";

    if (outputDir) {
      this._outputDir = outputDir;
    } else {
      const baseDir = process.env.CANVASTEKK_OUTPUT_DIR;
      if (baseDir) {
        this._outputDir = join(baseDir, resolvedRunId, resolvedNodeId);
      } else {
        this._outputDir = join("/tmp", resolvedRunId, resolvedNodeId);
      }
    }
    mkdirSync(this._outputDir, { recursive: true });

    this._logger = getNodeLogger(resolvedNodeId);
    this._tokenUsage = {};
    this._metadata = {};
    this._downloadsDir = null;
    this._cancelSignal = cancelSignal;
  }

  /** Cooperative cancellation signal — aborted when the request deadline expires. */
  get cancelSignal(): AbortSignal | null {
    return this._cancelSignal;
  }

  get runId(): string {
    if (this._request) return this._request.run_id;
    return this._outputDir.split("/").slice(-2, -1)[0] ?? "local";
  }

  get nodeId(): string {
    if (this._request) return this._request.node_id;
    return this._outputDir.split("/").pop() ?? "unknown";
  }

  get outputDir(): string {
    return this._outputDir;
  }

  get logger(): SdkLogger {
    return this._logger;
  }

  /**
   * Gets the full path for a file in the output directory.
   * @param filename - Filename to join with output directory
   * @returns Full file path
   * @throws {Error} If the filename escapes the output directory
   *   (path traversal — absolute paths or `..` segments).
   */
  outputPath(filename: string): string {
    const candidate = resolve(join(this._outputDir, filename));
    if (!candidate.startsWith(resolve(this._outputDir) + sep)) {
      throw new Error(`Output filename '${filename}' escapes the output directory`);
    }
    return candidate;
  }

  get downloadsDir(): string {
    if (this._downloadsDir === null) {
      this._downloadsDir = join(this._outputDir, "downloads");
      mkdirSync(this._downloadsDir, { recursive: true });
    }
    return this._downloadsDir;
  }

  get metadata(): Record<string, unknown> {
    return this._metadata;
  }

  set metadata(value: Record<string, unknown>) {
    this._metadata = value;
  }

  /**
   * Reports execution progress.
   * @param progress - Progress value between 0 and 1
   * @param message - Optional progress message
   */
  reportProgress(progress: number, message = ""): void {
    const percent = Math.round(progress * 100);
    let logMsg = `Progress: ${percent}%`;
    if (message) logMsg += ` - ${message}`;
    this._logger.info(logMsg);
  }

  recordTokenUsage(opts: {
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
  } = {}): void {
    this._tokenUsage = {
      prompt_tokens: opts.promptTokens ?? 0,
      completion_tokens: opts.completionTokens ?? 0,
      total_tokens: opts.totalTokens ?? 0,
    };
    this._logger.info(
      `Token usage: prompt=${this._tokenUsage.prompt_tokens}, completion=${this._tokenUsage.completion_tokens}, total=${this._tokenUsage.total_tokens}`,
    );
  }

  get tokenUsage(): Record<string, number> {
    return { ...this._tokenUsage };
  }
}
