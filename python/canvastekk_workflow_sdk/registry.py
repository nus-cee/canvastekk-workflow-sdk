"""
Registry Helper

Convenience function for registering nodes with the workflow engine
registry via its REST API. Intended for use in CI/CD pipelines.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.base import BaseNode

logger = logging.getLogger(__name__)


class RegistrationError(Exception):
    """Raised when node registration fails."""

    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _extract_node_data(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract node definition from registry response, handling both old and new formats.

    Args:
        payload: Parsed JSON response from the registry.

    Returns:
        The node definition dict.
    """
    if "data" in payload and isinstance(payload["data"], dict):
        return payload["data"]
    return payload


def register_node(
    node: BaseNode,
    registry_url: str,
    *,
    invoke_url: str | None = None,
    invoke_type: str = "http",
    api_key: str | None = None,
    service_token: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Register a node with the workflow engine registry.

    POSTs the node manifest to the registry endpoint. Intended for
    use in CI/CD pipelines after deployment.

    Args:
        node: The BaseNode instance to register.
        registry_url: Full URL of the registry endpoint
            (e.g., ``"https://engine.example.com/api/registry/nodes"``).
        invoke_url: URL where the node is reachable. If None, the
            registry may use the request origin.
        invoke_type: Invocation type (``"http"``, ``"lambda"``, etc.).
        api_key: Optional API key for registry authentication
            (sent as ``X-API-Key`` header).
        service_token: Optional service token for CI/CD authentication
            (sent as ``X-Service-Token`` header). Takes precedence over
            ``api_key`` when both are provided.
        timeout: Request timeout in seconds.

    Returns:
        The parsed JSON response from the registry. If the response uses
        the new ``RegisterNodeResponse`` wrapper format (with a ``data``
        key), the inner node definition dict is returned directly for
        backward compatibility.

    Raises:
        RegistrationError: If the registration request fails.
        ValueError: If neither ``api_key`` nor ``service_token`` is provided.

    Example::

        from canvastekk_workflow_sdk.registry import register_node

        node = MyNode()
        register_node(
            node,
            registry_url="https://engine.example.com/api/registry/nodes",
            invoke_url="https://my-node.example.com",
            api_key="secret-key",
        )

        # CI/CD with service token
        register_node(
            node,
            registry_url="https://engine.example.com/api/registry/nodes",
            invoke_url="https://my-node.example.com",
            service_token="svs_xxx",
        )
    """
    if not api_key and not service_token:
        raise ValueError("Either 'api_key' or 'service_token' must be provided for registration.")

    manifest = node.definition.to_dict()
    manifest["invoke_type"] = invoke_type
    if invoke_url is not None:
        manifest["invoke_url"] = invoke_url

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
        if action:
            logger.info("Node registration action: %s", action)
        return _extract_node_data(response_data)
    except httpx.HTTPStatusError as e:
        raise RegistrationError(
            f"Registration failed: {e}",
            status_code=e.response.status_code,
            body=e.response.text,
        ) from e
    except httpx.HTTPError as e:
        raise RegistrationError(f"Registration failed: {e}") from e
