"""Tests for ExecutionContext."""

import logging
from pathlib import Path

import pytest

from canvastekk_workflow_sdk import NodeExecutionRequest
from canvastekk_workflow_sdk.context import ExecutionContext


@pytest.fixture
def exec_request() -> NodeExecutionRequest:
    return NodeExecutionRequest(
        run_id="run-123",
        node_id="node-456",
        inputs={"key": "value"},
    )


@pytest.fixture
def context(exec_request: NodeExecutionRequest) -> ExecutionContext:
    return ExecutionContext(exec_request)


class TestExecutionContext:
    def test_run_id(self, context: ExecutionContext) -> None:
        assert context.run_id == "run-123"

    def test_node_id(self, context: ExecutionContext) -> None:
        assert context.node_id == "node-456"

    def test_output_dir_created(self, context: ExecutionContext) -> None:
        assert context.output_dir.exists()
        assert context.output_dir.is_dir()

    def test_output_dir_contains_run_and_node(self, context: ExecutionContext) -> None:
        assert "run-123" in str(context.output_dir)
        assert "node-456" in str(context.output_dir)

    def test_custom_output_dir(self, exec_request: NodeExecutionRequest, tmp_path: Path) -> None:
        custom_dir = tmp_path / "custom_output"
        ctx = ExecutionContext(exec_request, output_dir=custom_dir)
        assert ctx.output_dir == custom_dir
        assert custom_dir.exists()

    def test_logger_is_configured(self, context: ExecutionContext) -> None:
        assert isinstance(context.logger, logging.Logger)
        assert "node-456" in context.logger.name

    def test_output_path(self, context: ExecutionContext) -> None:
        path = context.output_path("result.ply")
        assert path.name == "result.ply"
        assert path.parent == context.output_dir

    def test_report_progress(self, context: ExecutionContext) -> None:
        context.report_progress(0.5, "halfway done")

    def test_report_progress_full(self, context: ExecutionContext) -> None:
        context.report_progress(1.0)


class TestTokenUsage:
    def test_initial_token_usage_empty(self, context: ExecutionContext) -> None:
        assert context.token_usage == {}

    def test_record_token_usage(self, context: ExecutionContext) -> None:
        context.record_token_usage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        assert context.token_usage == {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }

    def test_token_usage_returns_copy(self, context: ExecutionContext) -> None:
        context.record_token_usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        usage = context.token_usage
        usage["prompt_tokens"] = 999
        assert context.token_usage["prompt_tokens"] == 10

    def test_record_token_usage_overwrites(self, context: ExecutionContext) -> None:
        context.record_token_usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        context.record_token_usage(prompt_tokens=200, completion_tokens=100, total_tokens=300)
        assert context.token_usage["total_tokens"] == 300

    def test_record_token_usage_defaults(self, context: ExecutionContext) -> None:
        context.record_token_usage()
        assert context.token_usage == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }


class TestOutputDirEnvironmentVariable:
    """Tests for CANVASTEKK_OUTPUT_DIR environment variable (Phase 1)."""

    def test_output_dir_uses_env_var_when_set(
        self, exec_request: NodeExecutionRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that CANVASTEKK_OUTPUT_DIR env var overrides /tmp."""
        monkeypatch.setenv("CANVASTEKK_OUTPUT_DIR", str(tmp_path))
        ctx = ExecutionContext(exec_request)
        assert tmp_path in ctx.output_dir.parents
        assert exec_request.run_id in str(ctx.output_dir)
        assert exec_request.node_id in str(ctx.output_dir)

    def test_output_dir_fallback_to_tmp_when_env_not_set(
        self, exec_request: NodeExecutionRequest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that /tmp is used when CANVASTEKK_OUTPUT_DIR is not set."""
        monkeypatch.delenv("CANVASTEKK_OUTPUT_DIR", raising=False)
        ctx = ExecutionContext(exec_request)
        assert Path("/tmp") in ctx.output_dir.parents
        assert exec_request.run_id in str(ctx.output_dir)
        assert exec_request.node_id in str(ctx.output_dir)

    def test_custom_output_dir_overrides_env_var(
        self, exec_request: NodeExecutionRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that explicit output_dir parameter overrides env var."""
        monkeypatch.setenv("CANVASTEKK_OUTPUT_DIR", "/tmp/should-not-use")
        custom_dir = tmp_path / "custom"
        ctx = ExecutionContext(exec_request, output_dir=custom_dir)
        assert ctx.output_dir == custom_dir
        assert "/tmp/should-not-use" not in str(ctx.output_dir)


class TestAccountIdProperty:
    """DA-2242: ExecutionContext.account_id surfaces the request value."""

    def test_returns_request_account_id(self) -> None:
        req = NodeExecutionRequest(run_id="r1", node_id="n1", inputs={}, account_id=7)
        assert ExecutionContext(req).account_id == 7

    def test_none_when_request_has_none(self, context: ExecutionContext) -> None:
        assert context.account_id is None

    def test_none_without_request(self) -> None:
        assert ExecutionContext(run_id="r1", node_id="n1").account_id is None
