import { mkdirSync } from "node:fs";
import { join } from "node:path";
import type { NodeExecutionRequest } from "./request.js";
import { getNodeLogger, type SdkLogger } from "./logging.js";

export class ExecutionContext {
  private _request: NodeExecutionRequest | null;
  private _outputDir: string;
  private _logger: SdkLogger;
  private _tokenUsage: Record<string, number>;
  private _metadata: Record<string, unknown>;
  private _downloadsDir: string | null;

  constructor(opts: {
    request?: NodeExecutionRequest | null;
    outputDir?: string;
    runId?: string;
    nodeId?: string;
  } = {}) {
    const { request = null, outputDir, runId, nodeId } = opts;

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

  outputPath(filename: string): string {
    return join(this._outputDir, filename);
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
