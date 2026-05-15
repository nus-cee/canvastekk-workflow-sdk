"""Tests for BaseNode class."""

from typing import Any

import pytest

from canvastekk_workflow_sdk import BaseNode, ExecutionContext, NodeDefinition, NodeExecutionRequest
from canvastekk_workflow_sdk.exceptions import (
    NodeIOError,
    NodeOutputValidationError,
    NodeTimeoutError,
)
from canvastekk_workflow_sdk.middleware import TimingMiddleware
from canvastekk_workflow_sdk.observability import MetricsCollector


class EchoNode(BaseNode):
    """Simple echo node for testing."""

    definition = NodeDefinition(
        id="echo-v1.0.0",
        name="echo",
        version="1.0.0",
        title="Echo",
        description="Returns input unchanged",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
        },
        output_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
        },
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {"message": inputs.get("message", "")}


class FailingNode(BaseNode):
    """Node that always fails for testing."""

    definition = NodeDefinition(
        id="failing-v1.0.0",
        name="failing",
        version="1.0.0",
        title="Failing",
        description="Always fails",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        raise ValueError("Intentional failure for testing")


class HealthyNode(BaseNode):
    """Node with custom health checks."""

    definition = NodeDefinition(
        id="healthy-v1.0.0",
        name="healthy",
        version="1.0.0",
        title="Healthy",
        description="Has custom health checks",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {}

    def health_check(self) -> dict[str, Any]:
        return {
            "model_loaded": True,
            "storage_accessible": True,
        }


class NodeIOErrorNode(BaseNode):
    """Node that raises NodeIOError."""

    definition = NodeDefinition(
        id="io-err-v1.0.0",
        name="io-err",
        version="1.0.0",
        title="IO Error",
        description="Raises IO error",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        raise NodeIOError("File not found", path="/tmp/missing.ply")


class NodeTimeoutErrorNode(BaseNode):
    """Node that raises NodeTimeoutError."""

    definition = NodeDefinition(
        id="timeout-err-v1.0.0",
        name="timeout-err",
        version="1.0.0",
        title="Timeout Error",
        description="Raises timeout",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        raise NodeTimeoutError(30)


class TokenReportingNode(BaseNode):
    """Node that reports token usage via context."""

    definition = NodeDefinition(
        id="token-v1.0.0",
        name="token",
        version="1.0.0",
        title="Token",
        description="Reports token usage",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        token_cost=1.0,
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        context.record_token_usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        return {"done": True}


class ValidatedNode(BaseNode):
    """Node with required input fields for validation testing."""

    definition = NodeDefinition(
        id="validated-v1.0.0",
        name="validated",
        version="1.0.0",
        title="Validated",
        description="Has required inputs",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name", "count"],
        },
        output_schema={"type": "object"},
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {"name": inputs["name"], "count": inputs["count"]}


class TestBaseNode:
    """Tests for BaseNode class."""

    def test_definition_required(self) -> None:
        """Test that subclasses must define a definition."""
        with pytest.raises(TypeError, match="must define a 'definition'"):

            class InvalidNode(BaseNode):
                def execute(self, inputs: dict, context: ExecutionContext) -> dict:
                    return {}

    def test_execute_success(self) -> None:
        """Test successful node execution."""
        node = EchoNode()
        request = NodeExecutionRequest(
            run_id="test-run",
            node_id="test-node",
            inputs={"message": "Hello, World!"},
        )
        response = node.run(request)

        assert response.status == "pass"
        assert response.outputs == {"message": "Hello, World!"}
        assert response.error is None
        assert response.error_type is None
        assert response.duration_ms >= 0
        assert response.execution_id is not None

    def test_execute_failure(self) -> None:
        """Test node execution failure."""
        node = FailingNode()
        request = NodeExecutionRequest(
            run_id="test-run",
            node_id="test-node",
            inputs={},
        )
        response = node.run(request)

        assert response.status == "fail"
        assert response.outputs is None
        assert response.error == "Intentional failure for testing"
        assert response.error_type == "ValueError"
        assert response.duration_ms >= 0

    def test_default_health_check(self) -> None:
        """Test default health check returns empty dict."""
        node = EchoNode()
        checks = node.health_check()
        assert checks == {}

    def test_custom_health_check(self) -> None:
        """Test custom health check."""
        node = HealthyNode()
        checks = node.health_check()
        assert checks == {
            "model_loaded": True,
            "storage_accessible": True,
        }

    def test_create_app(self) -> None:
        """Test that create_app returns a FastAPI instance."""
        node = EchoNode()
        app = node.create_app()
        assert app is not None
        # Check that routes exist
        routes = [route.path for route in app.routes]
        assert "/execute" in routes
        assert "/health" in routes
        assert "/definition" in routes


class TestBaseNodeTypedExceptions:
    def test_io_error_response(self) -> None:
        node = NodeIOErrorNode()
        response = node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))
        assert response.status == "fail"
        assert response.error == "File not found"
        assert response.error_type == "NodeIOError"
        assert response.error_code == "IO_ERROR"

    def test_timeout_error_response(self) -> None:
        node = NodeTimeoutErrorNode()
        response = node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))
        assert response.status == "fail"
        assert "timed out" in response.error
        assert response.error_type == "NodeTimeoutError"
        assert response.error_code == "TIMEOUT"

    def test_generic_exception_no_error_code(self) -> None:
        node = FailingNode()
        response = node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))
        assert response.status == "fail"
        assert response.error_code is None

    def test_validation_error_on_missing_required(self) -> None:
        node = ValidatedNode()
        response = node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))
        assert response.status == "fail"
        assert response.error_type == "NodeValidationError"
        assert response.error_code == "VALIDATION_ERROR"

    def test_validation_passes_with_valid_inputs(self) -> None:
        node = ValidatedNode()
        response = node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={"name": "test", "count": 5}))
        assert response.status == "pass"
        assert response.outputs == {"name": "test", "count": 5}


