

class TestSlugValidation:
    """run_id/node_id slug constraints (DA-1711 3.1) — ids flow into
    /tmp/{run_id}/{node_id} paths, so traversal payloads must be rejected
    at the validation layer."""

    def test_dotdot_run_id_rejected(self) -> None:
        import pytest

        from canvastekk_workflow_sdk.request import NodeExecutionRequest

        with pytest.raises(Exception):
            NodeExecutionRequest(run_id="../../etc", node_id="n1", inputs={})

    def test_dotdot_node_id_rejected(self) -> None:
        import pytest

        from canvastekk_workflow_sdk.request import NodeExecutionRequest

        with pytest.raises(Exception):
            NodeExecutionRequest(run_id="r1", node_id="..", inputs={})

    def test_absolute_ish_id_rejected(self) -> None:
        import pytest

        from canvastekk_workflow_sdk.request import NodeExecutionRequest

        with pytest.raises(Exception):
            NodeExecutionRequest(run_id="/abs/path", node_id="n1", inputs={})

    def test_valid_slug_accepted(self) -> None:
        from canvastekk_workflow_sdk.request import NodeExecutionRequest

        req = NodeExecutionRequest(run_id="run-abc.123_x", node_id="node.1-y", inputs={})
        assert req.run_id == "run-abc.123_x"
