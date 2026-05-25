"""Tests for workflow runner, executor, resolver, and level computation."""

import pytest

from canvastekk_workflow_sdk import BaseNode, ExecutionContext, NodeDefinition
from canvastekk_workflow_sdk.workflow.executor import InProcessExecutor
from canvastekk_workflow_sdk.workflow.level import compute_levels
from canvastekk_workflow_sdk.workflow.models import (
    ResolutionStrategy,
    WorkflowEdge,
    WorkflowNode,
    WorkflowSpec,
)
from canvastekk_workflow_sdk.workflow.resolver import _resolve_output, _walk_dot_path, resolve_inputs
from canvastekk_workflow_sdk.workflow.runner import ErrorPolicy, WorkflowRunner, WorkflowRunResult


class TestResolverFlatStrategy:
    def test_flat_key_resolution(self) -> None:
        source_outputs = {"message": "hello", "count": 5}
        result = _resolve_output(source_outputs, "message", ResolutionStrategy.FLAT)
        assert result == "hello"

    def test_flat_key_not_found_raises(self) -> None:
        source_outputs = {"message": "hello"}
        with pytest.raises(KeyError):
            _resolve_output(source_outputs, "missing", ResolutionStrategy.FLAT)


class TestResolverDotPathStrategy:
    def test_dot_notation_resolution(self) -> None:
        source_outputs = {"data": {"nested": {"value": 42}}}
        result = _resolve_output(source_outputs, "data.nested.value", ResolutionStrategy.DOT_PATH)
        assert result == 42

    def test_dot_path_partial_nesting(self) -> None:
        source_outputs = {"user": {"name": "Alice", "age": 30}}
        result = _resolve_output(source_outputs, "user.name", ResolutionStrategy.DOT_PATH)
        assert result == "Alice"

    def test_dot_path_not_found_raises(self) -> None:
        source_outputs = {"data": {"nested": {"value": 42}}}
        with pytest.raises(KeyError):
            _resolve_output(source_outputs, "data.missing.field", ResolutionStrategy.DOT_PATH)


class TestResolverAutoStrategy:
    def test_auto_flat_first(self) -> None:
        source_outputs = {"message": "hello", "data": {"value": 42}}
        result = _resolve_output(source_outputs, "message", ResolutionStrategy.AUTO)
        assert result == "hello"

    def test_auto_dot_fallback(self) -> None:
        source_outputs = {"data": {"value": 42}}
        result = _resolve_output(source_outputs, "data.value", ResolutionStrategy.AUTO)
        assert result == 42

    def test_auto_key_not_in_outputs_raises(self) -> None:
        source_outputs = {"message": "hello"}
        with pytest.raises(KeyError, match="Cannot resolve from_output"):
            _resolve_output(source_outputs, "missing", ResolutionStrategy.AUTO)


class TestResolveInputs:
    def test_static_inputs_used(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0", inputs={"threshold": 0.5}),
            ],
            edges=[],
        )
        node_outputs = {}

        result = resolve_inputs("node1", spec, node_outputs)
        assert result == {"threshold": 0.5}

    def test_static_inputs_merged_with_edge_inputs(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0", inputs={"threshold": 0.5}),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="node1", from_output="file", to_input="input_file"),
            ],
        )
        node_outputs = {"start": {"file": "/data/input.ply"}}

        result = resolve_inputs("node1", spec, node_outputs)
        assert result == {"threshold": 0.5, "input_file": "/data/input.ply"}

    def test_edge_overwrites_static_input(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0", inputs={"file": "/static.txt"}),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="node1", from_output="file", to_input="file"),
            ],
        )
        node_outputs = {"start": {"file": "/dynamic.ply"}}

        result = resolve_inputs("node1", spec, node_outputs)
        assert result == {"file": "/dynamic.ply"}

    def test_multiple_incoming_edges_merged(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0"),
                WorkflowNode(id="node2", slug="echo-v1.0.0"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="node1", from_output="file1", to_input="input1"),
                WorkflowEdge(from_node="start", to_node="node1", from_output="file2", to_input="input2"),
            ],
        )
        node_outputs = {"start": {"file1": "a.ply", "file2": "b.ply"}}

        result = resolve_inputs("node1", spec, node_outputs)
        assert result == {"input1": "a.ply", "input2": "b.ply"}

    def test_empty_from_output_returns_full_outputs(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="node1", slug="echo-v1.0.0"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="node1", from_output="", to_input=""),
            ],
        )
        node_outputs = {"start": {"file": "data.ply", "count": 5}}

        result = resolve_inputs("node1", spec, node_outputs)
        assert result == {"file": "data.ply", "count": 5}


