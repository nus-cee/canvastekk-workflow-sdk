"""
Registry Helper

Convenience function for registering nodes with the workflow engine
registry via its REST API. Intended for use in CI/CD pipelines.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

import httpx
from pydantic import BaseModel

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.base import BaseNode
    from canvastekk_workflow_sdk.definition import NodeDefinition

logger = logging.getLogger(__name__)

InvokeType = Literal["http", "lambda", "sagemaker", "in-process"]
VALID_INVOKE_TYPES: set[str] = {"http", "lambda", "sagemaker", "in-process"}


class RegistrationError(Exception):
    """Raised when node registration fails."""

    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class RegisterNodeResult(BaseModel):
    """Structured result from node registration."""

    node: dict[str, Any]
    action: str | None = None
    revision_id: str | None = None
    previous_version: str | None = None
    changes: list[str] | None = None


def build_registry_payload(
    definition: NodeDefinition,
    *,
    invoke_type: str = "http",
    invoke_url: str | None = None,
    invoke_config: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    constraints: dict[str, Any] | None = None,
    node_status: str = "active",
) -> dict[str, Any]:
    """Build a registry-compatible payload dict from a NodeDefinition.

    Centralizes field mapping (title->label, default_retry->retry, omit id)
    so that ``register_node()`` and ``export_definition()`` share the same logic.

    Args:
        definition: The SDK NodeDefinition to convert.
        invoke_type: Invocation type (http, lambda, sagemaker, in-process).
        invoke_url: URL/ARN for invoking the node.
        invoke_config: Extra invocation parameters.
        tags: Searchable tags for the registry.
        constraints: Resource/compatibility constraints.
        node_status: Registry status (active, inactive, dead).

    Returns:
        A dict matching the engine's RegisterNodeRequest schema.
    """
    resolved_styles = None
    if definition.styles is not None:
        resolved_styles = definition.styles.model_dump(mode="json")

    payload: dict[str, Any] = {
        "name": definition.name,
        "label": definition.title,
        "version": definition.version,
        "description": definition.description,
        "input_schema": definition.input_schema,
        "output_schema": definition.output_schema,
        "invoke_type": invoke_type,
        "category": definition.category,
        "token_cost": definition.token_cost,
        "timeout_seconds": definition.timeout_seconds,
        "is_control_flow": definition.is_control_flow,
        "retry": definition.default_retry.model_dump(mode="json"),
        "tags": tags or [],
        "styles": resolved_styles,
        "node_status": node_status,
    }

    payload["invoke_url"] = invoke_url
    if invoke_config is not None:
        payload["invoke_config"] = invoke_config
    if constraints is not None:
        payload["constraints"] = constraints

    return payload


def _extract_node_data(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract node definition from registry response, handling multiple formats.

    Args:
        payload: Parsed JSON response from the registry.

    Returns:
        The node definition dict.
    """
    if "node" in payload and isinstance(payload["node"], dict):
        return payload["node"]
    if "data" in payload and isinstance(payload["data"], dict):
        return payload["data"]
    return payload


def register_node(
    node: BaseNode,
    registry_url: str,
    *,
    invoke_url: str | None = None,
    invoke_type: InvokeType = "http",
    api_key: str | None = None,
    service_token: str | None = None,
    tags: list[str] | None = None,
    invoke_config: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Register a node with the workflow engine registry.

    POSTs the node manifest to the registry endpoint. Intended for
    use in CI/CD pipelines after deployment.

    Args:
        node: The BaseNode instance to register.
        registry_url: Full URL of the registry endpoint
            (e.g., ``"https://engine.example.com/api/workflows/nodes/"``).
        invoke_url: URL where the node is reachable.
        invoke_type: Invocation type (``"http"``, ``"lambda"``,
            ``"sagemaker"``, or ``"in-process"``).
        api_key: Optional API key for registry authentication
            (sent as ``X-API-Key`` header).
        service_token: Optional service token for CI/CD authentication
            (sent as ``X-Service-Token`` header). Takes precedence over
            ``api_key`` when both are provided.
        tags: Optional searchable tags for the registry.
        invoke_config: Optional extra invocation parameters.
        timeout: Request timeout in seconds.

    Returns:
        The parsed JSON response from the registry. If the response uses
        a wrapper format (``{"node": ...}`` or ``{"data": ...}``), the inner
        node definition dict is returned directly for backward compatibility.

    Raises:
        RegistrationError: If the registration request fails.
        ValueError: If neither ``api_key`` nor ``service_token`` is provided,
            or if ``invoke_type`` is invalid.

    Example::

        from canvastekk_workflow_sdk.registry import register_node

        node = MyNode()
        register_node(
            node,
            registry_url="https://engine.example.com/api/workflows/nodes/",
            invoke_url="https://my-node.example.com",
            api_key="secret-key",
        )

        # CI/CD with service token
        register_node(
            node,
            registry_url="https://engine.example.com/api/workflows/nodes/",
            invoke_url="https://my-node.example.com",
            service_token="svs_xxx",
        )
    """
    if not api_key and not service_token:
        raise ValueError("Either 'api_key' or 'service_token' must be provided for registration.")

    if invoke_type not in VALID_INVOKE_TYPES:
        raise ValueError(
            f"Invalid invoke_type '{invoke_type}'. Must be one of: {', '.join(sorted(VALID_INVOKE_TYPES))}"
        )

    manifest = build_registry_payload(
        node.definition,
        invoke_type=invoke_type,
        invoke_url=invoke_url,
        tags=tags,
        invoke_config=invoke_config,
    )

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if service_token:
        headers["X-Service-Token"] = service_token
    elif api_key:
        headers["X-API-Key"] = api_key

    try:
        resp = httpx.post(registry_url, json=manifest, headers=headers, timeout=timeout)
        resp.raise_for_status()
        response_data = resp.json()

        action = response_data.get("action")
        revision_id = response_data.get("revision_id")
        previous_version = response_data.get("previous_version")
        changes = response_data.get("changes")

        if action:
            logger.info("Node registration action: %s", action)
        if revision_id:
            logger.info("Revision ID: %s", revision_id)
        if previous_version:
            logger.info("Previous version: %s", previous_version)
        if changes:
            logger.info("Changed fields: %s", changes)

        return _extract_node_data(response_data)
    except httpx.HTTPStatusError as e:
        raise RegistrationError(
            f"Registration failed: {e}",
            status_code=e.response.status_code,
            body=e.response.text,
        ) from e
    except httpx.HTTPError as e:
        raise RegistrationError(f"Registration failed: {e}") from e
