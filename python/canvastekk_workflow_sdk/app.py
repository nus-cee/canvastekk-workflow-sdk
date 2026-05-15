"""
FastAPI App Factory

Creates a FastAPI application with standard node endpoints:
- POST /execute - Run the node
- GET /health - Health check
- GET /manifest - Node self-description (replaces /definition)
- GET /definition - Deprecated, redirects to /manifest
- POST /hook - Webhook/callback handler (stub, 501 by default)
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from collections.abc import Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.datastructures import UploadFile

from canvastekk_workflow_sdk.exceptions import NodeExecutionError, get_http_status_for_error
from canvastekk_workflow_sdk.request import NodeExecutionRequest
from canvastekk_workflow_sdk.response import HealthResponse, NodeExecutionResponse
from canvastekk_workflow_sdk.uploads import get_default_uploader

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.base import BaseNode

logger = logging.getLogger(__name__)


def _coerce_form_value(key: str, value: str, schema: dict[str, Any]) -> Any:
    """Coerce a string form value to the type declared in input_schema.

    Args:
        key: Field name (for error messages).
        value: Raw string value from form data.
        schema: The JSON Schema for this field from input_schema["properties"][key].

    Returns:
        The coerced value (int, float, bool, or original string).
    """
    field_type = schema.get("type", "string")
    if field_type == "number":
        return float(value)
    if field_type == "integer":
        return int(value)
    if field_type == "boolean":
        return value.lower() in ("true", "1", "yes")
    return value


def _upload_to_presigned(file_path: str, presigned_url: str) -> None:
    """Upload a local file to an S3 pre-signed PUT URL.

    Uses urllib from stdlib — no boto3 or httpx dependency required.

    Args:
        file_path: Path to the local file to upload.
        presigned_url: Pre-signed S3 PUT URL.

    Raises:
        urllib.error.URLError: If the upload fails.
    """
    get_default_uploader().upload_file(file_path, presigned_url)


def _upload_outputs_to_s3(
    response: NodeExecutionResponse,
    upload_urls: dict[str, str],
    file_output_fields: list[str],
) -> None:
    """Upload binary output files to S3 via pre-signed URLs.

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
    **fastapi_kwargs: object,
) -> FastAPI:
    """
    Create a FastAPI application with standard node endpoints.

    This function creates an HTTP server that implements the node contract:
    - POST /execute - Execute the node with given inputs
    - GET /health - Return node health status
    - GET /manifest - Return node's self-description (NodeDefinition)
    - GET /definition - Deprecated redirect to /manifest
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
        async with node._lifespan():
            if base_lifespan:
                async with base_lifespan(app):
                    yield
            else:
                yield

    app = FastAPI(lifespan=_node_lifespan, **default_kwargs)

    router_dependencies = list(dependencies) if dependencies else []

    router = APIRouter(dependencies=router_dependencies)

    @router.post(
        "/execute",
        response_model=NodeExecutionResponse,
        summary="Execute node",
        description="Execute the node with given inputs. Accepts JSON or multipart/form-data payloads.",
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
        Execute the node with given inputs.

        Accepts both application/json and multipart/form-data payloads.

        For JSON: standard NodeExecutionRequest body.
        For multipart: form fields for run_id, node_id, scalar inputs,
        and file uploads for binary inputs.
        """
        content_type = request.headers.get("content-type", "")

        if "multipart/form-data" in content_type:
            form = await request.form()
            properties = node.definition.input_schema.get("properties", {})
            file_fields = set(node.definition.file_input_fields)

            run_id = str(form.get("run_id", ""))
            node_id = str(form.get("node_id", ""))
            callback_url = form.get("callback_url")
            output_upload_url_raw = form.get("output_upload_url")

            # Parse output_upload_url from JSON string (dict serialized for form data)
            output_upload_url: dict[str, str] | None = None
            if output_upload_url_raw:
                try:
                    output_upload_url = json.loads(str(output_upload_url_raw))
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Failed to parse output_upload_url from form data")

            inputs: dict[str, Any] = {}
            for field_name, field_value in form.items():
                if field_name in ("run_id", "node_id", "callback_url", "output_upload_url"):
                    continue

                if isinstance(field_value, UploadFile):
                    # Save uploaded file to temp directory
                    tmp_dir = Path(tempfile.mkdtemp())
                    filename = field_value.filename or field_name
                    file_path = tmp_dir / filename
                    content = await field_value.read()
                    file_path.write_bytes(content)
                    inputs[field_name] = str(file_path)
                elif field_name in file_fields:
                    # Binary field sent as raw string path (edge case)
                    inputs[field_name] = str(field_value)
                else:
                    # Scalar field: coerce type from schema
                    field_schema = properties.get(field_name, {})
                    inputs[field_name] = _coerce_form_value(field_name, str(field_value), field_schema)

            exec_request = NodeExecutionRequest(
                run_id=run_id,
                node_id=node_id,
                inputs=inputs,
                callback_url=str(callback_url) if callback_url else None,
                output_upload_url=output_upload_url,
            )
        else:
            # JSON body (backward compatible)
            body = await request.json()
            exec_request = NodeExecutionRequest(**body)

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
            status = "healthy"
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
        description="Returns the full NodeDefinition including identity, schemas, cost, retry policy, and metadata. "
        "Used by the registry for auto-discovery.",
        tags=["Discovery"],
    )
    async def manifest() -> JSONResponse:
        """
        Get node's self-description (manifest).

        Returns the NodeDefinition which includes:
        - Identity (id, name, version, title, description)
        - Schema (input_schema, output_schema)
        - Cost (token_cost)
        - Retry defaults
        - Metadata (category, timeout, is_control_flow)

        Used by registry for auto-discovery and manifest cross-checking.
        """
        return JSONResponse(content=node.definition.to_dict())

    @router.get(
        "/definition",
        deprecated=True,
        summary="Node definition (deprecated)",
        description="Deprecated: use GET /manifest instead. Redirects with 301.",
        tags=["Discovery"],
    )
    async def definition() -> RedirectResponse:
        """
        Deprecated: use GET /manifest instead.

        Redirects to /manifest with a 301 Moved Permanently status.
        """
        return RedirectResponse(url="/manifest", status_code=301)

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