class TestBaseNodeDynamicTokenUsage:
    def test_dynamic_token_usage_reported(self) -> None:
        node = TokenReportingNode()
        response = node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))
        assert response.status == "pass"
        assert response.token_usage == 150.0

    def test_static_token_cost_as_fallback(self) -> None:
        node = EchoNode()
        response = node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={"message": "hi"}))
        assert response.status == "pass"
        assert response.token_usage == 0.0


class TestBaseNodeMetricsIntegration:
    def test_successful_execution_records_metric(self) -> None:
        collector = MetricsCollector()
        node = EchoNode()
        node.set_metrics_collector(collector)

        node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={"message": "hi"}))

        summary = collector.get_summary()
        assert summary["total_executions"] == 1
        assert summary["pass_count"] == 1
        assert summary["fail_count"] == 0

    def test_failed_execution_records_metric(self) -> None:
        collector = MetricsCollector()
        node = FailingNode()
        node.set_metrics_collector(collector)

        node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))

        summary = collector.get_summary()
        assert summary["total_executions"] == 1
        assert summary["fail_count"] == 1

    def test_dynamic_token_usage_in_metrics(self) -> None:
        collector = MetricsCollector()
        node = TokenReportingNode()
        node.set_metrics_collector(collector)

        node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))

        summary = collector.get_summary()
        assert summary["total_token_usage"] == 150.0


class TestBaseNodeMiddlewareIntegration:
    def test_add_middleware_chaining(self) -> None:
        node = EchoNode()
        timing = TimingMiddleware()
        result = node.add_middleware(timing)
        assert result is node

    def test_timing_middleware_records(self) -> None:
        timing = TimingMiddleware()
        node = EchoNode()
        node.add_middleware(timing)

        node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={"message": "hi"}))

        assert len(timing.timings) == 1
        assert timing.timings[0]["status"] == "pass"

    def test_timing_middleware_on_error(self) -> None:
        timing = TimingMiddleware()
        node = FailingNode()
        node.add_middleware(timing)

        node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))

        assert len(timing.timings) == 1
        assert timing.timings[0]["status"] == "fail"
        assert timing.timings[0]["error_type"] == "ValueError"

    def test_hook_default_returns_none(self) -> None:
        node = EchoNode()
        assert node.hook({}) is None


