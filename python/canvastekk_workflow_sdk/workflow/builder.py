"""
Workflow Builder

Fluent API for constructing workflow definitions with built-in START/END nodes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canvastekk_workflow_sdk.workflow.models import (
    EdgeType,
    ResolutionStrategy,
    WorkflowEdge,
    WorkflowNode,
    WorkflowSpec,
)

if TYPE_CHECKING:
    pass


class WorkflowBuilder:
    """Fluent builder for workflow definitions.

    Example::

        spec = (
            WorkflowBuilder("my-pipeline")
            .add_start("start", outputs=["point_cloud"])
            .add_node("segment", slug="segmentation-v1.0.0", inputs={"method": "dbscan"})
            .add_end("end")
            .connect("start", "segment", from_output="point_cloud", to_input="input_file")
            .connect("segment", "end", from_output="instances", to_input="result")
            .build()
        )
    """

    def __init__(self, name: str | None = None) -> None:
        self._name = name
        self._nodes: list[WorkflowNode] = []
        self._edges: list[WorkflowEdge] = []
        self._node_ids: set[str] = set()
        self._has_start = False

    def _check_duplicate(self, node_id: str) -> None:
        if node_id in self._node_ids:
            raise ValueError(f"Duplicate node ID: '{node_id}'")

    def add_start(
        self,
        node_id: str = "start",
        *,
        outputs: list[str] | dict[str, Any] | None = None,
        config_schema: dict[str, Any] | None = None,
    ) -> WorkflowBuilder:
        """Add a START node (workflow entry point). Exactly one allowed.

        Args:
            node_id: Unique instance ID. Defaults to ``"start"``.
            outputs: Field names the START node produces. If provided,
                sets ``config_schema`` with string properties for each field.
            config_schema: Override config_schema directly.

        Returns:
            self for chaining.
        """
        if self._has_start:
            raise ValueError("Workflow already has a START node. Only one is allowed.")
        self._check_duplicate(node_id)

        cs: dict[str, Any] | None = config_schema
        if cs is None and outputs is not None:
            if isinstance(outputs, list):
                props = {name: {"type": "string"} for name in outputs}
            else:
                props = outputs
            cs = {
                "type": "object",
                "properties": props,
            }

        self._nodes.append(
            WorkflowNode(
                id=node_id,
                slug="__start__",
                name="START",
                inputs={},
                **({"config_schema": cs} if cs else {}),
            )
        )
        self._node_ids.add(node_id)
        self._has_start = True
        return self

    def add_end(self, node_id: str = "end") -> WorkflowBuilder:
        """Add an END node (workflow terminal). Multiple allowed.

        Args:
            node_id: Unique instance ID. Defaults to ``"end"``.

        Returns:
            self for chaining.
        """
        self._check_duplicate(node_id)
        self._nodes.append(
            WorkflowNode(
                id=node_id,
                slug="__end__",
                name="END",
                inputs={},
            )
        )
        self._node_ids.add(node_id)
        return self

    def add_node(
        self,
        node_id: str,
        *,
        slug: str,
        name: str | None = None,
        inputs: dict[str, Any] | None = None,
        version: str | None = None,
    ) -> WorkflowBuilder:
        """Add a user node with a registry slug reference.

        Args:
            node_id: Unique instance ID within this workflow.
            slug: Node type slug from the registry (e.g. ``"segmentation-v1.0.0"``).
            name: Optional display label.
            inputs: Static input parameter values.
            version: Pinned node version.

        Returns:
            self for chaining.
        """
        if slug in ("__start__", "__end__"):
            raise ValueError(
                f"Cannot use reserved slug '{slug}'. Use add_start() or add_end() instead."
            )
        self._check_duplicate(node_id)
        self._nodes.append(
            WorkflowNode(
                id=node_id,
                slug=slug,
                name=name,
                inputs=inputs or {},
                version=version,
            )
        )
        self._node_ids.add(node_id)
        return self

    def connect(
        self,
        from_node: str,
        to_node: str,
        *,
        from_output: str = "",
        to_input: str = "",
        edge_type: EdgeType = EdgeType.DEFAULT,
        resolution_strategy: ResolutionStrategy = ResolutionStrategy.AUTO,
        condition: str | None = None,
    ) -> WorkflowBuilder:
        """Add an edge connecting two nodes.

        Args:
            from_node: Source node instance ID.
            to_node: Target node instance ID.
            from_output: Output field from source node (supports dot-notation).
            to_input: Input field name on target node.
            edge_type: Routing type (default, success, failure, conditional).
            resolution_strategy: How to resolve ``from_output``.
            condition: CEL expression (required when ``edge_type=CONDITIONAL``).

        Returns:
            self for chaining.
        """
        if from_node not in self._node_ids:
            raise ValueError(f"Unknown source node: '{from_node}'")
        if to_node not in self._node_ids:
            raise ValueError(f"Unknown target node: '{to_node}'")

        self._edges.append(
            WorkflowEdge(
                from_node=from_node,
                to_node=to_node,
                from_output=from_output,
                to_input=to_input,
                edge_type=edge_type,
                resolution_strategy=resolution_strategy,
                condition=condition,
            )
        )
        return self

    def build(self, *, validate: bool = True) -> WorkflowSpec:
        """Build the workflow spec.

        Args:
            validate: If True, validate the graph before returning.

        Returns:
            A validated ``WorkflowSpec``.

        Raises:
            WorkflowValidationError: If validation fails.
        """
        from canvastekk_workflow_sdk.workflow.validation import validate as validate_graph

        spec = WorkflowSpec(
            name=self._name,
            nodes=list(self._nodes),
            edges=list(self._edges),
        )

        if validate:
            validate_graph(spec)

        return spec
