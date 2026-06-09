import { z } from "zod";
import { NodeValidationError } from "./exceptions.js";

const SLUG_PATTERN = /^[a-z]([a-z0-9-]*[a-z0-9])?$/;
const SEMVER_PATTERN = /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$/;

export const ColorPresetSchema = z.union([
  z.literal("purple"),
  z.literal("red"),
  z.literal("gray"),
  z.literal("cyan"),
  z.literal("emerald"),
  z.literal("orange"),
  z.literal("amber"),
  z.literal("sky"),
  z.literal("violet"),
  z.literal("teal"),
  z.literal("indigo"),
  z.literal("slate"),
  z.literal("blue"),
  z.literal("green"),
  z.literal("pink"),
  z.literal("yellow"),
  z.literal("rose"),
  z.literal("lime"),
  z.literal("fuchsia"),
  z.literal("emerald-light"),
  z.literal("indigo-light"),
  z.literal("slate-light"),
  z.literal("red-dark"),
  z.literal("sky-dark"),
  z.literal("teal-dark"),
  z.literal("emerald-dark"),
]);

/** Color preset for node UI styling. */
export type ColorPreset = z.infer<typeof ColorPresetSchema>;

export const WorkflowNodeStylesSchema = z.object({
  icon: z.string().nullable().default(null),
  color: ColorPresetSchema.nullable().default(null),
});

export type WorkflowNodeStyles = z.infer<typeof WorkflowNodeStylesSchema>;
export type NodeStyles = WorkflowNodeStyles;
export const NodeStylesSchema = WorkflowNodeStylesSchema;

export const RetryConfigSchema = z.object({
  max_attempts: z.number().int().min(1).default(1),
  initial_delay_ms: z.number().int().min(0).default(1000),
  backoff_multiplier: z.number().min(1.0).default(2.0),
  max_delay_ms: z.number().int().min(0).default(30000),
});

/** Retry configuration with exponential backoff. */
export type RetryConfig = z.infer<typeof RetryConfigSchema>;

export const WorkflowNodeRoleSchema = z.enum(["start", "end", "error_gate", "operation"]).default("operation");

export type WorkflowNodeRole = z.infer<typeof WorkflowNodeRoleSchema>;
export type NodeRole = WorkflowNodeRole;
export const NodeRoleSchema = WorkflowNodeRoleSchema;

function validateFileFieldFormats(
  schema: Record<string, unknown>,
): void {
  const properties = (schema.properties ?? {}) as Record<
    string,
    Record<string, unknown>
  >;
  for (const [name, propSchema] of Object.entries(properties)) {
    const fieldFormat = propSchema.format as string | undefined;
    const fieldType = propSchema.type as string | undefined;

    if (fieldFormat === "binary") {
      throw new Error(
        `Field '${name}' uses format 'binary' which is no longer supported. Use format 'file' instead. (See DA-894 migration guide.)`,
      );
    }

    if (fieldFormat === "file" && fieldType !== "string") {
      throw new Error(
        `Field '${name}' has format 'file' but type is '${fieldType}'. File fields must have type 'string'.`,
      );
    }
  }
}

export const WorkflowNodeManifestSchema = z
  .object({
    id: z.unknown().optional(),
    name: z.string().refine((v) => SLUG_PATTERN.test(v), (v) => ({
      message: `Node name must be a lowercase slug (alphanumeric and hyphens only, no leading/trailing hyphens). Got: '${v}'`,
    })),
    version: z.string().refine((v) => SEMVER_PATTERN.test(v), (v) => ({
      message: `Node version must be semantic version (X.Y.Z). Got: '${v}'`,
    })),
    title: z.string(),
    description: z.string(),
    input_schema: z.record(z.unknown()),
    output_schema: z.record(z.unknown()),
    token_cost: z.number().min(0.0).default(0.0),
    default_retry: RetryConfigSchema.default(RetryConfigSchema.parse({})),
    category: z.string().default("utility"),
    timeout_seconds: z.number().int().min(1).default(30),
    role: WorkflowNodeRoleSchema,
    styles: WorkflowNodeStylesSchema.nullable().default(null),
  })
  .transform((data, ctx) => {
    if (data.id !== undefined) {
      console.warn(
        `Providing 'id' manually is deprecated. Auto-derived '${data.name}-v${data.version}' will be used.`,
      );
    }
    const { id: _id, ...rest } = data;

    try {
      validateFileFieldFormats(rest.input_schema as Record<string, unknown>);
      validateFileFieldFormats(rest.output_schema as Record<string, unknown>);
    } catch (e) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: (e as Error).message,
      });
      return z.NEVER;
    }

    return rest;
  });

