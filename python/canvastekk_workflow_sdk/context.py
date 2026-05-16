"""
Execution Context

Provides context to the node's execute() method including
run information, output directory, and logging.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from canvastekk_workflow_sdk.logging import get_node_logger

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.request import NodeExecutionRequest


class ExecutionContext:
    """
    Context provided to node execute() method.

    Provides access to:
    - Run and node identifiers
    - Output directory for temporary files
    - Logger with context
    - Progress reporting (for long-running operations)
    """

    def __init__(
        self,
        request: NodeExecutionRequest,
        output_dir: Path | None = None,
    ) -> None:
        self._request = request
        if output_dir is not None:
            self._output_dir = output_dir
        else:
            base_dir = os.environ.get("CANVASTEKK_OUTPUT_DIR")
            if base_dir:
                self._output_dir = Path(base_dir) / request.run_id / request.node_id
            else:
                self._output_dir = Path("/tmp") / request.run_id / request.node_id
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._logger = get_node_logger(request.node_id)

        self._token_usage: dict[str, int] = {}

    @property
    def run_id(self) -> str:
        """Workflow run identifier."""
        return self._request.run_id

    @property
    def node_id(self) -> str:
        """Node instance ID in workflow."""
        return self._request.node_id

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
        """
        return self._output_dir / filename

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
