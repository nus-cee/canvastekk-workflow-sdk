"""
Base Node Class

The abstract base class that all nodes must inherit from.
Provides the interface for node execution.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import jsonschema

from canvastekk_workflow_sdk.context import ExecutionContext
from canvastekk_workflow_sdk.definition import NodeDefinition
from canvastekk_workflow_sdk.exceptions import (
    NodeExecutionError,
    NodeOutputValidationError,
    NodeTimeoutError,
    NodeValidationError,
)
from canvastekk_workflow_sdk.middleware import LoggingMiddleware, NodeMiddleware
from canvastekk_workflow_sdk.observability import ExecutionMetric, MetricsCollector
from canvastekk_workflow_sdk.request import NodeExecutionRequest
from canvastekk_workflow_sdk.response import NodeExecutionResponse

logger = logging.getLogger(__name__)


class BaseNode(ABC):
    """
    Abstract base class for all nodes.

    Subclasses must:
    1. Define a `definition` class attribute with NodeDefinition
    2. Implement the `execute()` method

    Example:
        class EchoNode(BaseNode):
            definition = NodeDefinition(
                id="echo-v1.0.0",
                name="echo",
                version="1.0.0",
                title="Echo",
                description="Returns input unchanged",
                input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
                output_schema={"type": "object", "properties": {"message": {"type": "string"}}},
            )

            def execute(self, inputs: dict, context: ExecutionContext) -> dict:
                return {"message": inputs.get("message", "")}
    """

    definition: NodeDefinition

    def __init__(self) -> None:
        self._middleware: list[NodeMiddleware] = [LoggingMiddleware()]
        self._metrics_collector: MetricsCollector = MetricsCollector()

    def add_middleware(self, middleware: NodeMiddleware) -> BaseNode:
        """Register a middleware instance. Returns self for chaining.

        Args:
            middleware: A NodeMiddleware implementation.

        Returns:
            self for fluent chaining.
        """
        self._middleware.append(middleware)
        return self

    def set_metrics_collector(self, collector: MetricsCollector) -> BaseNode:
        """Set a custom metrics collector. Returns self for chaining.

        Args:
            collector: A MetricsCollector instance.

        Returns:
            self for fluent chaining.
        """
        self._metrics_collector = collector
        return self

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Validate that subclasses define required attributes."""
        super().__init_subclass__(**kwargs)
        # Skip validation for abstract classes
        if ABC in cls.__bases__:
            return
        if not hasattr(cls, "definition") or cls.definition is None:
            raise TypeError(f"{cls.__name__} must define a 'definition' class attribute")

    @abstractmethod
    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        """
        Execute the node's business logic.

        This is the only method node authors need to implement.

        Args:
            inputs: Input values (already validated against input_schema).
                    File inputs are presigned GET URLs provided by the engine. Node authors download them directly.
            context: Execution context providing run_id, node_id, output_dir, logger, etc.

        Returns:
            Output dict matching output_schema. File outputs should be paths
            to files in context.output_dir (SDK will upload them).

        Raises:
            Any exception will be caught by the SDK and returned as a failure response.
        """
        ...

    def _validate_inputs(self, inputs: dict[str, Any]) -> None:
        """Validate inputs against the node's input_schema.

        Args:
            inputs: The inputs dict to validate.

        Raises:
            NodeValidationError: If inputs do not match input_schema.
        """
        schema = self.definition.input_schema
        if not schema or schema == {"type": "object"}:
            return

        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(inputs), key=lambda e: list(e.path))
        if errors:
            error_details = [
                {
                    "path": list(e.path),
                    "message": e.message,
                    "validator": e.validator,
                }
                for e in errors
            ]
            raise NodeValidationError(
                f"Input validation failed: {errors[0].message}",
                errors=error_details,
            )

    def _validate_outputs(self, outputs: dict[str, Any]) -> None:
        """Validate outputs against the node's output_schema.

        Args:
            outputs: The outputs dict to validate.

        Raises:
            NodeOutputValidationError: If outputs do not match output_schema.
        """
        schema = self.definition.output_schema
        if not schema or schema == {"type": "object"}:
            return

        validator = jsonschema.Draft7Validator(schema)
        errors = sorted(validator.iter_errors(outputs), key=lambda e: list(e.path))
        if errors:
            error_details = [
                {
                    "path": list(e.path),
                    "message": e.message,
                    "validator": e.validator,
                }
                for e in errors
            ]
            raise NodeOutputValidationError(
                f"Output validation failed: {errors[0].message}",
                errors=error_details,
            )

    def run(self, request: NodeExecutionRequest) -> NodeExecutionResponse:
        """
        Run the node with full error handling, validation, and timing.

        This is called by the HTTP endpoint handler. It:
        1. Validates inputs against input_schema
        2. Creates execution context
        3. Runs middleware on_before_execute hooks
        4. Calls execute() with timing and timeout enforcement
        5. Runs middleware on_after_execute / on_error hooks
        6. Records metrics
        7. Returns success or failure response

        Args:
            request: The execution request from orchestrator

        Returns:
            NodeExecutionResponse with pass/fail status
        """
        execution_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        try:
            self._validate_inputs(request.inputs)

            context = ExecutionContext(request)

            inputs = request.inputs
            for mw in self._middleware:
                inputs = mw.on_before_execute(inputs, context)

            outputs = self.execute(inputs, context)

            self._validate_outputs(outputs)

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            for mw in self._middleware:
                mw.on_after_execute(inputs, outputs, context, duration_ms)

            token_usage = context.token_usage.get("total_tokens") or self.definition.token_cost

            self._metrics_collector.record(
                ExecutionMetric(
                    run_id=context.run_id,
                    node_id=context.node_id,
                    node_name=self.definition.name,
                    status="pass",
                    duration_ms=duration_ms,
                    token_usage=token_usage,
                )
            )

            return NodeExecutionResponse.success(
                execution_id=execution_id,
                outputs=outputs,
                duration_ms=duration_ms,
                token_usage=token_usage,
            )

        except NodeTimeoutError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._record_error(request, e, duration_ms)
            return NodeExecutionResponse.failure(
                execution_id=execution_id,
                error=e.message,
                error_type=type(e).__name__,
                duration_ms=duration_ms,
                error_code=e.error_code,
            )

        except NodeValidationError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._record_error(request, e, duration_ms)
            return NodeExecutionResponse.failure(
                execution_id=execution_id,
                error=e.message,
                error_type=type(e).__name__,
                duration_ms=duration_ms,
                error_code=e.error_code,
            )

        except NodeOutputValidationError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._record_error(request, e, duration_ms)
            return NodeExecutionResponse.failure(
                execution_id=execution_id,
                error=e.message,
                error_type=type(e).__name__,
                duration_ms=duration_ms,
                error_code=e.error_code,
            )

        except NodeExecutionError as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._record_error(request, e, duration_ms)
            return NodeExecutionResponse.failure(
                execution_id=execution_id,
                error=e.message,
                error_type=type(e).__name__,
                duration_ms=duration_ms,
                error_code=e.error_code,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self._record_error(request, e, duration_ms)
            return NodeExecutionResponse.failure(
                execution_id=execution_id,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=duration_ms,
            )

    def _record_error(
        self,
        request: NodeExecutionRequest,
        error: Exception,
        duration_ms: int,
    ) -> None:
        context = ExecutionContext(request)
        for mw in self._middleware:
            mw.on_error(request.inputs, error, context, duration_ms)

        error_code = getattr(error, "error_code", None)
        self._metrics_collector.record(
            ExecutionMetric(
                run_id=request.run_id,
                node_id=request.node_id,
                node_name=self.definition.name,
                status="fail",
                duration_ms=duration_ms,
                error_type=type(error).__name__,
                error_code=error_code,
            )
        )

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check for this node.

        Override this method to add custom health checks (e.g., model loaded,
        storage accessible, GPU available).

        Returns:
            Dict with check names as keys and bool results as values.
        """
        return {}

    def hook(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """
        Handle webhook/callback payloads.

        Override this method to handle async completion notifications,
        progress updates, or external triggers. The default implementation
        returns None, which the /hook endpoint translates to 501 Not Implemented.

        Args:
            payload: The JSON body from the POST /hook request.

        Returns:
            A dict response to send back, or None if hooks are not supported.
        """
        return None

    async def on_startup(self) -> None:
        """
        Hook called when the FastAPI app starts up.

        Override to perform initialization (e.g., load models, warm caches,
        establish connections). Runs once at server startup.

        Default is a no-op.
        """

    async def on_shutdown(self) -> None:
        """
        Hook called when the FastAPI app shuts down.

        Override to perform cleanup (e.g., close connections, flush buffers,
        release resources). Runs once at server shutdown.

        Default is a no-op.
        """

    @asynccontextmanager
    async def _lifespan(self) -> AsyncIterator[None]:
        """FastAPI lifespan context manager wired to on_startup/on_shutdown."""
        await self.on_startup()
        try:
            yield
        finally:
            await self.on_shutdown()

    def create_app(self, **kwargs: Any) -> Any:
        """
        Create a FastAPI app with all required endpoints.

        This is a convenience method that wraps the node in an HTTP server.
        For more control, use the `create_node_app` function from app.py.

        Args:
            **kwargs: Keyword arguments passed to ``create_node_app()``
                (e.g., ``dependencies``, ``extra_routes``, FastAPI kwargs).

        Returns:
            FastAPI application instance
        """
        from canvastekk_workflow_sdk.app import create_node_app

        return create_node_app(self, **kwargs)
