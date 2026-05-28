import { z } from "zod";

export const NodeExecutionResponseSchema = z.object({
  execution_id: z.string(),
  status: z.union([z.literal("pass"), z.literal("fail")]),
  outputs: z.record(z.unknown()).nullable().default(null),
  token_usage: z.number().min(0.0).default(0.0),
  duration_ms: z.number().int().min(0).default(0),
  error: z.string().nullable().default(null),
  error_type: z.string().nullable().default(null),
  error_code: z.string().nullable().default(null),
});

/** Node execution response. */
export type NodeExecutionResponse = z.infer<typeof NodeExecutionResponseSchema>;

function createSuccessResponse(
  executionId: string,
  outputs: Record<string, unknown>,
  durationMs = 0,
  tokenUsage = 0.0,
): NodeExecutionResponse {
  return {
    execution_id: executionId,
    status: "pass",
    outputs,
    duration_ms: durationMs,
    token_usage: tokenUsage,
    error: null,
    error_type: null,
    error_code: null,
  };
}

function createFailureResponse(
  executionId: string,
  error: string,
  errorType: string | null = null,
  durationMs = 0,
  errorCode: string | null = null,
): NodeExecutionResponse {
  return {
    execution_id: executionId,
    status: "fail",
    outputs: null,
    error,
    error_type: errorType,
    duration_ms: durationMs,
    error_code: errorCode,
    token_usage: 0.0,
  };
}

export const NodeExecutionResponseFactory = {
  success: createSuccessResponse,
  failure: createFailureResponse,
};

export const HealthResponseSchema = z.object({
  status: z.union([
    z.literal("healthy"),
    z.literal("unhealthy"),
    z.literal("degraded"),
  ]),
  node_id: z.string(),
  version: z.string(),
  checks: z.record(z.boolean()).default({}),
});

/** Node health check response. */
export type HealthResponse = z.infer<typeof HealthResponseSchema>;
