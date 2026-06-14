"""
FastAPI App Factory

Creates a FastAPI application with standard node endpoints:
- POST /execute - Run the node
- GET /health - Health check
- GET /manifest - Node self-description
- POST /hook - Webhook/callback handler (stub, 501 by default)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from canvastekk_workflow_sdk.exceptions import NodeExecutionError, NodeTimeoutError, get_http_status_for_error
from canvastekk_workflow_sdk.logging import configure_logging
from canvastekk_workflow_sdk.middleware import SDKVersionMiddleware
from canvastekk_workflow_sdk.request import NodeExecutionRequest
from canvastekk_workflow_sdk.response import HealthResponse, NodeExecutionResponse
from canvastekk_workflow_sdk.uploads import get_default_uploader

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.base import BaseNode

logger = logging.getLogger(__name__)


def _upload_to_presigned(file_path: str, presigned_url: str) -> None:
    """Upload a local file to an S3 pre-signed PUT URL.

    Uses httpx for HTTP requests.

    Args:
        file_path: Path to the local file to upload.
        presigned_url: Pre-signed S3 PUT URL.

    Raises:
        httpx.HTTPStatusError: If the upload fails.
    """
    get_default_uploader().upload_file(file_path, presigned_url)


def _upload_outputs_to_s3(
    response: NodeExecutionResponse,
    upload_urls: dict[str, str],
    file_output_fields: list[str],
) -> None:
    """Upload file output files to S3 via pre-signed URLs.

    Delegates to the default ``S3PresignedUploader`` instance.

    Args:
        response: The node execution response containing output values.
        upload_urls: Mapping of output field name to pre-signed PUT URL.
        file_output_fields: Output field names that produce files.
    """
    get_default_uploader().upload_outputs(response, upload_urls, file_output_fields)


_NODE_OPENAPI_TAGS: list[dict[str, str]] = [
    {"name": "Execution", "description": "Run a node with given inputs and receive structured output."},
    {"name": "Health", "description": "Check node health and readiness."},
    {"name": "Discovery", "description": "Retrieve node metadata, schemas, and self-description."},
    {"name": "Callbacks", "description": "Webhook and async callback endpoints."},
    {"name": "Observability", "description": "Execution metrics and telemetry."},
]


def create_node_app(
    node: BaseNode,
    *,
    dependencies: Sequence[Any] | None = None,
    extra_routes: list[APIRouter] | None = None,
    **fastapi_kwargs: Any,
) -> FastAPI:
    """
    Create a FastAPI application with standard node endpoints.

    This function creates an HTTP server that implements the node contract:
    - POST /execute - Execute the node with given inputs
    - GET /health - Return node health status
    - GET /manifest - Return node's self-description (WorkflowNodeManifest)
    - POST /hook - Webhook/callback handler

    Args:
        node: The BaseNode instance to wrap
        dependencies: Optional FastAPI dependencies applied to all endpoints
            (e.g., ``[Depends(auth)]`` for request authentication).
        extra_routes: Optional list of FastAPI APIRouter instances to mount
            on the application.
        **fastapi_kwargs: Additional arguments passed to FastAPI constructor
            (e.g., title, version, docs_url)

    Returns:
        FastAPI application instance

    Example:
        from canvastekk_workflow_sdk.auth import NodeAuth

        node = EchoNode()
        auth = NodeAuth.api_key()
        app = create_node_app(node, dependencies=[Depends(auth)])

        # Run with: uvicorn handler:app --port 8001
    """
    default_kwargs: dict[str, Any] = {
        "title": node.definition.title,
        "version": node.definition.version,
        "description": node.definition.description,
        "openapi_tags": _NODE_OPENAPI_TAGS,
    }
    default_kwargs.update(fastapi_kwargs)

    # Merge node lifespan hooks with any user-provided lifespan
    base_lifespan = default_kwargs.pop("lifespan", None)

    @asynccontextmanager
    async def _node_lifespan(app: Any) -> Any:
        configure_logging()
        async with node._lifespan():
            if base_lifespan:
                async with base_lifespan(app):
                    yield
            else:
                yield

    app = FastAPI(lifespan=_node_lifespan, **default_kwargs)
    app.add_middleware(SDKVersionMiddleware)

    router_dependencies = list(dependencies) if dependencies else []

    router = APIRouter(dependencies=router_dependencies)

    @router.post(
        "/execute",
        response_model=NodeExecutionResponse,
        summary="Execute node",
        description="Execute the node with given inputs via JSON body.",
        tags=["Execution"],
        responses={
            200: {"description": "Node executed successfully"},
            400: {
                "description": "Bad request — invalid or missing inputs",
                "content": {"application/json": {"example": {"detail": "Missing required input: file_path"}}},
            },
            422: {
                "description": "Validation error — request body does not match schema",
                "content": {
                    "application/json": {"example": {"detail": [{"loc": ["body", "run_id"], "msg": "field required"}]}}
                },
            },
            500: {
                "description": "Internal server error — unexpected failure during execution",
                "content": {
                    "application/json": {"example": {"detail": "Unexpected error", "error_type": "RuntimeError"}}
                },
            },
        },
    )
    async def execute(request: Request) -> NodeExecutionResponse:
        """
        Execute the node with given inputs via JSON body.

        The engine sends presigned GET URLs for file input fields.
        Outputs are uploaded via presigned PUT URLs after successful execution.
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid JSON body"},
            )
        exec_request = NodeExecutionRequest(**body)

        timeout = node.definition.timeout_seconds
        if timeout and timeout > 0:
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(node.run, exec_request),
                    timeout=timeout,
                )
            except TimeoutError:
                raise NodeTimeoutError(timeout)
        else:
            response = await asyncio.to_thread(node.run, exec_request)

        if exec_request.output_upload_url and response.status == "pass":
            file_output_fields = node.definition.file_output_fields
            if file_output_fields:
                await asyncio.to_thread(
                    _upload_outputs_to_s3,
                    response,
                    exec_request.output_upload_url,
                    file_output_fields,
                )

        return response

    @router.get(
        "/health",
        response_model=HealthResponse,
        summary="Health check",
        description="Returns healthy/unhealthy/degraded status along with individual check results.",
        tags=["Health"],
    )
    async def health() -> HealthResponse:
        """
        Check node health.

        Returns healthy/unhealthy/degraded status along with
        individual check results.
        """
        checks = node.health_check()

        # Determine overall status from checks
        if not checks:
            status: Literal["healthy", "unhealthy", "degraded"] = "healthy"
        elif all(checks.values()):
            status = "healthy"
        elif any(checks.values()):
            status = "degraded"
        else:
            status = "unhealthy"

        return HealthResponse(
            status=status,
            node_id=node.definition.id,
            version=node.definition.version,
            checks=checks,
        )

    @router.get(
        "/manifest",
        summary="Node manifest",
        description="Returns the full WorkflowNodeManifest including identity, schemas, cost, retry policy, and metadata. "
        "Used by the registry for auto-discovery.",
        tags=["Discovery"],
    )
    async def manifest() -> JSONResponse:
        """
        Get node's self-description (manifest).

        Returns the WorkflowNodeManifest which includes:
        - Identity (id, name, version, title, description)
        - Schema (input_schema, output_schema)
        - Cost (token_cost)
        - Retry defaults
        - Metadata (category, timeout, role)
        - SDK version (sdk_version — auto-injected)
        - Node environment (mode — "dev" or "production", from CANVASTEKK_NODE_ENV)

        Used by registry for auto-discovery and manifest cross-checking.
        The engine reads ``mode`` to decide routing and test behaviour.
        """
        import os

        import canvastekk_workflow_sdk

        content = node.definition.to_dict()
        content["sdk_version"] = canvastekk_workflow_sdk.__version__
        raw_env = os.environ.get("CANVASTEKK_NODE_ENV", "dev").lower()
        if raw_env in ("dev", "development", "test"):
            mode = "dev"
        elif raw_env in ("uat", "staging"):
            mode = "uat"
        else:
            mode = "production"
        content["mode"] = mode
        return JSONResponse(content=content)

    @router.post(
        "/hook",
        summary="Webhook callback",
        description="Receives external triggers, progress updates, or async completion notifications. "
        "Returns 501 if the node has not overridden hook().",
        tags=["Callbacks"],
    )
    async def hook(request: Request) -> JSONResponse:
        """
        Webhook/callback endpoint for async operations.

        Receives external triggers, progress updates, or async completion
        notifications. Subclasses can override BaseNode.hook() to handle
        these payloads.

        Returns 501 Not Implemented if the node has not overridden hook().
        """
        body: dict[str, Any] = await request.json()
        result = node.hook(body)
        if result is None:
            return JSONResponse(
                status_code=501,
                content={"detail": "Hook not implemented for this node"},
            )
        return JSONResponse(content=result)

    @router.get(
        "/metrics",
        summary="Execution metrics",
        description="Aggregated execution statistics including success rate, average duration, and token usage.",
        tags=["Observability"],
    )
    async def metrics() -> JSONResponse:
        """
        Get node execution metrics.

        Returns aggregated execution statistics including success rate,
        average duration, and token usage.
        """
        return JSONResponse(content=node._metrics_collector.get_summary())

    @router.get(
        "/live",
        summary="Liveness probe",
        description="Returns 200 if the process is alive. Used by Kubernetes to decide whether to restart the pod.",
        tags=["Health"],
    )
    async def liveness() -> JSONResponse:
        """Liveness probe — always returns 200 if the process is running."""
        return JSONResponse(content={"status": "alive"})

    @router.get(
        "/ready",
        summary="Readiness probe",
        description="Returns 200 when the node is ready to accept traffic. "
        "Calls node.health_check(); returns 503 if any check fails.",
        tags=["Health"],
    )
    async def readiness() -> JSONResponse:
        """Readiness probe — returns 200 when the node can accept traffic."""
        checks = node.health_check()
        if not checks or all(checks.values()):
            return JSONResponse(content={"status": "ready", "node_id": node.definition.id, "checks": checks})
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "node_id": node.definition.id, "checks": checks},
        )

    app.include_router(router)

    if extra_routes:
        for extra_router in extra_routes:
            app.include_router(extra_router)

    @app.exception_handler(NodeExecutionError)
    async def node_error_handler(request: object, exc: NodeExecutionError) -> JSONResponse:
        """Handle structured node execution errors."""
        status_code = get_http_status_for_error(exc)
        return JSONResponse(
            status_code=status_code,
            content={
                "detail": exc.message,
                "error_type": type(exc).__name__,
                "error_code": exc.error_code,
                **exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def exception_handler(request: object, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions."""
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "error_type": type(exc).__name__,
            },
        )

    return app
