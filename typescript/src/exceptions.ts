/**
 * Base error class for all node execution errors with error code and details.
 */
export class NodeExecutionError extends Error {
  readonly errorCode: string;
  readonly details: Record<string, unknown>;

  /**
   * Creates a new NodeExecutionError.
   * @param message - Error message
   * @param options - Error options including error code and details
   */
  constructor(
    message: string,
    { errorCode = "EXECUTION_ERROR", details }: {
      errorCode?: string;
      details?: Record<string, unknown>;
    } = {},
  ) {
    super(message);
    this.name = "NodeExecutionError";
    this.errorCode = errorCode;
    this.details = details ?? {};
  }

  /**
   * Converts error to dictionary for serialization.
   * @returns Dictionary with error_code, message, and details
   */
  toDict(): Record<string, unknown> {
    return {
      error_code: this.errorCode,
      message: this.message,
      details: this.details,
    };
  }
}

/**
 * Error thrown when node execution exceeds timeout limit.
 */
export class NodeTimeoutError extends NodeExecutionError {
  readonly timeoutSeconds: number;

  /**
   * Creates a new NodeTimeoutError.
   * @param timeoutSeconds - Timeout duration in seconds
   * @param options - Additional error details
   */
  constructor(
    timeoutSeconds: number,
    { details }: { details?: Record<string, unknown> } = {},
  ) {
    super(`Node execution timed out after ${timeoutSeconds}s`, {
      errorCode: "TIMEOUT",
      details: details ?? { timeout_seconds: timeoutSeconds },
    });
    this.name = "NodeTimeoutError";
    this.timeoutSeconds = timeoutSeconds;
  }
}

/**
 * Error thrown when node input validation fails.
 */
export class NodeValidationError extends NodeExecutionError {
  readonly errors: Record<string, unknown>[];

  /**
   * Creates a new NodeValidationError.
   * @param message - Error message
   * @param options - Validation errors and additional details
   */
  constructor(
    message: string,
    { errors, details }: {
      errors?: Record<string, unknown>[];
      details?: Record<string, unknown>;
    } = {},
  ) {
    super(message, { errorCode: "VALIDATION_ERROR", details });
    this.name = "NodeValidationError";
    this.errors = errors ?? [];
  }

  /**
   * Converts error to dictionary for serialization.
   * @returns Dictionary with validation errors
   */
  toDict(): Record<string, unknown> {
    return { ...super.toDict(), errors: this.errors };
  }
}

/**
 * Error thrown when node output validation fails.
 */
export class NodeOutputValidationError extends NodeExecutionError {
  readonly errors: Record<string, unknown>[];

  /**
   * Creates a new NodeOutputValidationError.
   * @param message - Error message
   * @param options - Validation errors and additional details
   */
  constructor(
    message: string,
    { errors, details }: {
      errors?: Record<string, unknown>[];
      details?: Record<string, unknown>;
    } = {},
  ) {
    super(message, { errorCode: "OUTPUT_VALIDATION_ERROR", details });
    this.name = "NodeOutputValidationError";
    this.errors = errors ?? [];
  }

  /**
   * Converts error to dictionary for serialization.
   * @returns Dictionary with validation errors
   */
  toDict(): Record<string, unknown> {
    return { ...super.toDict(), errors: this.errors };
  }
}

/**
 * Error thrown when file I/O operations fail.
 */
export class NodeIOError extends NodeExecutionError {
  readonly path: string | null;

  /**
   * Creates a new NodeIOError.
   * @param message - Error message
   * @param options - File path and additional details
   */
  constructor(
    message: string,
    { path, details }: {
      path?: string | null;
      details?: Record<string, unknown>;
    } = {},
  ) {
    const mergedDetails: Record<string, unknown> = { ...details };
    if (path) mergedDetails.path = path;
    super(message, { errorCode: "IO_ERROR", details: mergedDetails });
    this.name = "NodeIOError";
    this.path = path ?? null;
  }
}

/**
 * Error thrown when node configuration is invalid.
 */
export class NodeConfigurationError extends NodeExecutionError {
  /**
   * Creates a new NodeConfigurationError.
   * @param message - Error message
   * @param options - Additional error details
   */
  constructor(
    message: string,
    { details }: { details?: Record<string, unknown> } = {},
  ) {
    super(message, { errorCode: "CONFIGURATION_ERROR", details });
    this.name = "NodeConfigurationError";
  }
}

/**
 * Error thrown when workflow execution fails.
 */
export class WorkflowExecutionError extends NodeExecutionError {
  readonly nodeId: string | null;

  /**
   * Creates a new WorkflowExecutionError.
   * @param message - Error message
   * @param options - Node ID and additional details
   */
  constructor(
    message: string,
    { nodeId, details }: {
      nodeId?: string | null;
      details?: Record<string, unknown>;
    } = {},
  ) {
    const mergedDetails: Record<string, unknown> = { ...details };
    if (nodeId) mergedDetails.node_id = nodeId;
    super(message, { errorCode: "WORKFLOW_EXECUTION_ERROR", details: mergedDetails });
    this.name = "WorkflowExecutionError";
    this.nodeId = nodeId ?? null;
  }
}

/**
 * Error thrown when workflow validation fails.
 */
export class WorkflowValidationError extends NodeExecutionError {
  readonly errors: string[];

  /**
   * Creates a new WorkflowValidationError.
   * @param message - Error message
   * @param options - Validation errors and additional details
   */
  constructor(
    message: string,
    { errors, details }: {
      errors?: string[];
      details?: Record<string, unknown>;
    } = {},
  ) {
    super(message, { errorCode: "WORKFLOW_VALIDATION_ERROR", details });
    this.name = "WorkflowValidationError";
    this.errors = errors ?? [];
  }

  /**
   * Converts error to dictionary for serialization.
   * @returns Dictionary with validation errors
   */
  toDict(): Record<string, unknown> {
    return { ...super.toDict(), errors: this.errors };
  }
}

/**
 * Error thrown when node registration fails.
 */
export class RegistrationError extends Error {
  readonly statusCode: number;
  readonly body: Record<string, unknown>;

  /**
   * Creates a new RegistrationError.
   * @param statusCode - HTTP status code
   * @param body - Response body with error details
   */
  constructor(statusCode: number, body: Record<string, unknown>) {
    const message = body.detail?.toString() ?? body.message?.toString() ?? `Registration failed with status ${statusCode}`;
    super(message);
    this.name = "RegistrationError";
    this.statusCode = statusCode;
    this.body = body;
  }
}

/**
 * Mapping of error codes to HTTP status codes.
 */
export const ERROR_CODE_TO_HTTP_STATUS: Record<string, number> = {
  EXECUTION_ERROR: 500,
  TIMEOUT: 408,
  VALIDATION_ERROR: 422,
  OUTPUT_VALIDATION_ERROR: 422,
  IO_ERROR: 500,
  CONFIGURATION_ERROR: 500,
  WORKFLOW_EXECUTION_ERROR: 500,
  WORKFLOW_VALIDATION_ERROR: 422,
};

/**
 * Converts a NodeExecutionError to its HTTP status code.
 * @param exc - Node execution error
 * @returns HTTP status code (500 default)
 */
export function getHttpStatusForError(exc: NodeExecutionError): number {
  return ERROR_CODE_TO_HTTP_STATUS[exc.errorCode] ?? 500;
}
