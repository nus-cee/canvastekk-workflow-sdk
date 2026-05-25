"""
Structured Exception Hierarchy

Provides typed exceptions that the SDK and node authors can raise.
Each exception maps to a specific HTTP status code for consistent error handling.
"""

from __future__ import annotations

from typing import Any


class NodeExecutionError(Exception):
    """Base exception for all node execution errors."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "EXECUTION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize the error to a JSON-friendly dict.

        Returns:
            Dict with ``error_code``, ``message``, and ``details`` keys.
        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class NodeTimeoutError(NodeExecutionError):
    """Raised when node execution exceeds the configured timeout."""

    def __init__(
        self,
        timeout_seconds: int,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Node execution timed out after {timeout_seconds}s",
            error_code="TIMEOUT",
            details=details or {"timeout_seconds": timeout_seconds},
        )
        self.timeout_seconds = timeout_seconds


class NodeValidationError(NodeExecutionError):
    """Raised when input validation against JSON Schema fails."""

    def __init__(
        self,
        message: str,
        *,
        errors: list[dict[str, Any]] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            details=details or {},
        )
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        """Serialize with an additional ``errors`` list.

        Returns:
            Dict with ``error_code``, ``message``, ``details``, and ``errors``.
        """
        result = super().to_dict()
        result["errors"] = self.errors
        return result


class NodeIOError(NodeExecutionError):
    """Raised when file I/O operations fail."""

    def __init__(
        self,
        message: str,
        *,
        path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details: dict[str, Any] = details or {}
        if path:
            merged_details["path"] = path
        super().__init__(
            message,
            error_code="IO_ERROR",
            details=merged_details,
        )
        self.path = path


class NodeConfigurationError(NodeExecutionError):
    """Raised when node configuration is invalid."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="CONFIGURATION_ERROR",
            details=details or {},
        )


class WorkflowExecutionError(NodeExecutionError):
    """Raised when local workflow execution fails."""

    def __init__(
        self,
        message: str,
        *,
        node_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details: dict[str, Any] = details or {}
        if node_id:
            merged_details["node_id"] = node_id
        super().__init__(
            message,
            error_code="WORKFLOW_EXECUTION_ERROR",
            details=merged_details,
        )
        self.node_id = node_id


class WorkflowValidationError(NodeExecutionError):
    """Raised when workflow spec validation fails."""

    def __init__(
        self,
        message: str,
        *,
        errors: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="WORKFLOW_VALIDATION_ERROR",
            details=details or {},
        )
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["errors"] = self.errors
        return result


class NodeOutputValidationError(NodeExecutionError):
    """Raised when output validation against JSON Schema fails."""

    def __init__(
        self,
        message: str,
        *,
        errors: list[dict[str, Any]] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="OUTPUT_VALIDATION_ERROR",
            details=details or {},
        )
        self.errors = errors or []

    def to_dict(self) -> dict[str, Any]:
        """Serialize with an additional ``errors`` list.

        Returns:
            Dict with ``error_code``, ``message``, ``details``, and ``errors``.
        """
        result = super().to_dict()
        result["errors"] = self.errors
        return result


ERROR_CODE_TO_HTTP_STATUS: dict[str, int] = {
    "EXECUTION_ERROR": 500,
    "TIMEOUT": 408,
    "VALIDATION_ERROR": 422,
    "OUTPUT_VALIDATION_ERROR": 422,
    "IO_ERROR": 500,
    "CONFIGURATION_ERROR": 500,
    "WORKFLOW_EXECUTION_ERROR": 500,
    "WORKFLOW_VALIDATION_ERROR": 422,
}


def get_http_status_for_error(exc: NodeExecutionError) -> int:
    """Map a :class:`NodeExecutionError` to the appropriate HTTP status code.

    Args:
        exc: A structured node execution error.

    Returns:
        Integer HTTP status code (defaults to 500 for unknown error codes).
    """
    return ERROR_CODE_TO_HTTP_STATUS.get(exc.error_code, 500)
