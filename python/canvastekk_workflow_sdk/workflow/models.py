"""
Workflow Models

Engine-compatible Pydantic models matching the CanvasTEKK Workflow Engine's
``SaveWorkflowRequest.spec`` schema. ``WorkflowSpec.model_dump(mode="json")``
produces JSON directly POSTable to ``/api/workflows/definitions``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EdgeType(StrEnum):
    """When an edge fires relative to source node execution outcome.

    Matches engine's ``EdgeType`` for routing semantics.
    """

    DEFAULT = "default"
    SUCCESS = "success"
    FAILURE = "failure"
    CONDITIONAL = "conditional"


class ResolutionStrategy(StrEnum):
    """How an edge's ``from_output`` is resolved against source node outputs.

    Matches engine's ``ResolutionStrategy``.
    """

    AUTO = "auto"
    FLAT = "flat"
    DOT_PATH = "dot_path"


class WorkflowEdge(BaseModel):
    """An edge connecting two nodes in a workflow graph.

    Uses engine-compatible field names (``from_node``, ``to_node``).
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    from_node: str = Field(description="Source node instance ID")
    to_node: str = Field(description="Target node instance ID")
    from_output: str = Field(default="", description="Output field from source (supports dot-notation)")
    to_input: str = Field(default="", description="Input field name on target node")
    edge_type: EdgeType = Field(default=EdgeType.DEFAULT, description="Routing type")
    resolution_strategy: ResolutionStrategy = Field(
        default=ResolutionStrategy.AUTO,
        description="How to resolve from_output against source outputs",
    )
    condition: str | None = Field(default=None, description="CEL expression for conditional edges")


class WorkflowNode(BaseModel):
    """A node instance placed into a workflow definition.

    Uses engine-compatible field names. Outputs are NOT stored here —
    they flow through edges at runtime.
    """

    id: str = Field(description="Unique node instance ID within the workflow")
    slug: str = Field(
        description="Node type slug from registry (e.g. '__start__', 'segmentation-v1.0.0')",
    )
    version: str | None = Field(default=None, description="Pinned node version")
    name: str | None = Field(default=None, description="Display label")
    x: float | None = Field(default=None, description="Canvas X coordinate")
    y: float | None = Field(default=None, description="Canvas Y coordinate")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Static input values")


class WorkflowSpec(BaseModel):
    """Complete workflow specification as a directed acyclic graph.

    ``model_dump(mode="json")`` produces JSON compatible with the engine's
    ``SaveWorkflowRequest.spec`` schema.
    """

    name: str | None = Field(default=None, description="Workflow display name")
    nodes: list[WorkflowNode] = Field(description="All nodes in the workflow")
    edges: list[WorkflowEdge] = Field(description="All edges connecting nodes")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow metadata (e.g. {'version': '1.0.0'})",
    )
