"""
Registry Helper

Convenience function for registering nodes with the workflow engine
registry via its REST API. Intended for use in CI/CD pipelines.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal, get_args

import httpx
from pydantic import BaseModel

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.base import BaseNode
    from canvastekk_workflow_sdk.definition import WorkflowNodeManifest

logger = logging.getLogger(__name__)

InvokeType = Literal["http", "lambda", "sagemaker", "in-process"]
VALID_INVOKE_TYPES: set[str] = set(get_args(InvokeType))


class RegistrationError(Exception):
    """Raised when node registration fails."""

    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class RegisterNodeResult(BaseModel):
    """Structured result from node registration.

    Supports dict-like access (``result["name"]``) for backward compatibility
    by delegating to the ``node`` field.

    Attributes:
        node: Registered node definition dict from the engine.
        action: Registration outcome — ``"created"`` (new node),
            ``"updated"`` (new version of existing node), or ``"unchanged"``
            (same version, same data, idempotent no-op).
        revision_id: Engine revision identifier for this registration.
        previous_version: Previous version string if this was an update.
        changes: List of changed field names if this was an update.
    """

    node: dict[str, Any]
    action: str | None = None
    revision_id: str | None = None
    previous_version: str | None = None
    changes: list[str] | None = None

    def __getitem__(self, key: str) -> Any:
        return self.node[key]

    def __contains__(self, key: str) -> bool:
        return key in self.node

    def get(self, key: str, default: Any = None) -> Any:
        return self.node.get(key, default)


def build_registry_payload(
    definition: WorkflowNodeManifest,
    *,
    invoke_type: InvokeType = "http",
    invoke_url: str | None = None,
    invoke_config: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    constraints: dict[str, Any] | None = None,
    node_status: str = "active",
) -> dict[str, Any]:
    """Build a registry-compatible payload dict from a WorkflowNodeManifest.

    Centralizes field mapping (title->label, default_retry->retry, omit id)
    so that ``register_node()`` and ``export_definition()`` share the same logic.

    The payload targets the engine's ``RegisterNodeRequest`` schema, which
    registers a ``WorkflowNode`` (the registry-level node type). This is
    distinct from ``WorkflowDefinitionNode`` (a node instance in a workflow
    definition).

    Versioning note:
        The ``version`` field in the payload is the node's semantic version
        (e.g., ``"1.2.0"``). The engine stores and enforces this version —
        re-registering with the same version and changed data is rejected.
        Node authors must bump the version for any schema changes.

    Args:
        definition: The SDK WorkflowNodeManifest to convert.
        invoke_type: Invocation type (``"http"``, ``"lambda"``,
            ``"sagemaker"``, or ``"in-process"``).
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
        "node_role": definition.role.value,
        "retry": definition.default_retry.model_dump(mode="json"),
        "tags": tags or [],
        "styles": resolved_styles,
        "node_status": node_status,
    }

    if invoke_url is not None:
        payload["invoke_url"] = invoke_url
    if invoke_config is not None:
        payload["invoke_config"] = invoke_config
    if constraints is not None:
        payload["constraints"] = constraints

    return payload


def _extract_node_data(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract node definition from registry response, handling multiple formats.

    The ``"node"`` key takes precedence over ``"data"`` when both are present,
    matching the engine's current ``RegisterNodeResponse`` schema.

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
) -> RegisterNodeResult:
    """Register a node with the workflow engine registry.

    POSTs the node manifest to the registry endpoint. Intended for
    use in CI/CD pipelines after deployment.

    The engine's registry stores the node as a ``WorkflowNode`` (registry-level
    node type). This is distinct from ``WorkflowDefinitionNode``, which
    represents a node instance within a specific workflow definition.

    Versioning:
        The engine uses the semantic version string from ``WorkflowNodeManifest.version``
        directly. Versions are immutable: re-registering with the same version
        and changed data is rejected (HTTP 409). Node authors must bump the
        version for any schema or metadata changes.

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
        A :class:`RegisterNodeResult` containing the registered node data,
        the action taken (``"created"``, ``"updated"``, ``"unchanged"``),
        and metadata such as ``revision_id``, ``previous_version``, and
        ``changes``. For backward compatibility, the result supports dict-like
        access (``result["name"]``) by delegating to the ``node`` field.

    Raises:
        RegistrationError: If the registration request fails.
        ValueError: If neither ``api_key`` nor ``service_token`` is provided,
            or if ``invoke_type`` is invalid.

    Example::

        from canvastekk_workflow_sdk.registry import register_node

        node = MyNode()
        result = register_node(
            node,
            registry_url="https://engine.example.com/api/workflows/nodes/",
            invoke_url="https://my-node.example.com",
            api_key="secret-key",
        )
        print(result.action)         # "created"
        print(result.revision_id)    # "rev-abc123"
        print(result["name"])        # dict-like access for backward compat

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

        node_data = _extract_node_data(response_data)
        return RegisterNodeResult(
            node=node_data,
            action=action,
            revision_id=revision_id,
            previous_version=previous_version,
            changes=changes,
        )
    except httpx.HTTPStatusError as e:
        raise RegistrationError(
            f"Registration failed: {e}",
            status_code=e.response.status_code,
            body=e.response.text,
        ) from e
    except httpx.HTTPError as e:
        raise RegistrationError(f"Registration failed: {e}") from e
