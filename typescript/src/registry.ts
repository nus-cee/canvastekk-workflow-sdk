import { writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import type { WorkflowNodeManifest } from "./definition.js";
import { RegistrationError } from "./exceptions.js";

/** Node invocation type. */
export type InvokeType = "http" | "lambda" | "sagemaker" | "in-process";

const VALID_INVOKE_TYPES: Set<string> = new Set(["http", "lambda", "sagemaker", "in-process"]);

/** Result from node registration. */
export interface RegisterNodeResult {
  node: Record<string, unknown>;
  action?: string | null;
  revisionId?: string | null;
  previousVersion?: string | null;
  changes?: string[] | null;
}

/**
 * Gets a value from registration result with default fallback.
 * @param result - Registration result
 * @param key - Key to retrieve
 * @param defaultValue - Default value if key not found
 * @returns Value or default
 */
export function registerNodeResultGet(result: RegisterNodeResult, key: string, defaultValue?: unknown): unknown {
  return result.node[key] ?? defaultValue;
}

/**
 * Checks if a key exists in registration result.
 * @param result - Registration result
 * @param key - Key to check
 * @returns True if key exists
 */
export function registerNodeResultHas(result: RegisterNodeResult, key: string): boolean {
  return key in result.node;
}

/**
 * Builds payload for node registration.
 * @param definition - Node definition
 * @param opts - Registration options
 * @returns Registration payload dictionary
 */
export function buildRegistryPayload(
  definition: WorkflowNodeManifest,
  opts: {
    invokeType?: InvokeType;
    invokeUrl?: string;
    invokeConfig?: Record<string, unknown>;
    tags?: string[];
    constraints?: Record<string, unknown>;
    nodeStatus?: string;
  } = {},
): Record<string, unknown> {
  const {
    invokeType = "http",
    invokeUrl,
    invokeConfig,
    tags,
    constraints,
    nodeStatus = "active",
  } = opts;

  const resolvedStyles = definition.styles ?? null;

  const payload: Record<string, unknown> = {
    name: definition.name,
    label: definition.title,
    version: definition.version,
    description: definition.description,
    input_schema: definition.input_schema,
    output_schema: definition.output_schema,
    invoke_type: invokeType,
    category: definition.category,
    token_cost: definition.token_cost,
    timeout_seconds: definition.timeout_seconds,
    node_role: definition.role,
    retry: definition.default_retry,
    tags: tags ?? [],
    styles: resolvedStyles,
    node_status: nodeStatus,
  };

  if (invokeUrl !== undefined) {
    payload.invoke_url = invokeUrl;
  }
  if (invokeConfig !== undefined) {
    payload.invoke_config = invokeConfig;
  }
  if (constraints !== undefined) {
    payload.constraints = constraints;
  }

  return payload;
}

/**
 * Extracts node data from API response payload.
 * @param payload - API response payload
 * @returns Node data dictionary
 */
export function extractNodeData(payload: Record<string, unknown>): Record<string, unknown> {
  if ("node" in payload && typeof payload.node === "object" && payload.node !== null) {
    return payload.node as Record<string, unknown>;
  }
  if ("data" in payload && typeof payload.data === "object" && payload.data !== null) {
    return payload.data as Record<string, unknown>;
  }
  return payload;
}

/**
 * Registers a node with the CanvasTEKK registry.
 * @param node - Node with definition
 * @param registryUrl - Registry API URL
 * @param opts - Registration options
 * @returns Registration result
 * @throws RegistrationError if registration fails
 */
export async function registerNode(
  node: { definition: WorkflowNodeManifest },
  registryUrl: string,
  opts: {
    invokeUrl?: string;
    invokeType?: InvokeType;
    apiKey?: string;
    serviceToken?: string;
    tags?: string[];
    invokeConfig?: Record<string, unknown>;
    timeout?: number;
  } = {},
): Promise<RegisterNodeResult> {
  const {
    invokeUrl,
    invokeType = "http",
    apiKey,
    serviceToken,
    tags,
    invokeConfig,
    timeout = 30,
  } = opts;

  if (!apiKey && !serviceToken) {
    throw new Error("Either 'apiKey' or 'serviceToken' must be provided for registration.");
  }

  if (!VALID_INVOKE_TYPES.has(invokeType)) {
    throw new Error(
      `Invalid invoke_type '${invokeType}'. Must be one of: ${[...VALID_INVOKE_TYPES].sort().join(", ")}`,
    );
  }

  const manifest = buildRegistryPayload(node.definition, {
    invokeType,
    invokeUrl,
    tags,
    invokeConfig,
  });

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
  if (serviceToken) {
    headers["X-Service-Token"] = serviceToken;
  } else if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  try {
    const resp = await fetch(registryUrl, {
      method: "POST",
      body: JSON.stringify(manifest),
      headers,
      signal: AbortSignal.timeout(timeout * 1000),
    });

    if (!resp.ok) {
      const body = await resp.text().catch(() => "");
      throw new RegistrationError(resp.status, { detail: body });
    }

    const responseData = await resp.json() as Record<string, unknown>;
    const action = responseData.action as string | undefined;
    const revisionId = responseData.revision_id as string | undefined;
    const previousVersion = responseData.previous_version as string | undefined;
    const changes = responseData.changes as string[] | undefined;

    const nodeData = extractNodeData(responseData);
    return {
      node: nodeData,
      action,
      revisionId,
      previousVersion,
      changes,
    };
  } catch (err) {
    if (err instanceof RegistrationError) throw err;
    throw new RegistrationError(500, { detail: `Registration failed: ${(err as Error).message}` });
  }
}

/**
 * Exports node definition to a JSON file.
 * @param definition - Node definition
 * @param outputPath - Output file path
 * @param opts - Export options
 * @returns Output file path
 */
export function exportDefinition(
  definition: WorkflowNodeManifest,
  outputPath: string,
  opts: {
    invokeType?: InvokeType;
    invokeUrl?: string;
    nodeStatus?: string;
    tags?: string[];
    styles?: Record<string, unknown> | null;
    constraints?: Record<string, unknown>;
  } = {},
): string {
  const registryDict = buildRegistryPayload(definition, {
    invokeType: opts.invokeType,
    invokeUrl: opts.invokeUrl,
    tags: opts.tags,
    constraints: opts.constraints,
    nodeStatus: opts.nodeStatus,
  });

  if (opts.styles !== undefined && opts.styles !== null) {
    registryDict.styles = opts.styles;
  }

  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, JSON.stringify(registryDict, null, 2) + "\n");
  return outputPath;
}
