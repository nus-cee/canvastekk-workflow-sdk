"""
Node Execution Request Model

This is the payload sent to a node's /execute endpoint.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class NodeExecutionRequest(BaseModel):
    """
    Request payload for node execution.

    Sent by the orchestrator to a node's POST /execute endpoint.
    ``run_id``/``node_id`` are constrained to a slug charset and may not
    contain ``..`` (defense against path construction attacks — the ids
    flow into ``/tmp/{run_id}/{node_id}`` output paths).
    """

    _SLUG_RE = r"^[A-Za-z0-9._-]+$"

    run_id: str = Field(
        pattern=_SLUG_RE,
        description="Workflow run identifier (slug: letters, digits, dot, underscore, hyphen)",
    )
    node_id: str = Field(
        pattern=_SLUG_RE,
        description="Node instance ID in workflow (slug: letters, digits, dot, underscore, hyphen)",
    )

    @model_validator(mode="after")
    def _reject_dot_segments(self) -> NodeExecutionRequest:
        """Reject `..` substrings and dot-only values.

        The slug charset alone still permits `..` and `.` segments; these
        flow into ``/tmp/{run_id}/{node_id}`` path construction and would
        escape the run sandbox (DA-1711 3.1).
        """
        for field_name in ("run_id", "node_id"):
            value = getattr(self, field_name)
            if ".." in value or value.strip(".") != value or not value.strip("."):
                raise ValueError(
                    f"{field_name} must not contain dot segments (got {value!r})"
                )
        return self
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Input values (may include signed URLs for file access)",
    )
    callback_url: str | None = Field(
        default=None,
        description="For async execution - URL to POST result to when complete",
    )
    output_upload_url: dict[str, str] | None = Field(
        default=None,
        description="Mapping of output field name to pre-signed S3 PUT URL for uploading output files",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "run_id": "run-abc123",
                    "node_id": "echo-1",
                    "inputs": {"message": "Hello, World!"},
                    "callback_url": None,
                    "output_upload_url": None,
                }
            ]
        }
    }