class TestWalkDotPath:
    def test_walk_simple_path(self) -> None:
        data = {"user": {"name": "Alice"}}
        result = _walk_dot_path(data, "user.name")
        assert result == "Alice"

    def test_walk_deep_path(self) -> None:
        data = {"a": {"b": {"c": {"d": 42}}}}
        result = _walk_dot_path(data, "a.b.c.d")
        assert result == 42

    def test_walk_empty_segment_raises(self) -> None:
        data = {"a": {"b": 1}}
        with pytest.raises(KeyError, match="empty segment"):
            _walk_dot_path(data, "a..b")

    def test_walk_non_dict_raises(self) -> None:
        data = {"a": 42}
        with pytest.raises(KeyError, match="non-dict"):
            _walk_dot_path(data, "a.b")

    def test_walk_missing_key_raises(self) -> None:
        data = {"a": {"b": 1}}
        with pytest.raises(KeyError, match="not found"):
            _walk_dot_path(data, "a.missing")


class TestLevelComputation:
    def test_single_node(self) -> None:
        spec = WorkflowSpec(
            nodes=[WorkflowNode(id="node1", slug="echo-v1.0.0")],
            edges=[],
        )
        levels = compute_levels(spec)
        assert levels == [["node1"]]

    def test_linear_chain(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="A", slug="echo-v1.0.0"),
                WorkflowNode(id="B", slug="echo-v1.0.0"),
                WorkflowNode(id="C", slug="echo-v1.0.0"),
            ],
            edges=[
                WorkflowEdge(from_node="A", to_node="B"),
                WorkflowEdge(from_node="B", to_node="C"),
            ],
        )
        levels = compute_levels(spec)
        assert levels == [["A"], ["B"], ["C"]]

    def test_diamond_dag(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="A", slug="echo-v1.0.0"),
                WorkflowNode(id="B", slug="echo-v1.0.0"),
                WorkflowNode(id="C", slug="echo-v1.0.0"),
                WorkflowNode(id="D", slug="echo-v1.0.0"),
            ],
            edges=[
                WorkflowEdge(from_node="A", to_node="B"),
                WorkflowEdge(from_node="A", to_node="C"),
                WorkflowEdge(from_node="B", to_node="D"),
                WorkflowEdge(from_node="C", to_node="D"),
            ],
        )
        levels = compute_levels(spec)
        assert levels == [["A"], ["B", "C"], ["D"]]

    def test_empty_spec(self) -> None:
        spec = WorkflowSpec(nodes=[], edges=[])
        levels = compute_levels(spec)
        assert levels == []

    def test_cycle_raises(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="A", slug="echo-v1.0.0"),
                WorkflowNode(id="B", slug="echo-v1.0.0"),
                WorkflowNode(id="C", slug="echo-v1.0.0"),
            ],
            edges=[
                WorkflowEdge(from_node="A", to_node="B"),
                WorkflowEdge(from_node="B", to_node="C"),
                WorkflowEdge(from_node="C", to_node="A"),
            ],
        )
        with pytest.raises(ValueError, match="cycle"):
            compute_levels(spec)


class TestInProcessExecutor:
    def test_executor_registration(self) -> None:
        executor = InProcessExecutor()
        node = EchoNode()
        result = executor.register("echo-v1.0.0", node)
        assert result is executor
        assert executor.has("echo-v1.0.0")

    def test_executor_has_checks_registry(self) -> None:
        executor = InProcessExecutor()
        assert executor.has("missing") is False

        executor.register("echo-v1.0.0", EchoNode())
        assert executor.has("echo-v1.0.0") is True


