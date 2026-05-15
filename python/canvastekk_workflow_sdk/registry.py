"""
Registry Helper

Convenience function for registering nodes with the workflow engine
registry via its REST API. Intended for use in CI/CD pipelines.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import TYPE_CHECKING, Any
from urllib.error import URLError

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

    payload = json.dumps(manifest).encode("utf-8")

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key:
        headers["X-API-Key"] = api_key

    req = urllib.request.Request(
        registry_url,
        data=payload,
        method="POST",
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except URLError as e:
        status_code = getattr(e, "code", None)
        body = getattr(e, "read", lambda: b"")().decode("utf-8") if hasattr(e, "read") else None
        raise RegistrationError(
            f"Registration failed: {e}",
            status_code=status_code,
            body=body,
        ) from e
