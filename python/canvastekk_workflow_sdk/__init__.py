"""
CanvasTEKK Workflow Node SDK

A convenience SDK for building HTTP-based workflow nodes.
Handles all boilerplate (endpoints, validation, error handling)
so node authors can focus on business logic.

Quick Start:
    from canvastekk_workflow_sdk import BaseNode, NodeDefinition, ExecutionContext

    class MyNode(BaseNode):
        definition = NodeDefinition(
            id="my-node-v1.0.0",
            name="my-node",
            version="1.0.0",
            title="My Node",
            description="Does something useful",
            input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"output": {"type": "string"}}},
        )

        def execute(self, inputs: dict, context: ExecutionContext) -> dict:
            return {"output": f"Processed: {inputs.get('input', '')}"}

    # Create FastAPI app
    app = MyNode().create_app()

Run with:
    uvicorn handler:app --port 8001

Endpoints:
    POST /execute    - Run the node
    GET /health      - Health check
    GET /manifest    - Node self-description
    GET /definition  - Deprecated, redirects to /manifest
    POST /hook       - Webhook/callback handler

Philosophy:
    The SDK is a convenience layer, not a hard dependency.
    Nodes can "eject" by copying SDK code if true independence is needed.
"""

from canvastekk_workflow_sdk.app import create_node_app
from canvastekk_workflow_sdk.base import BaseNode
from canvastekk_workflow_sdk.context import ExecutionContext
from canvastekk_workflow_sdk.contracts import (
    BaseContract,
    BoundingBox3D,
    Instance,
    InstanceSet,
    Measurement,
    MeasurementSet,
    Plane,
    PlaneSet,
    Point3D,
)
from canvastekk_workflow_sdk.definition import ColorPreset, NodeDefinition, NodeStyles, RetryConfig, export_definition
from canvastekk_workflow_sdk.exceptions import (
    NodeConfigurationError,
    NodeExecutionError,
    NodeIOError,
    NodeTimeoutError,
    NodeValidationError,
)
from canvastekk_workflow_sdk.middleware import LoggingMiddleware, NodeMiddleware, TimingMiddleware
from canvastekk_workflow_sdk.observability import ExecutionMetric, MetricsCollector, get_default_collector
from canvastekk_workflow_sdk.request import NodeExecutionRequest
from canvastekk_workflow_sdk.response import HealthResponse, NodeExecutionResponse

__all__ = [
    "BaseContract",
    "BaseNode",
    "BoundingBox3D",
    "ColorPreset",
    "ExecutionContext",
    "ExecutionMetric",
    "HealthResponse",
    "Instance",
    "InstanceSet",
    "LoggingMiddleware",
    "Measurement",
    "MeasurementSet",
    "MetricsCollector",
    "NodeConfigurationError",
    "NodeDefinition",
    "NodeExecutionError",
    "NodeIOError",
    "NodeMiddleware",
    "NodeStyles",
    "NodeExecutionRequest",
    "NodeExecutionResponse",
    "NodeTimeoutError",
    "NodeValidationError",
    "Plane",
    "PlaneSet",
    "Point3D",
    "RetryConfig",
    "TimingMiddleware",
    "create_node_app",
    "export_definition",
    "get_default_collector",
]

__version__ = "0.2.0"
