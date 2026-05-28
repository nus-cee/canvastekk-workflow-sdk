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

/** Node execution request payload. */
export type NodeExecutionRequest = z.infer<typeof NodeExecutionRequestSchema>;
