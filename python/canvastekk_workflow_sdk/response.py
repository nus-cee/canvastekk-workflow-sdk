"""
Node Execution Response Model

This is the response returned from a node's /execute endpoint.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class NodeExecutionResponse(BaseModel):
    """
    Response payload from node execution.

    Returned by a node's POST /execute endpoint (sync) or
    POSTed to callback_url (async).
    """

    execution_id: str = Field(description="Unique ID for this execution (for cancellation)")
    status: Literal["pass", "fail"] = Field(description="Execution result status")
    outputs: dict[str, Any] | None = Field(
        default=None,
        description="Output values (if pass)",
    )
    token_usage: float = Field(
        default=0.0,
        ge=0.0,
        description="Actual tokens consumed",
    )
    duration_ms: int = Field(
        default=0,
        ge=0,
        description="Execution time in milliseconds",
    )
    error: str | None = Field(
        default=None,
        description="Error message (if fail)",
    )
    error_type: str | None = Field(
        default=None,
        description="Error class name (if fail)",
    )
    error_code: str | None = Field(
        default=None,
        description="Structured error code (e.g., TIMEOUT, VALIDATION_ERROR)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "execution_id": "exec-xyz789",
                    "status": "pass",
                    "outputs": {"message": "Hello, World!", "timestamp": "2026-01-15T10:30:00+00:00"},
                    "token_usage": 0.0,
                    "duration_ms": 42,
                    "error": None,
                    "error_type": None,
                    "error_code": None,
                }
            ]
        }
    }

    @classmethod
    def success(
        cls,
        execution_id: str,
        outputs: dict[str, Any],
        duration_ms: int = 0,
        token_usage: float = 0.0,
    ) -> NodeExecutionResponse:
        """Create a successful response."""
        return cls(
            execution_id=execution_id,
            status="pass",
            outputs=outputs,
            duration_ms=duration_ms,
            token_usage=token_usage,
        )

    @classmethod
    def failure(
        cls,
        execution_id: str,
        error: str,
        error_type: str | None = None,
        duration_ms: int = 0,
        error_code: str | None = None,
    ) -> NodeExecutionResponse:
        """Create a failure response."""
        return cls(
            execution_id=execution_id,
            status="fail",
            outputs=None,
            error=error,
            error_type=error_type,
            duration_ms=duration_ms,
            error_code=error_code,
        )


class HealthResponse(BaseModel):
    """Response from /health endpoint."""

    status: Literal["healthy", "unhealthy", "degraded"] = Field(
        description="Health status",
    )
    node_id: str = Field(description="Node identifier with version")
    version: str = Field(description="Node version")
    checks: dict[str, bool] = Field(
        default_factory=dict,
        description="Individual health check results",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "node_id": "echo-v1.0.0",
                    "version": "1.0.0",
                    "checks": {},
                }
            ]
        }
    }
