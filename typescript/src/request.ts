import { z } from "zod";

export const NodeExecutionRequestSchema = z.object({
  run_id: z.string(),
  node_id: z.string(),
  inputs: z.record(z.unknown()).default({}),
  callback_url: z.string().nullable().optional(),
  output_upload_url: z
    .union([z.record(z.string()), z.null()])
    .optional()
    .default(null),
});

/**
 * Node execution request payload sent by the workflow engine.
 *
 * Fields use snake_case for wire-format compatibility with the Python engine.
 *
 * @property run_id - Unique identifier for the workflow run
 * @property node_id - Unique identifier for this node within the run
 * @property inputs - Node input values (may include presigned URLs for file fields)
 * @property callback_url - Optional URL to post completion status
 * @property output_upload_url - Optional presigned URL(s) for uploading output files
 */
export type NodeExecutionRequest = z.infer<typeof NodeExecutionRequestSchema>;