/** Complete node manifest including metadata, schemas, and configuration. */
export type WorkflowNodeManifest = z.infer<typeof WorkflowNodeManifestSchema>;

export type WorkflowNodeDefinition = WorkflowNodeManifest;

export type NodeDefinition = WorkflowNodeManifest;

export function getNodeId(def: Pick<WorkflowNodeManifest, "name" | "version">): string {
  return `${def.name}-v${def.version}`;
}

/**
 * Extracts the names of file input fields from a node's input schema.
 *
 * File fields are identified by `format: "file"` in their JSON Schema definition.
 *
 * @param def - Node definition to inspect
 * @returns Array of field names that have `format: "file"`
 */
export function getFileInputFields(def: WorkflowNodeManifest): string[] {
  const properties = ((def.input_schema as Record<string, unknown>)?.properties ?? {}) as Record<
    string,
    Record<string, unknown>
  >;
  return Object.entries(properties)
    .filter(([, schema]) => schema.format === "file")
    .map(([name]) => name);
}

/**
 * Extracts the names of file output fields from a node's output schema.
 *
 * File fields are identified by `format: "file"` in their JSON Schema definition.
 *
 * @param def - Node definition to inspect
 * @returns Array of field names that have `format: "file"`
 */
export function getFileOutputFields(def: WorkflowNodeManifest): string[] {
  const properties = ((def.output_schema as Record<string, unknown>)?.properties ?? {}) as Record<
    string,
    Record<string, unknown>
  >;
  return Object.entries(properties)
    .filter(([, schema]) => schema.format === "file")
    .map(([name]) => name);
}

/**
 * Validates a downloaded file against schema constraints.
 *
 * Checks the file extension against `x-accept` (allowed extensions)
 * and the file size against `x-maxSizeBytes` (maximum size in bytes).
 *
 * @param def - Node definition containing the input schema
 * @param fieldName - Name of the file input field
 * @param filePath - Local path to the downloaded file
 * @param fileSize - Size of the downloaded file in bytes
 * @throws {NodeValidationError} If file extension or size violates constraints
 */
export function validateFileInput(
  def: WorkflowNodeManifest,
  fieldName: string,
  filePath: string,
  fileSize?: number,
): void {
  const properties = ((def.input_schema as Record<string, unknown>)?.properties ?? {}) as Record<
    string,
    Record<string, unknown>
  >;
  const schema = properties[fieldName] ?? {};

  const xAccept = schema["x-accept"] as string[] | undefined;
  if (xAccept) {
    const ext = filePath.substring(filePath.lastIndexOf(".")).toLowerCase();
    const allowed = xAccept.map((e: string) => e.toLowerCase());
    if (!allowed.includes(ext)) {
      throw new NodeValidationError(
        `File extension '${ext}' is not allowed for field '${fieldName}'. Allowed extensions: ${JSON.stringify(xAccept)}`,
      );
    }
  }

  const xMaxSizeBytes = schema["x-maxSizeBytes"] as number | undefined;
  if (xMaxSizeBytes !== undefined && fileSize !== undefined) {
    if (fileSize > xMaxSizeBytes) {
      throw new NodeValidationError(
        `File size ${fileSize} bytes exceeds maximum allowed size ${xMaxSizeBytes} bytes for field '${fieldName}'`,
      );
    }
  }
}
