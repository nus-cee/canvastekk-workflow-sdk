"""Tests for workflow validation."""


from canvastekk_workflow_sdk.workflow.models import EdgeType, WorkflowEdge, WorkflowNode, WorkflowSpec
from canvastekk_workflow_sdk.workflow.validation import ValidationResult, validate


def make_linear_spec() -> WorkflowSpec:
    """Helper to create a simple start -> node -> end spec for reuse."""
    return WorkflowSpec(
        nodes=[
            WorkflowNode(id="start", slug="__start__"),
            WorkflowNode(id="node1", slug="echo-v1.0.0"),
            WorkflowNode(id="end", slug="__end__"),
        ],
        edges=[
            WorkflowEdge(from_node="start", to_node="node1"),
            WorkflowEdge(from_node="node1", to_node="end"),
        ],
    )


class TestValidationLinearGraph:
    def test_valid_linear_graph_passes(self) -> None:
        spec = make_linear_spec()
        result = validate(spec)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.orphans) == 0
        assert len(result.dead_ends) == 0

    def test_validation_result_structure(self) -> None:
        result = ValidationResult()
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.errors, list)
        assert isinstance(result.orphans, list)
        assert isinstance(result.dead_ends, list)


class TestOrphanDetection:
    def test_orphan_node_detection(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="connected", slug="echo-v1.0.0"),
                WorkflowNode(id="orphan", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="connected"),
                WorkflowEdge(from_node="connected", to_node="end"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert "orphan" in result.orphans
        assert any("Orphan node(s)" in error for error in result.errors)

    def test_multiple_orphans_detected(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="orphan1", slug="echo-v1.0.0"),
                WorkflowNode(id="orphan2", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="end"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert "orphan1" in result.orphans
        assert "orphan2" in result.orphans


class TestDeadEndDetection:
    def test_dead_end_node_detection(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="connected", slug="echo-v1.0.0"),
                WorkflowNode(id="dead_end", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="connected"),
                WorkflowEdge(from_node="start", to_node="dead_end"),
                WorkflowEdge(from_node="connected", to_node="end"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert "dead_end" in result.dead_ends
        assert any("Dead-end node(s)" in error for error in result.errors)

    def test_multiple_dead_ends_detected(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="dead1", slug="echo-v1.0.0"),
                WorkflowNode(id="dead2", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="dead1"),
                WorkflowEdge(from_node="start", to_node="dead2"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert "dead1" in result.dead_ends
        assert "dead2" in result.dead_ends


class TestCycleDetection:
    def test_cycle_detection(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="A", slug="echo-v1.0.0"),
                WorkflowNode(id="B", slug="echo-v1.0.0"),
                WorkflowNode(id="C", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="A"),
                WorkflowEdge(from_node="A", to_node="B"),
                WorkflowEdge(from_node="B", to_node="C"),
                WorkflowEdge(from_node="C", to_node="A"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert any("cycle" in error.lower() for error in result.errors)

    def test_self_loop_detected_as_cycle(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="node1"),
                WorkflowEdge(from_node="node1", to_node="node1"),
                WorkflowEdge(from_node="node1", to_node="end"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert any("cycle" in error.lower() for error in result.errors)


class TestStartEndConstraints:
    def test_multiple_start_nodes_rejected(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start1", slug="__start__"),
                WorkflowNode(id="start2", slug="__start__"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start1", to_node="end"),
                WorkflowEdge(from_node="start2", to_node="end"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert any("exactly 1 __start__" in error for error in result.errors)

    def test_no_start_node_rejected(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="node1", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="node1", to_node="end"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert any("must have a __start__" in error for error in result.errors)

    def test_no_end_node_rejected(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="node1"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert any("must have at least 1 __end__" in error for error in result.errors)

    def test_start_with_incoming_edges_rejected(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="node1", to_node="start"),
                WorkflowEdge(from_node="start", to_node="end"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert any("no incoming edges" in error for error in result.errors)

    def test_end_with_outgoing_edges_rejected(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="end", slug="__end__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="end"),
                WorkflowEdge(from_node="end", to_node="node1"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert any("no outgoing edges" in error for error in result.errors)


class TestEdgeReferenceValidation:
    def test_invalid_edge_from_node_reference(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="nonexistent", to_node="end"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert any("non-existent from_node" in error for error in result.errors)

    def test_invalid_edge_to_node_reference(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="nonexistent"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert any("non-existent to_node" in error for error in result.errors)


class TestNodeIdUniqueness:
    def test_duplicate_node_ids_rejected(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="duplicate", slug="__start__"),
                WorkflowNode(id="duplicate", slug="echo-v1.0.0"),
            ],
            edges=[],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert any("Duplicate node ID" in error for error in result.errors)

    def test_duplicate_edge_ids_rejected(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(id="same-id", from_node="start", to_node="end"),
                WorkflowEdge(id="same-id", from_node="start", to_node="end"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is False
        assert any("Duplicate edge ID" in error for error in result.errors)


class TestComplexGraphs:
    def test_diamond_graph_valid(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0"),
                WorkflowNode(id="node2", slug="echo-v1.0.0"),
                WorkflowNode(id="node3", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="node1"),
                WorkflowEdge(from_node="start", to_node="node2"),
                WorkflowEdge(from_node="node1", to_node="node3"),
                WorkflowEdge(from_node="node2", to_node="node3"),
                WorkflowEdge(from_node="node3", to_node="end"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is True

    def test_multiple_end_nodes_valid(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0"),
                WorkflowNode(id="end1", slug="__end__"),
                WorkflowNode(id="end2", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="node1"),
                WorkflowEdge(from_node="node1", to_node="end1"),
                WorkflowEdge(from_node="node1", to_node="end2"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is True

    def test_branching_conditional_edges_valid(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0"),
                WorkflowNode(id="node2", slug="echo-v1.0.0"),
                WorkflowNode(id="node3", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="node1"),
                WorkflowEdge(from_node="node1", to_node="node2", edge_type=EdgeType.CONDITIONAL, condition="value > 10"),
                WorkflowEdge(from_node="node1", to_node="node3", edge_type=EdgeType.CONDITIONAL, condition="value <= 10"),
                WorkflowEdge(from_node="node2", to_node="end"),
                WorkflowEdge(from_node="node3", to_node="end"),
            ],
        )

        result = validate(spec)

        assert result.is_valid is True
