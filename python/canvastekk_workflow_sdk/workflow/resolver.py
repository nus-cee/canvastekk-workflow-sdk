"""
Input Resolver

Resolves a node's inputs from static params + incoming edge outputs.
Supports dot-notation traversal for nested output extraction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.workflow.models import WorkflowDefinitionSpec


def resolve_inputs(
    node_id: str,
    spec: WorkflowDefinitionSpec,
    node_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    try:
        node = next(n for n in spec.nodes if n.id == node_id)
    except StopIteration:
        raise KeyError(f"Node '{node_id}' not found in spec") from None
    resolved: dict[str, Any] = dict(node.inputs)

    incoming = [e for e in spec.edges if e.to_node == node_id]
    for edge in incoming:
        source_outputs = node_outputs.get(edge.from_node, {})
        value = _resolve_output(source_outputs, edge.from_output)
        if edge.to_input:
            resolved[edge.to_input] = value
        elif isinstance(value, dict):
            resolved.update(value)

    return resolved


def _resolve_output(
    source_outputs: dict[str, Any],
    from_output: str,
) -> Any:
    if not from_output:
        return source_outputs

    if from_output in source_outputs:
        return source_outputs[from_output]
    if "." in from_output:
        return _walk_dot_path(source_outputs, from_output)
    raise KeyError(f"Cannot resolve from_output '{from_output}'")


def _walk_dot_path(data: dict[str, Any], path: str) -> Any:
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
