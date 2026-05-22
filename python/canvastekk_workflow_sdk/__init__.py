"""
CanvasTEKK Workflow Node SDK

A convenience SDK for building HTTP-based workflow nodes.
Handles all boilerplate (endpoints, validation, error handling)
so node authors can focus on business logic.

Quick Start:
    from canvastekk_workflow_sdk import BaseNode, NodeDefinition, ExecutionContext

    class MyNode(BaseNode):
        definition = NodeDefinition(
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
from canvastekk_workflow_sdk.auth import NodeAuth
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
    NodeOutputValidationError,
    NodeTimeoutError,
    NodeValidationError,
)
from canvastekk_workflow_sdk.logging import StructuredJsonFormatter, configure_logging, get_node_logger
from canvastekk_workflow_sdk.middleware import LoggingMiddleware, NodeMiddleware, SDKVersionMiddleware, TimingMiddleware
from canvastekk_workflow_sdk.observability import ExecutionMetric, MetricsCollector
from canvastekk_workflow_sdk.registry import (
    RegisterNodeResult,
    RegistrationError,
    build_registry_payload,
    register_node,
)
from canvastekk_workflow_sdk.request import NodeExecutionRequest
from canvastekk_workflow_sdk.response import HealthResponse, NodeExecutionResponse
from canvastekk_workflow_sdk.router import create_multi_node_app
from canvastekk_workflow_sdk.uploads import OutputUploader, S3PresignedUploader, get_default_uploader

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
    "NodeOutputValidationError",
    "NodeStyles",
    "NodeExecutionRequest",
    "NodeExecutionResponse",
    "NodeTimeoutError",
    "NodeValidationError",
    "NodeAuth",
    "OutputUploader",
    "Plane",
    "PlaneSet",
    "Point3D",
    "RetryConfig",
    "RegistrationError",
    "RegisterNodeResult",
    "SDKVersionMiddleware",
    "StructuredJsonFormatter",
    "S3PresignedUploader",
    "TimingMiddleware",
    "create_multi_node_app",
    "create_node_app",
    "configure_logging",
    "export_definition",
    "get_default_uploader",
    "get_node_logger",
    "register_node",
    "build_registry_payload",
]

__version__ = "0.11.0"
