"""
Node Execution Request Model

This is the payload sent to a node's /execute endpoint.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NodeExecutionRequest(BaseModel):
    """
    Request payload for node execution.

    Sent by the orchestrator to a node's POST /execute endpoint.
    """

    run_id: str = Field(description="Workflow run identifier")
    node_id: str = Field(description="Node instance ID in workflow")
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
