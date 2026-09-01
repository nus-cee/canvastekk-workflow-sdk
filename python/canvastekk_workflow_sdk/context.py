"""
Execution Context

Provides context to the node's execute() method including
run information, output directory, and logging.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from canvastekk_workflow_sdk.logging import get_node_logger

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.request import NodeExecutionRequest


class ExecutionContext:
    """
    Context provided to node execute() method.

    Provides access to:
    - Run and node identifiers
    - Output directory for temporary files
    - Downloads directory for auto-downloaded file inputs
    - Metadata dict for download tracking
    - Logger with context
    - Progress reporting (for long-running operations)
    - Cooperative cancellation (``cancel_event``) — set by the server when
      the request deadline expires; checked between download chunks.
      ``execute()`` itself cannot be interrupted.
    """

    def __init__(
        self,
        request: NodeExecutionRequest | None = None,
        output_dir: Path | None = None,
        *,
        run_id: str | None = None,
        node_id: str | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        """Initialize execution context.

        Args:
            request: Node execution request (provides run_id, node_id).
            output_dir: Override output directory (defaults to temp or env var).
            run_id: Override workflow run ID.
            node_id: Override node instance ID.
            cancel_event: Cooperative cancellation event for downloads.
        """
        self._request = request
        resolved_run_id = run_id or (request.run_id if request else "local")
        resolved_node_id = node_id or (request.node_id if request else "unknown")

        if output_dir is not None:
            self._output_dir = output_dir
        else:
            base_dir = os.environ.get("CANVASTEKK_OUTPUT_DIR")
            if base_dir:
                self._output_dir = Path(base_dir) / resolved_run_id / resolved_node_id
            else:
                self._output_dir = Path("/tmp") / resolved_run_id / resolved_node_id
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._logger = get_node_logger(resolved_node_id)

        self._token_usage: dict[str, int] = {}
        self._metadata: dict[str, Any] = {}
        self._downloads_dir: Path | None = None
        self._cancel_event = cancel_event if cancel_event is not None else threading.Event()

    @property
    def cancel_event(self) -> threading.Event:
        """Cooperative cancellation event — set when the request deadline expires."""
        return self._cancel_event

    @property
    def run_id(self) -> str:
        """Workflow run identifier."""
        if self._request is not None:
            return self._request.run_id
        return self._output_dir.parent.name

    @property
    def node_id(self) -> str:
        """Node instance ID in workflow."""
        if self._request is not None:
            return self._request.node_id
        return self._output_dir.name

    @property
    def account_id(self) -> int | None:
        """Active account ID asserted by the orchestrator (DA-2242).

        Engine-controlled routing identity (not an auth credential) — set
        exclusively from the ``X-Account-Id`` header on ``/execute``.
        ``None`` for local runs and request-less contexts.
        """
        if self._request is not None:
            return self._request.account_id
        return None

    @property
    def output_dir(self) -> Path:
        """Local temp directory for outputs."""
        return self._output_dir

    @property
    def logger(self) -> logging.Logger:
        """Pre-configured logger with context."""
        return self._logger

    def output_path(self, filename: str) -> Path:
        """
        Get path for an output file.

        Files written to output paths will be uploaded to storage
        by the SDK after execute() returns.

        Args:
            filename: Name of the output file

        Returns:
            Full path in the output directory

        Raises:
            ValueError: If the filename escapes the output directory
                (path traversal — absolute paths or ``..`` segments).
        """
        candidate = (self._output_dir / filename).resolve()
        if not candidate.is_relative_to(self._output_dir.resolve()):
            raise ValueError(
                f"Output filename '{filename}' escapes the output directory"
            )
        return candidate

    @property
    def downloads_dir(self) -> Path:
        """Directory for auto-downloaded file inputs.

        Created lazily on first access. Separate from ``output_dir``
        to keep downloaded inputs distinct from node-generated outputs.
        """
        if self._downloads_dir is None:
            self._downloads_dir = self._output_dir / "downloads"
            self._downloads_dir.mkdir(parents=True, exist_ok=True)
        return self._downloads_dir

    @property
    def metadata(self) -> dict[str, Any]:
        """Mutable metadata dict for tracking download info and other context.

        The SDK stores download metadata here (original URLs, local paths,
        file sizes). Node authors may also use this for custom metadata.
        """
        return self._metadata

    def report_progress(self, progress: float, message: str = "") -> None:
        """
        Report progress for long-running operations.

        Args:
            progress: Progress value from 0.0 to 1.0
            message: Optional progress message

        Note:
            Currently logs progress. Future: will send to callback/websocket.
        """
        percent = int(progress * 100)
        log_msg = f"Progress: {percent}%"
        if message:
            log_msg += f" - {message}"
        self._logger.info(log_msg)

    def record_token_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        """
        Record actual token usage for this execution.

        Called by nodes that interact with LLM APIs to report
        real token counts instead of the static token_cost.

        Args:
            prompt_tokens: Number of tokens in the prompt
            completion_tokens: Number of tokens in the completion
            total_tokens: Total tokens used
        """
        self._token_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        self._logger.info(
            "Token usage: prompt=%d, completion=%d, total=%d",
            prompt_tokens,
            completion_tokens,
            total_tokens,
        )

    @property
    def token_usage(self) -> dict[str, int]:
        """Token usage recorded during execution, if any."""
        return dict(self._token_usage)
