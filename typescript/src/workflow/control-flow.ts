import type { ExecutionContext } from "../context.js";

/** Handler function for control flow nodes. */
type ControlFlowHandler = (inputs: Record<string, unknown>, context: ExecutionContext) => Record<string, unknown>;

/** Built-in control flow handlers. */
export const CONTROL_FLOW_HANDLERS: Record<string, ControlFlowHandler> = {
  __start__: (inputs) => ({ ...inputs }),
  __end__: (inputs) => ({ ...inputs }),
};
