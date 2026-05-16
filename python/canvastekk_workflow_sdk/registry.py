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


def register_node(
    node: BaseNode,
    registry_url: str,
    *,
    invoke_url: str | None = None,
    invoke_type: str = "http",
    api_key: str | None = None,
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
        timeout: Request timeout in seconds.

    Returns:
        The parsed JSON response from the registry.

    Raises:
        RegistrationError: If the registration request fails.

    Example::

        from canvastekk_workflow_sdk.registry import register_node

        node = MyNode()
        register_node(
            node,
            registry_url="https://engine.example.com/api/registry/nodes",
            invoke_url="https://my-node.example.com",
            api_key="secret-key",
        )
    """
    manifest = node.definition.to_dict()
    manifest["invoke_type"] = invoke_type
    if invoke_url is not None:
        manifest["invoke_url"] = invoke_url

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        resp = httpx.post(registry_url, json=manifest, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise RegistrationError(
            f"Registration failed: {e}",
            status_code=e.response.status_code,
            body=e.response.text,
        ) from e
    except httpx.HTTPError as e:
        raise RegistrationError(f"Registration failed: {e}") from e
