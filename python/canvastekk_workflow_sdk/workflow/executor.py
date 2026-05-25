"""
Node Executor Strategy

Defines how a node is executed: in-process (BaseNode.execute) or HTTP (POST /execute).
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.base import BaseNode
    from canvastekk_workflow_sdk.context import ExecutionContext


class NodeExecutor(ABC):
    """Abstract strategy for executing a workflow node."""

    @abstractmethod
    async def execute(
        self,
        slug: str,
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        """Execute a node and return its outputs."""

    @abstractmethod
    def has(self, slug: str) -> bool:
        """Check if this executor can handle the given slug."""


class InProcessExecutor(NodeExecutor):
    """Execute nodes by calling BaseNode.execute() directly via asyncio.to_thread.

    Example::

        executor = InProcessExecutor()
        executor.register("segmentation-v1.0.0", MySegmentNode())
        runner = WorkflowRunner(executor)
    """

    def __init__(self) -> None:
        self._registry: dict[str, BaseNode] = {}

    def register(self, slug: str, node: BaseNode) -> InProcessExecutor:
        """Register a BaseNode instance for a slug.

        Args:
            slug: Node type slug (e.g. ``"segmentation-v1.0.0"``).
            node: BaseNode instance.

        Returns:
            self for chaining.
        """
        self._registry[slug] = node
        return self

    async def execute(
        self,
        slug: str,
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        node = self._registry[slug]
        return await asyncio.to_thread(node.execute, inputs, context)

    def has(self, slug: str) -> bool:
        return slug in self._registry


class HttpExecutor(NodeExecutor):
    """Execute nodes by POSTing to their ``/execute`` endpoint.

    Posts a ``NodeExecutionRequest``-compatible payload:
    ``{"run_id": ..., "node_id": ..., "inputs": ...}``

    Example::

        executor = HttpExecutor()
        executor.register_url("segmentation-v1.0.0", "http://localhost:8001")
        runner = WorkflowRunner(executor)
    """

    def __init__(self, *, timeout: float = 300.0) -> None:
        self._urls: dict[str, str] = {}
        self._timeout = timeout

    def register_url(self, slug: str, url: str) -> HttpExecutor:
        """Register a base URL for a slug.

        Args:
            slug: Node type slug (e.g. ``"segmentation-v1.0.0"``).
            url: Base URL where the node is hosted (e.g. ``"http://localhost:8001"``).

        Returns:
            self for chaining.
        """
        self._urls[slug] = url.rstrip("/")
        return self

    async def execute(
        self,
        slug: str,
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        url = self._urls[slug]
        payload = {
            "run_id": context.run_id,
            "node_id": context.node_id,
            "inputs": inputs,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{url}/execute", json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "pass":
                return data.get("outputs", {})
            raise RuntimeError(
                f"Node '{slug}' returned failure: {data.get('error', 'unknown')}"
            )

    def has(self, slug: str) -> bool:
        return slug in self._urls