class TestBaseNodeInitSubclass:
    def test_abstract_subclass_skips_validation(self) -> None:
        from abc import ABC

        class MiddleNode(BaseNode, ABC):
            pass

        assert not hasattr(MiddleNode, "definition") or MiddleNode.definition is None


class OutputValidationNode(BaseNode):
    """Node with strict output schema for validation testing."""

    definition = NodeDefinition(
        id="output-val-v1.0.0",
        name="output-val",
        version="1.0.0",
        title="Output Validation",
        description="Has strict output schema",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
        },
        output_schema={
            "type": "object",
            "properties": {
                "result": {"type": "integer"},
                "message": {"type": "string"},
            },
            "required": ["result", "message"],
        },
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        val = inputs.get("value", 0)
        return {"result": val * 2, "message": f"Doubled: {val * 2}"}


class OutputValidationErrorNode(BaseNode):
    """Node that returns invalid output type."""

    definition = NodeDefinition(
        id="output-err-v1.0.0",
        name="output-err",
        version="1.0.0",
        title="Output Error",
        description="Returns invalid output",
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        },
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {"count": "not an integer"}


class OutputMissingRequiredNode(BaseNode):
    """Node that returns missing required field."""

    definition = NodeDefinition(
        id="output-missing-v1.0.0",
        name="output-missing",
        version="1.0.0",
        title="Output Missing",
        description="Returns missing required field",
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
        },
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {"name": "John"}


class TrivialOutputSchemaNode(BaseNode):
    """Node with trivial output schema."""

    definition = NodeDefinition(
        id="trivial-v1.0.0",
        name="trivial",
        version="1.0.0",
        title="Trivial",
        description="Has trivial output schema",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {"anything": "goes"}


class TestBaseNodeOutputValidation:
    """Tests for output schema validation (Phase 1)."""

    def test_valid_output_passes_validation(self) -> None:
        """Test that valid output passes schema validation."""
        node = OutputValidationNode()
        response = node.run(
            NodeExecutionRequest(run_id="r1", node_id="n1", inputs={"value": 5})
        )
        assert response.status == "pass"
        assert response.outputs == {"result": 10, "message": "Doubled: 10"}
        assert response.error is None

    def test_invalid_output_wrong_type_raises_error(self) -> None:
        """Test that invalid output type raises NodeOutputValidationError."""
        node = OutputValidationErrorNode()
        response = node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))
        assert response.status == "fail"
        assert response.error_type == "NodeOutputValidationError"
        assert response.error_code == "OUTPUT_VALIDATION_ERROR"
        assert "output validation failed" in response.error.lower()

    def test_missing_required_output_field_raises_error(self) -> None:
        """Test that missing required output field raises NodeOutputValidationError."""
        node = OutputMissingRequiredNode()
        response = node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))
        assert response.status == "fail"
        assert response.error_type == "NodeOutputValidationError"
        assert response.error_code == "OUTPUT_VALIDATION_ERROR"
        assert "output validation failed" in response.error.lower()

    def test_trivial_output_schema_always_passes(self) -> None:
        """Test that trivial output schema {'type': 'object'} always passes."""
        node = TrivialOutputSchemaNode()
        response = node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))
        assert response.status == "pass"
        assert response.outputs == {"anything": "goes"}

    def test_output_validation_error_code(self) -> None:
        """Test that NodeOutputValidationError has correct error_code."""
        try:
            raise NodeOutputValidationError("test error")
        except NodeOutputValidationError as e:
            assert e.error_code == "OUTPUT_VALIDATION_ERROR"

    def test_output_validation_error_in_response(self) -> None:
        """Test that error_type is correctly set in response."""
        node = OutputValidationErrorNode()
        response = node.run(NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}))
        assert response.status == "fail"
        assert response.error_type == "NodeOutputValidationError"
        assert response.error is not None