class TestWorkflowRunner:
    def test_linear_workflow_execution(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="echo", slug="echo-v1.0.0", inputs={"message": "hello"}),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="echo"),
                WorkflowEdge(from_node="echo", to_node="end", from_output="message", to_input="result"),
            ],
        )

        executor = InProcessExecutor()
        executor.register("echo-v1.0.0", EchoNode())
        runner = WorkflowRunner(executor)

        result = runner.run(spec)

        assert result.status == "completed"
        assert result.final_outputs == {"result": "hello"}
        assert len(result.node_results) == 3
        assert result.duration_ms >= 0

    def test_workflow_run_result_structure(self) -> None:
        result = WorkflowRunResult(
            status="completed",
            final_outputs={"value": 42},
            node_results=[],
            duration_ms=100,
        )
        assert result.status == "completed"
        assert result.final_outputs == {"value": 42}
        assert result.node_results == []
        assert result.duration_ms == 100

    def test_node_results_structure(self) -> None:
        from canvastekk_workflow_sdk.workflow.runner import NodeResult

        node_result = NodeResult(
            node_id="n1",
            slug="echo-v1.0.0",
            status="completed",
            outputs={"message": "hello"},
            duration_ms=50,
        )
        assert node_result.node_id == "n1"
        assert node_result.slug == "echo-v1.0.0"
        assert node_result.status == "completed"
        assert node_result.outputs == {"message": "hello"}
        assert node_result.duration_ms == 50

    def test_error_handling_failing_node(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="fail", slug="failing-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="fail"),
                WorkflowEdge(from_node="fail", to_node="end"),
            ],
        )

        executor = InProcessExecutor()
        executor.register("failing-v1.0.0", FailingNode())
        runner = WorkflowRunner(executor)

        result = runner.run(spec, inputs={})

        assert result.status == "failed"
        failed_result = next(r for r in result.node_results if r.node_id == "fail")
        assert failed_result.status == "failed"
        assert failed_result.error is not None

    def test_error_policy_fail_fast(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="fail", slug="failing-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="fail"),
                WorkflowEdge(from_node="fail", to_node="end"),
            ],
        )

        executor = InProcessExecutor()
        executor.register("failing-v1.0.0", FailingNode())
        runner = WorkflowRunner(executor, error_policy=ErrorPolicy.FAIL_FAST)

        result = runner.run(spec, inputs={})

        assert result.status == "failed"
        fail_result = next((r for r in result.node_results if r.node_id == "fail"), None)
        assert fail_result is not None
        assert fail_result.status == "failed"

    def test_error_policy_continue(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="fail", slug="failing-v1.0.0"),
                WorkflowNode(id="skip", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="fail"),
                WorkflowEdge(from_node="start", to_node="skip"),
                WorkflowEdge(from_node="fail", to_node="end"),
                WorkflowEdge(from_node="skip", to_node="end"),
            ],
        )

        executor = InProcessExecutor()
        executor.register("failing-v1.0.0", FailingNode())
        executor.register("echo-v1.0.0", EchoNode())
        runner = WorkflowRunner(executor, error_policy=ErrorPolicy.CONTINUE)

        result = runner.run(spec, inputs={})

        assert result.status == "failed"
        skip_result = next(r for r in result.node_results if r.node_id == "skip")
        assert skip_result.status == "completed"

    def test_missing_executor_fails_node(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="missing", slug="unknown-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="missing"),
                WorkflowEdge(from_node="missing", to_node="end"),
            ],
        )

        executor = InProcessExecutor()
        runner = WorkflowRunner(executor)

        result = runner.run(spec, inputs={})

        assert result.status == "failed"
        missing_result = next(r for r in result.node_results if r.node_id == "missing")
        assert missing_result.status == "failed"
        assert "No executor registered" in missing_result.error

    def test_upstream_failure_skips_dependent_nodes(self) -> None:
        spec = WorkflowSpec(
            nodes=[
                WorkflowNode(id="start", slug="__start__"),
                WorkflowNode(id="fail", slug="failing-v1.0.0"),
                WorkflowNode(id="dependent", slug="echo-v1.0.0"),
                WorkflowNode(id="end", slug="__end__"),
            ],
            edges=[
                WorkflowEdge(from_node="start", to_node="fail"),
                WorkflowEdge(from_node="fail", to_node="dependent"),
                WorkflowEdge(from_node="dependent", to_node="end"),
            ],
        )

        executor = InProcessExecutor()
        executor.register("failing-v1.0.0", FailingNode())
        executor.register("echo-v1.0.0", EchoNode())
        runner = WorkflowRunner(executor, error_policy=ErrorPolicy.CONTINUE)

        result = runner.run(spec, inputs={})

        dependent_result = next(r for r in result.node_results if r.node_id == "dependent")
        assert dependent_result.status == "skipped"
        assert dependent_result.skipped_reason == "upstream_failed"


class EchoNode(BaseNode):
    definition = NodeDefinition(
        name="echo",
        version="1.0.0",
        title="Echo",
        description="Returns input message",
        input_schema={"type": "object"},
        output_schema={"type": "object", "properties": {"message": {"type": "string"}}},
    )

    def execute(self, inputs: dict, context: ExecutionContext) -> dict:
        return {"message": inputs.get("message", "")}


class FailingNode(BaseNode):
    definition = NodeDefinition(
        name="failing",
        version="1.0.0",
        title="Failing",
        description="Always fails",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def execute(self, inputs: dict, context: ExecutionContext) -> dict:
        raise ValueError("Intentional failure")
