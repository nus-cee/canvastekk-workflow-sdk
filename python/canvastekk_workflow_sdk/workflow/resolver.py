"""
Input Resolver

Resolves a node's inputs from static params + incoming edge outputs.
Supports dot-notation traversal for nested output extraction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canvastekk_workflow_sdk.workflow.models import ResolutionStrategy

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.workflow.models import WorkflowSpec


def resolve_inputs(
    node_id: str,
    spec: WorkflowSpec,
    node_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Resolve a node's inputs from static params + incoming edge outputs.

    Args:
        node_id: The target node instance ID.
        spec: The workflow spec (contains nodes and edges).
        node_outputs: Map of node_id → outputs dict from already-executed nodes.

    Returns:
        Merged inputs dict ready for execution.
    """
    node = next(n for n in spec.nodes if n.id == node_id)
    resolved: dict[str, Any] = dict(node.inputs)

    incoming = [e for e in spec.edges if e.to_node == node_id]
    for edge in incoming:
        source_outputs = node_outputs.get(edge.from_node, {})
        value = _resolve_output(
            source_outputs, edge.from_output, edge.resolution_strategy
        )
        if edge.to_input:
            resolved[edge.to_input] = value
        elif isinstance(value, dict):
            resolved.update(value)

    return resolved


def _resolve_output(
    source_outputs: dict[str, Any],
    from_output: str,
    strategy: ResolutionStrategy,
) -> Any:
    """Extract a value from source outputs using the resolution strategy.

    Args:
        source_outputs: The source node's output dict.
        from_output: Key or dot-path to extract.
        strategy: How to resolve the key.

    Returns:
        The extracted value.

    Raises:
        KeyError: If the key/path cannot be resolved.
    """
    if not from_output:
        return source_outputs

    if strategy == ResolutionStrategy.FLAT:
        return source_outputs[from_output]

    if strategy == ResolutionStrategy.DOT_PATH:
        return _walk_dot_path(source_outputs, from_output)

    # AUTO: flat first, dot-path fallback
    if from_output in source_outputs:
        return source_outputs[from_output]
    if "." in from_output:
        return _walk_dot_path(source_outputs, from_output)
    raise KeyError(f"Cannot resolve from_output '{from_output}' with AUTO strategy")


def _walk_dot_path(data: dict[str, Any], path: str) -> Any:
    """Walk a nested dict using dot-separated path segments.

    Example: ``"data.url"`` → ``data["data"]["url"]``
    """
    current: Any = data
    for segment in path.split("."):
        if not segment:
            raise KeyError(f"Invalid dot-path '{path}' (empty segment)")
        if not isinstance(current, dict):
            raise KeyError(
                f"Cannot walk dot-path '{path}': segment '{segment}' hits non-dict"
            )
        if segment not in current:
            raise KeyError(f"Dot-path '{path}': segment '{segment}' not found")
        current = current[segment]
    return current
