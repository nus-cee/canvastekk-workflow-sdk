import { randomUUID } from "node:crypto";
import { mkdirSync, unlinkSync, statSync, writeFileSync } from "node:fs";
import { join, basename } from "node:path";
import AjvModule from "ajv";
const Ajv = AjvModule.default ?? AjvModule;
import type { ValidateFunction } from "ajv";
import type { NodeDefinition } from "./definition.js";
import { NodeDefinitionSchema, getFileInputFields, validateFileInput } from "./definition.js";
import { ExecutionContext } from "./context.js";
import type { NodeMiddleware } from "./middleware.js";
import { LoggingMiddleware } from "./middleware.js";
import { MetricsCollector, createExecutionMetric } from "./observability.js";
import type { NodeExecutionRequest } from "./request.js";
import { NodeExecutionResponseFactory, type NodeExecutionResponse } from "./response.js";
import {
  NodeExecutionError,
  NodeValidationError,
  NodeOutputValidationError,
  NodeIOError,
} from "./exceptions.js";
import { createNodeApp } from "./app.js";
import type { CreateNodeAppOptions } from "./app.js";

const ajv = new Ajv({ strict: false });

/**
 * Sanitizes a filename by extracting only the base name, preventing path traversal.
 * @param rawName - Raw filename that may contain directory components
 * @returns Safe basename with no directory separators
 */
function sanitizeFilename(rawName: string): string {
  return basename(rawName);
}

/**
 * Extracts a filename from a URL or Content-Disposition header.
 *
 * Tries Content-Disposition first, falls back to URL pathname,
 * then defaults to "download".
 *
 * @param url - Download URL
 * @param contentDisposition - Optional Content-Disposition header value
 * @returns Extracted filename (sanitized)
 */
