"""
Workflow Runner

Local workflow executor that ties together executor, resolver, and level computation.
Accepts a NodeExecutor via constructor (Strategy pattern).
"""

from __future__ import annotations

import asyncio
import time
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from canvastekk_workflow_sdk.context import ExecutionContext
from canvastekk_workflow_sdk.workflow._control_flow import CONTROL_FLOW_HANDLERS
from canvastekk_workflow_sdk.workflow.executor import NodeExecutor
from canvastekk_workflow_sdk.workflow.level import compute_levels
from canvastekk_workflow_sdk.workflow.resolver import resolve_inputs

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.workflow.models import WorkflowSpec


class ErrorPolicy(StrEnum):
    """How the runner handles node execution failures."""

    FAIL_FAST = "fail_fast"
    CONTINUE = "continue"


class NodeResult:
    """Result of executing a single node."""

    __slots__ = ("node_id", "slug", "status", "outputs", "duration_ms", "error", "skipped_reason")

    def __init__(
        self,
        node_id: str,
        slug: str,
        status: str,
        outputs: dict[str, Any] | None = None,
        duration_ms: int = 0,
        error: str | None = None,
        skipped_reason: str | None = None,
    ) -> None:
        self.node_id = node_id
        self.slug = slug
        self.status = status
        self.outputs = outputs
        self.duration_ms = duration_ms
        self.error = error
        self.skipped_reason = skipped_reason


class WorkflowRunResult:
    """Result of executing a complete workflow."""

    __slots__ = ("status", "final_outputs", "node_results", "duration_ms")

    def __init__(
        self,
        status: str,
        final_outputs: dict[str, Any],
        node_results: list[NodeResult],
        duration_ms: int,
    ) -> None:
        self.status = status
        self.final_outputs = final_outputs
        self.node_results = node_results
        self.duration_ms = duration_ms


class WorkflowRunner:
    """Local workflow runner.

    Accepts a ``NodeExecutor`` strategy and runs a workflow spec level-by-level.

    Example::

        executor = InProcessExecutor()
        executor.register("segmentation-v1.0.0", MySegmentNode())
        runner = WorkflowRunner(executor)
        result = runner.run(spec, inputs={"point_cloud": "/data/scan.las"})
    """

    def __init__(
        self,
        executor: NodeExecutor,
        *,
        error_policy: ErrorPolicy = ErrorPolicy.FAIL_FAST,
    ) -> None:
        self._executor = executor
        self._error_policy = error_policy

    def run(
        self,
        spec: WorkflowSpec,
        inputs: dict[str, Any] | None = None,
    ) -> WorkflowRunResult:
        """Execute a workflow synchronously.

        Args:
            spec: The workflow spec to execute.
            inputs: Initial inputs for the START node.

        Returns:
            WorkflowRunResult with final outputs and per-node results.
        """
        return asyncio.run(self.run_async(spec, inputs))

    async def run_async(
        self,
        spec: WorkflowSpec,
        inputs: dict[str, Any] | None = None,
    ) -> WorkflowRunResult:
        """Execute a workflow asynchronously.

        Args:
            spec: The workflow spec to execute.
            inputs: Initial inputs for the START node.

        Returns:
            WorkflowRunResult with final outputs and per-node results.
        """
        start_time = time.perf_counter()
        node_map = {n.id: n for n in spec.nodes}
        node_outputs: dict[str, dict[str, Any]] = {}
        node_results: list[NodeResult] = []
        failed_nodes: set[str] = set()

        if inputs:
            start_nodes = [n for n in spec.nodes if n.slug == "__start__"]
            if start_nodes:
                node_outputs[start_nodes[0].id] = inputs

        levels = compute_levels(spec)

        for level in levels:
            control_ids: list[str] = []
            user_ids: list[str] = []

            for nid in level:
                slug = node_map[nid].slug
                if slug in CONTROL_FLOW_HANDLERS:
                    control_ids.append(nid)
                else:
                    user_ids.append(nid)

            for nid in control_ids:
                node = node_map[nid]
                handler = CONTROL_FLOW_HANDLERS[node.slug]
                resolved = resolve_inputs(nid, spec, node_outputs)
                context = ExecutionContext(run_id="local", node_id=nid)
                t0 = time.perf_counter()
                try:
                    outputs = handler(resolved, context)
                    node_outputs[nid] = outputs
                    node_results.append(
                        NodeResult(
                            node_id=nid,
                            slug=node.slug,
                            status="completed",
                            outputs=outputs,
                            duration_ms=int((time.perf_counter() - t0) * 1000),
                        )
                    )
                except Exception as exc:
                    failed_nodes.add(nid)
                    node_results.append(
                        NodeResult(
                            node_id=nid,
                            slug=node.slug,
                            status="failed",
                            duration_ms=int((time.perf_counter() - t0) * 1000),
                            error=str(exc),
                        )
                    )

            tasks: list[Any] = []
            task_node_ids: list[str] = []

            for nid in user_ids:
                upstream_failed = any(
                    e.from_node in failed_nodes
                    for e in spec.edges
                    if e.to_node == nid
                )
                if upstream_failed or nid in failed_nodes:
                    node = node_map[nid]
                    node_results.append(
                        NodeResult(
                            node_id=nid,
                            slug=node.slug,
                            status="skipped",
                            skipped_reason="upstream_failed",
                        )
                    )
                    failed_nodes.add(nid)
                    continue

                node = node_map[nid]
                if not self._executor.has(node.slug):
                    node_results.append(
                        NodeResult(
                            node_id=nid,
                            slug=node.slug,
                            status="failed",
                            error=f"No executor registered for slug '{node.slug}'",
                        )
                    )
                    failed_nodes.add(nid)
                    if self._error_policy == ErrorPolicy.FAIL_FAST:
                        break
                    continue

                resolved = resolve_inputs(nid, spec, node_outputs)
                context = ExecutionContext(run_id="local", node_id=nid)
                tasks.append(self._executor.execute(node.slug, resolved, context))
                task_node_ids.append(nid)

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    nid = task_node_ids[i]
                    node = node_map[nid]
                    if isinstance(result, Exception):
                        failed_nodes.add(nid)
                        node_results.append(
                            NodeResult(
                                node_id=nid,
                                slug=node.slug,
                                status="failed",
                                error=str(result),
                            )
                        )
                    else:
                        node_outputs[nid] = result
                        node_results.append(
                            NodeResult(
                                node_id=nid,
                                slug=node.slug,
                                status="completed",
                                outputs=result,
                            )
                        )

            if self._error_policy == ErrorPolicy.FAIL_FAST and failed_nodes:
                break

        final_outputs: dict[str, Any] = {}
        for n in spec.nodes:
            if n.slug == "__end__" and n.id in node_outputs:
                final_outputs.update(node_outputs[n.id])

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        status = "completed" if not failed_nodes else "failed"

        return WorkflowRunResult(
            status=status,
            final_outputs=final_outputs,
            node_results=node_results,
            duration_ms=duration_ms,
        )
