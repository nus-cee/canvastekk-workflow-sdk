"""
Node Definition Models

These models define what a node is and how it should behave.
Every compliant node must provide a NodeDefinition.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

# fmt: off
ColorPreset = Literal[
    # Standard (500→600)
    "purple", "red", "gray", "cyan", "emerald", "orange", "amber",
    "sky", "violet", "teal", "indigo", "slate", "blue", "green",
    "pink", "yellow", "rose", "lime", "fuchsia",
    # Light variants (400→500)
    "emerald-light", "indigo-light", "slate-light",
    # Dark variants (600→700)
    "red-dark", "sky-dark", "teal-dark", "emerald-dark",
]
"""Color preset for the node header gradient.

Pick a preset name and the frontend maps it to the correct Tailwind gradient.
Use the standard variant (e.g. ``"emerald"``) unless you need to distinguish
nodes within the same category, in which case use ``-light`` or ``-dark``.
"""
# fmt: on


class NodeStyles(BaseModel):
    """Presentation metadata consumed by the frontend."""

    icon: str | None = Field(
        default=None,
        description="Lucide icon name in PascalCase (e.g. 'Brain', 'GitBranch'). "
        "Any icon from the full Lucide set (1500+) is supported via dynamic imports. "
        "See https://lucide.dev/icons for the full list. "
        "Unknown names fall back to 'Box'.",
    )
    color: ColorPreset | None = Field(
        default=None,
        description="Color preset for the node header gradient. "
        "See ColorPreset type for all options (e.g. 'emerald', 'indigo-light').",
    )


class RetryConfig(BaseModel):
    """Retry configuration for node execution."""

    max_attempts: int = Field(
        default=1,
        ge=1,
        description="Total attempts (1 = no retry, 3 = 1 initial + 2 retries)",
    )
    initial_delay_ms: int = Field(
        default=1000,
        ge=0,
        description="Delay before first retry in milliseconds",
    )
    backoff_multiplier: float = Field(
        default=2.0,
        ge=1.0,
        description="Multiplier for exponential backoff",
    )
    max_delay_ms: int = Field(
        default=30000,
        ge=0,
        description="Maximum delay between retries in milliseconds",
    )


class NodeDefinition(BaseModel):
    """
    Standard definition that every node must provide.

    This is returned by the /manifest endpoint and used by:
    - Registry to store node metadata
    - Frontend to render properties panel from input_schema
    - Orchestrator to validate inputs before execution
    """

    # Identity
    id: str = Field(description="Unique identifier with version (e.g., 'segmentation-v1.2.0')")
    name: str = Field(description="Slug for routing (e.g., 'segmentation')")
    version: str = Field(description="Semantic version (e.g., '1.2.0')")
    title: str = Field(description="Human-readable title (e.g., 'Point Cloud Segmentation')")
    description: str = Field(description="What this node does")

    # Schema (JSON Schema - language agnostic)
    input_schema: dict[str, Any] = Field(
        description="JSON Schema for expected inputs",
    )
    output_schema: dict[str, Any] = Field(
        description="JSON Schema for expected outputs",
    )

    # Cost
    token_cost: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost per execution (0.0 for free nodes)",
    )

    # Retry defaults
    default_retry: RetryConfig = Field(
        default_factory=RetryConfig,
        description="Default retry policy for this node type",
    )

    # Metadata
    category: str = Field(
        default="utility",
        description="Category (e.g., 'transform', 'inference', 'utility', 'control-flow')",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        description="Maximum execution time in seconds",
    )
    is_control_flow: bool = Field(
        default=False,
        description="True for IF, Stop-Error, etc. (run in orchestrator, not HTTP)",
    )

    # Styles (optional — frontend presentation)
    styles: NodeStyles | None = Field(
        default=None,
        description="Icon and color for the workflow builder UI",
    )

    @property
    def file_input_fields(self) -> list[str]:
        """Return list of input field names that accept file uploads.

        A field is considered a file input if it has ``"format": "binary"``
        in the input_schema properties.
        """
        properties = self.input_schema.get("properties", {})
        return [name for name, schema in properties.items() if schema.get("format") == "binary"]

    @property
    def has_file_inputs(self) -> bool:
        """Return True if any input field accepts file uploads."""
        return len(self.file_input_fields) > 0

    @property
    def file_output_fields(self) -> list[str]:
        """Return list of output field names that produce files.

        A field is considered a file output if it has ``"format": "binary"``
        in the output_schema properties.
        """
        properties = self.output_schema.get("properties", {})
        return [name for name, schema in properties.items() if schema.get("format") == "binary"]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json")


def export_definition(
    definition: NodeDefinition,
    output_path: str | Path,
    *,
    invoke_type: str = "http",
    invoke_url: str | None = None,
    node_status: str = "active",
    tags: list[str] | None = None,
    styles: dict[str, Any] | None = None,
    constraints: dict[str, Any] | None = None,
) -> Path:
    """
    Export a NodeDefinition as a RegistryNodeDefinition-compatible JSON file.

    Maps SDK NodeDefinition fields to the registry schema and writes the result
    as a clean JSON file suitable for CI/CD registration via POST /registry/nodes.

    Field mapping:
        NodeDefinition.title  -> label
        NodeDefinition.default_retry -> retry

    Args:
        definition: The SDK NodeDefinition to export.
        output_path: File path to write the JSON output.
        invoke_type: Invocation type (http, lambda, sagemaker, in-process).
        invoke_url: URL/ARN for invoking the node. None for in-process nodes.
        node_status: Registry status (active, inactive, dead).
        tags: Searchable tags for the registry.
        styles: Presentation metadata (icon, color). Overrides definition.styles if provided.
        constraints: Resource/compatibility constraints (placeholder).

    Returns:
        The resolved Path where the file was written.
    """
    output_path = Path(output_path)

    # Use explicitly passed styles, fall back to definition.styles
    resolved_styles = styles
    if resolved_styles is None and definition.styles is not None:
        resolved_styles = definition.styles.model_dump(mode="json")

    registry_dict: dict[str, Any] = {
        "name": definition.name,
        "version": definition.version,
        "label": definition.title,
        "description": definition.description,
        "category": definition.category,
        "node_status": node_status,
        "input_schema": definition.input_schema,
        "output_schema": definition.output_schema,
        "invoke_type": invoke_type,
        "invoke_url": invoke_url,
        "styles": resolved_styles,
        "constraints": constraints,
        "tags": tags or [],
        "token_cost": definition.token_cost,
        "timeout_seconds": definition.timeout_seconds,
        "retry": definition.default_retry.model_dump(mode="json"),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(registry_dict, indent=2) + "\n")
    return output_path