function extractFilename(url: string, contentDisposition?: string | null): string {
  if (contentDisposition) {
    for (const part of contentDisposition.split(";")) {
      const trimmed = part.trim();
      if (trimmed.toLowerCase().startsWith("filename=")) {
        const raw = trimmed.split("=").slice(1).join("=").trim().replace(/^["']|["']$/g, "");
        if (raw) return sanitizeFilename(raw);
      }
    }
  }

  try {
    const parsed = new URL(url);
    const path = parsed.pathname;
    if (path) {
      const raw = path.replace(/\/$/, "").split("/").pop();
      if (raw) return sanitizeFilename(raw);
    }
  } catch {
    // ignore URL parse errors
  }

  return "download";
}

/**
 * Compiles a JSON Schema into an Ajv validation function.
 *
 * Returns null for trivial schemas (`{"type":"object"}`) to skip unnecessary validation.
 * Compiled validators are cached by Ajv internally.
 *
 * @param schema - JSON Schema object
 * @returns Validation function, or null for trivial schemas
 */
function compileSchema(schema: Record<string, unknown>): ValidateFunction | null {
  if (!schema || JSON.stringify(schema) === '{"type":"object"}') return null;
  return ajv.compile(schema);
}

/**
 * Formats Ajv validation errors into a structured, sorted array.
 *
 * Errors are sorted by instance path for deterministic output.
 *
 * @param errors - Raw Ajv error objects
 * @returns Array of { path, message, validator } objects
 */
function formatAjvErrors(errors: import("ajv").ErrorObject[]): Record<string, unknown>[] {
  return errors
    .sort((a, b) => {
      const ap = a.instancePath.split("/").filter(Boolean);
      const bp = b.instancePath.split("/").filter(Boolean);
      return ap.join("/").localeCompare(bp.join("/"));
    })
    .map((e) => ({
      path: e.instancePath.split("/").filter(Boolean),
      message: e.message ?? "validation failed",
      validator: e.keyword,
    }));
}

/**
 * Abstract base class for all CanvasTEKK workflow nodes.
 *
 * Subclasses must:
 * 1. Define a `definition` class attribute with a valid NodeDefinition
 * 2. Implement the `execute()` method
 *
 * The SDK validates the definition at construction time and auto-downloads
 * file inputs before calling `execute()`. Output validation runs after
 * `execute()` returns.
 *
 * @example
 * ```typescript
 * class EchoNode extends BaseNode {
 *   definition = {
 *     name: "echo",
 *     version: "1.0.0",
 *     title: "Echo Node",
 *     description: "Passes inputs through unchanged",
 *     input_schema: { type: "object", properties: { data: { type: "string" } } },
 *     output_schema: { type: "object", properties: { data: { type: "string" } } },
 *   };
 *
 *   execute(inputs: Record<string, unknown>, context: ExecutionContext) {
 *     return inputs;
 *   }
 * }
 * ```
 */
export abstract class BaseNode {
  abstract definition: NodeDefinition;

  private _middleware: NodeMiddleware[] = [new LoggingMiddleware()];
  private _metricsCollector: MetricsCollector = new MetricsCollector();
  private _validatedDefinition: NodeDefinition | null = null;

  constructor() {
    // Constructor-time validation replaces Python's __init_subclass__
  }

  get nodeDefinition(): NodeDefinition {
    return this.getDefinition();
  }

  get metricsCollector(): MetricsCollector {
    return this._metricsCollector;
  }

  protected getDefinition(): NodeDefinition {
    if (!this._validatedDefinition) {
      this._validatedDefinition = NodeDefinitionSchema.parse(this.definition);
    }
    return this._validatedDefinition;
  }

  addMiddleware(middleware: NodeMiddleware): this {
    this._middleware.push(middleware);
    return this;
  }

  setMetricsCollector(collector: MetricsCollector): this {
    this._metricsCollector = collector;
    return this;
  }

  abstract execute(
    inputs: Record<string, unknown>,
    context: ExecutionContext,
  ): Record<string, unknown> | Promise<Record<string, unknown>>;

  private validateInputs(inputs: Record<string, unknown>): void {
    const def = this.getDefinition();
    const validate = compileSchema(def.input_schema as Record<string, unknown>);
    if (!validate) return;

    if (!validate(inputs)) {
      const errors = formatAjvErrors(validate.errors ?? []);
      throw new NodeValidationError(
        `Input validation failed: ${errors[0]?.message ?? "unknown error"}`,
        { errors },
      );
    }
  }

  private validateOutputs(outputs: Record<string, unknown>): void {
    const def = this.getDefinition();
    const validate = compileSchema(def.output_schema as Record<string, unknown>);
    if (!validate) return;

    if (!validate(outputs)) {
      const errors = formatAjvErrors(validate.errors ?? []);
      throw new NodeOutputValidationError(
        `Output validation failed: ${errors[0]?.message ?? "unknown error"}`,
        { errors },
      );
    }
  }

  private async prepareFileInputs(
    inputs: Record<string, unknown>,
    context: ExecutionContext,
  ): Promise<Record<string, unknown>> {
    const def = this.getDefinition();
    const fileFields = getFileInputFields(def);
    const downloaded: string[] = [];

    try {
      for (const fieldName of fileFields) {
        const value = inputs[fieldName];

        if (value == null || typeof value !== "string" || !value.trim()) continue;
        if (!value.startsWith("http://") && !value.startsWith("https://")) continue;

        context.reportProgress(0.05, `Downloading ${fieldName}`);

        let localPath: string;
        try {
          const resp = await fetch(value, { redirect: "follow", signal: AbortSignal.timeout(30_000) });
          if (!resp.ok) {
            throw new NodeIOError(
              `HTTP ${resp.status} downloading file for field '${fieldName}'`,
              { path: value },
            );
          }

          const contentDisposition = resp.headers.get("content-disposition");
          const filename = `${fieldName}_${extractFilename(value, contentDisposition)}`;
          localPath = join(context.downloadsDir, filename);

          const body = resp.body;
          if (!body) {
            throw new NodeIOError(`Empty response body for field '${fieldName}'`, { path: value });
          }

          const chunks: Uint8Array[] = [];
          const reader = body.getReader();
          try {
            while (true) {
              const { done, value: chunk } = await reader.read();
              if (done) break;
              chunks.push(chunk);
            }
          } finally {
            reader.releaseLock();
          }

          const totalBytes = chunks.reduce((sum, c) => sum + c.length, 0);
          const buffer = new Uint8Array(totalBytes);
          let offset = 0;
          for (const chunk of chunks) {
            buffer.set(chunk, offset);
            offset += chunk.length;
          }
          writeFileSync(localPath, buffer);
        } catch (err) {
          if (err instanceof NodeIOError) throw err;
          throw new NodeIOError(
            `Failed to download file for field '${fieldName}': ${err}`,
            { path: value },
          );
        }

        downloaded.push(localPath);

        const fileSize = statSync(localPath).size;

        validateFileInput(def, fieldName, localPath, fileSize);

        context.metadata[fieldName] = {
          original_url: value,
          local_path: localPath,
          size_bytes: fileSize,
        };

        inputs[fieldName] = localPath;
        context.reportProgress(0.1, `Downloaded ${fieldName} (${fileSize} bytes)`);
      }
    } catch (err) {
      for (const p of downloaded) {
        try { unlinkSync(p); } catch { /* ignore cleanup errors */ }
      }
      throw err;
    }

    return inputs;
  }

  async run(request: NodeExecutionRequest): Promise<NodeExecutionResponse> {
    const executionId = randomUUID();
    const startTime = performance.now();
    const def = this.getDefinition();

    try {
      this.validateInputs(request.inputs);

      const context = new ExecutionContext({ request });
      let inputs = { ...request.inputs };

      const fileFields = getFileInputFields(def);
      if (fileFields.length > 0) {
        inputs = await this.prepareFileInputs(inputs, context);
      }

      for (const mw of this._middleware) {
        inputs = mw.onBeforeExecute(inputs, context);
      }

      const outputs = await this.execute(inputs, context);

      this.validateOutputs(outputs);

      const durationMs = Math.round(performance.now() - startTime);

      for (const mw of this._middleware) {
        mw.onAfterExecute(inputs, outputs, context, durationMs);
      }

      const tokenUsage = context.tokenUsage.total_tokens || def.token_cost;

      this._metricsCollector.record(
        createExecutionMetric({
          runId: context.runId,
          nodeId: context.nodeId,
          nodeName: def.name,
          status: "pass",
          durationMs,
          tokenUsage,
        }),
      );

      return NodeExecutionResponseFactory.success(executionId, outputs, durationMs, tokenUsage);
    } catch (err) {
      const durationMs = Math.round(performance.now() - startTime);
      this.recordError(request, err as Error, durationMs);

      if (err instanceof NodeExecutionError) {
        return NodeExecutionResponseFactory.failure(
          executionId,
          err.message,
          err.constructor.name,
          durationMs,
          err.errorCode,
        );
      }

      const error = err as Error;
      return NodeExecutionResponseFactory.failure(
        executionId,
        error.message ?? String(error),
        error.constructor?.name ?? "Error",
        durationMs,
      );
    }
  }

  private recordError(
    request: NodeExecutionRequest,
    error: Error,
    durationMs: number,
  ): void {
    const context = new ExecutionContext({ request });
    for (const mw of this._middleware) {
      mw.onError(request.inputs, error, context, durationMs);
    }

    const errorCode = (error as NodeExecutionError).errorCode ?? undefined;
    this._metricsCollector.record(
      createExecutionMetric({
        runId: request.run_id,
        nodeId: request.node_id,
        nodeName: this.getDefinition().name,
        status: "fail",
        durationMs,
        errorType: error.constructor.name,
        errorCode,
        tokenUsage: 0,
      }),
    );
  }

  healthCheck(): Record<string, boolean> {
    return {};
  }

  hook(_payload: Record<string, unknown>): Record<string, unknown> | null {
    return null;
  }

  async onStartup(): Promise<void> {
    // no-op
  }

  async onShutdown(): Promise<void> {
    // no-op
  }

  createApp(opts?: CreateNodeAppOptions): unknown {
    return createNodeApp(this, opts);
  }
}
