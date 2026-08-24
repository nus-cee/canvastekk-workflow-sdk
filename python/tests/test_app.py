"""Tests for FastAPI app factory."""

import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import APIRouter, Depends, Request
from fastapi.testclient import TestClient

from canvastekk_workflow_sdk import BaseNode, ExecutionContext, WorkflowNodeManifest, __version__, create_node_app


class EchoNode(BaseNode):
    """Simple echo node for testing."""

    definition = WorkflowNodeManifest(
        name="echo",
        version="1.0.0",
        title="Echo",
        description="Returns input unchanged",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
        },
        output_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
        },
        token_cost=0.0,
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {"message": inputs.get("message", "")}


class FileProcessingNode(BaseNode):
    """Node that accepts file uploads and scalar inputs."""

    definition = WorkflowNodeManifest(
        name="file-proc",
        version="1.0.0",
        title="File Processor",
        description="Processes uploaded files",
        input_schema={
            "type": "object",
            "properties": {
                "point_cloud": {"type": "string", "format": "file", "description": "Point cloud file"},
                "threshold": {"type": "number", "default": 0.5},
                "iterations": {"type": "integer", "default": 10},
                "verbose": {"type": "boolean", "default": False},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "result_path": {"type": "string", "format": "file"},
            },
        },
        token_cost=0.0,
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if "point_cloud" in inputs:
            # Read the file content to verify it was saved correctly
            file_path = Path(inputs["point_cloud"])
            result["file_content"] = file_path.read_text() if file_path.exists() else ""
            result["file_name"] = file_path.name
        if "threshold" in inputs:
            result["threshold_used"] = inputs["threshold"]
        if "iterations" in inputs:
            result["iterations_used"] = inputs["iterations"]
        if "verbose" in inputs:
            result["verbose_used"] = inputs["verbose"]
        return result


class FailingNode(BaseNode):
    """Node that always fails."""

    definition = WorkflowNodeManifest(
        name="failing",
        version="1.0.0",
        title="Failing",
        description="Always fails",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        raise ValueError("Intentional failure")


class DegradedNode(BaseNode):
    """Node with mixed health checks."""

    definition = WorkflowNodeManifest(
        name="degraded",
        version="1.0.0",
        title="Degraded",
        description="Has degraded health",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {}

    def health_check(self) -> dict[str, Any]:
        return {
            "primary": True,
            "secondary": False,
        }


@pytest.fixture
def echo_client() -> TestClient:
    """Create test client for echo node."""
    node = EchoNode()
    app = create_node_app(node)
    return TestClient(app)


@pytest.fixture
def failing_client() -> TestClient:
    """Create test client for failing node."""
    node = FailingNode()
    app = create_node_app(node)
    return TestClient(app)


@pytest.fixture
def degraded_client() -> TestClient:
    """Create test client for degraded node."""
    node = DegradedNode()
    app = create_node_app(node)
    return TestClient(app)


class TestExecuteEndpoint:
    """Tests for POST /execute endpoint."""

    def test_execute_success(self, echo_client: TestClient) -> None:
        """Test successful execution."""
        response = echo_client.post(
            "/execute",
            json={
                "run_id": "test-run",
                "node_id": "test-node",
                "inputs": {"message": "Hello!"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pass"
        assert data["outputs"] == {"message": "Hello!"}
        assert data["error"] is None
        assert data["execution_id"] is not None
        assert data["duration_ms"] >= 0

    def test_execute_empty_inputs(self, echo_client: TestClient) -> None:
        """Test execution with empty inputs."""
        response = echo_client.post(
            "/execute",
            json={
                "run_id": "test-run",
                "node_id": "test-node",
                "inputs": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pass"
        assert data["outputs"] == {"message": ""}

    def test_execute_failure(self, failing_client: TestClient) -> None:
        """Test execution failure."""
        response = failing_client.post(
            "/execute",
            json={
                "run_id": "test-run",
                "node_id": "test-node",
                "inputs": {},
            },
        )
        assert response.status_code == 200  # Error is in response body, not HTTP status
        data = response.json()
        assert data["status"] == "fail"
        assert data["outputs"] is None
        assert data["error"] == "Intentional failure"
        assert data["error_type"] == "ValueError"

    def test_execute_with_presigned_url_input(self) -> None:
        """Test execution with presigned URL for file input field."""
        node = FileProcessingNode()
        client = TestClient(create_node_app(node))

        with tempfile.NamedTemporaryFile(suffix=".ply", delete=False, mode="w") as f:
            f.write("fake point cloud data")
            local_path = f.name

        try:
            response = client.post(
                "/execute",
                json={
                    "run_id": "run-1",
                    "node_id": "node-1",
                    "inputs": {
                        "point_cloud": local_path,
                    },
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "pass"
            assert "file_content" in data["outputs"]
        finally:
            os.unlink(local_path)


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_healthy(self, echo_client: TestClient) -> None:
        """Test health check for healthy node."""
        response = echo_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["node_id"] == "echo-v1.0.0"
        assert data["version"] == "1.0.0"

    def test_health_degraded(self, degraded_client: TestClient) -> None:
        """Test health check for degraded node."""
        response = degraded_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["primary"] is True
        assert data["checks"]["secondary"] is False


class TestManifestBasic:
    """Basic tests for GET /manifest endpoint."""

    def test_manifest(self, echo_client: TestClient) -> None:
        """Test getting node manifest."""
        response = echo_client.get("/manifest")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "echo-v1.0.0"
        assert data["name"] == "echo"
        assert data["version"] == "1.0.0"
        assert data["title"] == "Echo"
        assert data["description"] == "Returns input unchanged"
        assert data["token_cost"] == 0.0
        assert "input_schema" in data
        assert "output_schema" in data
        assert "default_retry" in data


class FileOutputNode(BaseNode):
    """Node that produces file outputs for S3 upload testing."""

    definition = WorkflowNodeManifest(
        name="file-output",
        version="1.0.0",
        title="File Output",
        description="Produces a file output",
        input_schema={
            "type": "object",
            "properties": {"input_data": {"type": "string"}},
        },
        output_schema={
            "type": "object",
            "properties": {
                "result_path": {"type": "string", "format": "file"},
                "summary": {"type": "string"},
            },
        },
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        # Create a real temp file to simulate binary output
        fd, path = tempfile.mkstemp(suffix=".ply")
        os.close(fd)
        Path(path).write_bytes(b"fake binary output data")
        return {"result_path": path, "summary": "done"}


class FailingOutputNode(BaseNode):
    """Node that always fails — for testing S3 upload skip on failure."""

    definition = WorkflowNodeManifest(
        name="fail-output",
        version="1.0.0",
        title="Fail Output",
        description="Always fails",
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {
                "result_path": {"type": "string", "format": "file"},
            },
        },
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        raise RuntimeError("Node execution failed")


@pytest.fixture
def file_output_client() -> TestClient:
    """Create test client for file output node."""
    node = FileOutputNode()
    app = create_node_app(node)
    return TestClient(app)


@pytest.fixture
def failing_output_client() -> TestClient:
    """Create test client for failing output node."""
    node = FailingOutputNode()
    app = create_node_app(node)
    return TestClient(app)


class TestOutputUploadToS3:
    """Tests for S3 output upload via pre-signed URLs."""

    def test_output_upload_url_triggers_s3_upload(self, file_output_client: TestClient) -> None:
        """When output_upload_url is provided and status=pass, upload_file is called."""
        with patch("canvastekk_workflow_sdk.uploads.S3PresignedUploader.upload_file") as mock_upload:
            response = file_output_client.post(
                "/execute",
                json={
                    "run_id": "run-1",
                    "node_id": "node-1",
                    "inputs": {"input_data": "test"},
                    "output_upload_url": {
                        "result_path": "https://s3.amazonaws.com/presigned-put",
                    },
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "pass"

            mock_upload.assert_called_once()
            call_args = mock_upload.call_args
            assert call_args[0][1] == "https://s3.amazonaws.com/presigned-put"
            uploaded_file = call_args[0][0]
            assert uploaded_file == data["outputs"]["result_path"]

    def test_output_upload_url_skipped_on_failure(self, failing_output_client: TestClient) -> None:
        """When node returns status=fail, upload_file should NOT be called."""
        with patch("canvastekk_workflow_sdk.uploads.S3PresignedUploader.upload_file") as mock_upload:
            response = failing_output_client.post(
                "/execute",
                json={
                    "run_id": "run-1",
                    "node_id": "node-1",
                    "inputs": {},
                    "output_upload_url": {
                        "result_path": "https://s3.amazonaws.com/presigned-put",
                    },
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "fail"

            # Upload should NOT have been called
            mock_upload.assert_not_called()

    def test_output_upload_url_skipped_when_not_provided(self, file_output_client: TestClient) -> None:
        """When output_upload_url is None, no upload is attempted."""
        with patch("canvastekk_workflow_sdk.uploads.S3PresignedUploader.upload_file") as mock_upload:
            response = file_output_client.post(
                "/execute",
                json={
                    "run_id": "run-1",
                    "node_id": "node-1",
                    "inputs": {"input_data": "test"},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "pass"

            # No upload should happen
            mock_upload.assert_not_called()


class TestAsyncExecution:
    """Tests for async execution with asyncio.to_thread (Phase 1)."""

    def test_execute_endpoint_works_with_async_wrapper(self, echo_client: TestClient) -> None:
        """Test that POST /execute works correctly with asyncio.to_thread wrapping."""
        response = echo_client.post(
            "/execute",
            json={
                "run_id": "test-run",
                "node_id": "test-node",
                "inputs": {"message": "Async test"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pass"
        assert data["outputs"] == {"message": "Async test"}
        assert data["error"] is None
        assert data["execution_id"] is not None

    def test_execute_with_failure_still_works_with_async_wrapper(self, failing_client: TestClient) -> None:
        """Test that execution failures are correctly handled with async wrapper."""
        response = failing_client.post(
            "/execute",
            json={
                "run_id": "test-run",
                "node_id": "test-node",
                "inputs": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "fail"
        assert data["outputs"] is None
        assert data["error"] == "Intentional failure"
        assert data["error_type"] == "ValueError"


class TestDependencyInjection:
    """Tests for FastAPI dependency injection (Phase 2)."""

    def test_dependency_applied_to_all_endpoints(self) -> None:
        """Test that a custom dependency is invoked on all endpoints."""
        dependency_invocations: list[str] = []

        def custom_dependency(request: Request) -> None:
            dependency_invocations.append(request.url.path)

        node = EchoNode()
        app = create_node_app(node, dependencies=[Depends(custom_dependency)])
        client = TestClient(app)

        client.get("/health")
        client.get("/manifest")
        client.get("/metrics")
        client.post("/execute", json={"run_id": "r1", "node_id": "n1", "inputs": {"message": "test"}})
        client.post("/hook", json={"event": "test"})

        assert "/health" in dependency_invocations
        assert "/manifest" in dependency_invocations
        assert "/metrics" in dependency_invocations
        assert "/execute" in dependency_invocations
        assert "/hook" in dependency_invocations

    def test_dependency_rejects_invalid_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a dependency can reject requests."""
        monkeypatch.setenv("CANVASTEKK_API_KEY", "correct-key")

        from canvastekk_workflow_sdk.auth import NodeAuth

        auth = NodeAuth.api_key()
        node = EchoNode()
        app = create_node_app(node, dependencies=[Depends(auth)])
        client = TestClient(app)

        response = client.get("/health", headers={})
        assert response.status_code == 401

        response = client.get("/health", headers={"X-API-Key": "correct-key"})
        assert response.status_code == 200

    def test_multiple_dependencies_all_invoked(self) -> None:
        """Test that multiple dependencies are all invoked."""
        dependency_order: list[str] = []

        def dep1(request: Request) -> None:
            dependency_order.append("dep1")

        def dep2(request: Request) -> None:
            dependency_order.append("dep2")

        node = EchoNode()
        app = create_node_app(node, dependencies=[Depends(dep1), Depends(dep2)])
        client = TestClient(app)

        client.get("/health")
        assert dependency_order == ["dep1", "dep2"]

    def test_empty_dependencies_list(self) -> None:
        """Test that empty dependencies list works."""
        node = EchoNode()
        app = create_node_app(node, dependencies=[])
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200


class TestExtraRoutes:
    """Tests for extra routes feature (Phase 2)."""

    def test_extra_route_accessible(self) -> None:
        """Test that a custom route is accessible on the created app."""
        extra_router = APIRouter(prefix="/custom", tags=["Custom"])

        @extra_router.get("/info")
        def custom_info() -> dict[str, str]:
            return {"message": "Custom endpoint"}

        node = EchoNode()
        app = create_node_app(node, extra_routes=[extra_router])
        client = TestClient(app)

        response = client.get("/custom/info")
        assert response.status_code == 200
        assert response.json() == {"message": "Custom endpoint"}

    def test_multiple_extra_routes_accessible(self) -> None:
        """Test that multiple extra routers are all accessible."""
        router1 = APIRouter(prefix="/api/v1", tags=["V1"])

        @router1.get("/data")
        def get_v1_data() -> dict[str, str]:
            return {"version": "v1"}

        router2 = APIRouter(prefix="/api/v2", tags=["V2"])

        @router2.get("/data")
        def get_v2_data() -> dict[str, str]:
            return {"version": "v2"}

        node = EchoNode()
        app = create_node_app(node, extra_routes=[router1, router2])
        client = TestClient(app)

        response1 = client.get("/api/v1/data")
        assert response1.status_code == 200
        assert response1.json() == {"version": "v1"}

        response2 = client.get("/api/v2/data")
        assert response2.status_code == 200
        assert response2.json() == {"version": "v2"}

    def test_standard_routes_still_work_with_extra_routes(self) -> None:
        """Test that standard routes still work when extra routes are added."""
        extra_router = APIRouter(prefix="/extra")

        @extra_router.get("/test")
        def extra_test() -> dict[str, str]:
            return {"extra": "route"}

        node = EchoNode()
        app = create_node_app(node, extra_routes=[extra_router])
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200

        response = client.get("/manifest")
        assert response.status_code == 200

        response = client.get("/metrics")
        assert response.status_code == 200

    def test_extra_routes_with_dependencies(self) -> None:
        """Test that extra routes work alongside app dependencies."""
        dependency_invoked: list[bool] = []

        def custom_dependency(request: Request) -> None:
            dependency_invoked.append(True)

        extra_router = APIRouter(prefix="/custom")

        @extra_router.get("/test")
        def custom_test() -> dict[str, str]:
            return {"test": "data"}

        node = EchoNode()
        app = create_node_app(node, dependencies=[Depends(custom_dependency)], extra_routes=[extra_router])
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        assert len(dependency_invoked) == 1

        response = client.get("/custom/test")
        assert response.status_code == 200
        assert len(dependency_invoked) == 1

    def test_empty_extra_routes_list(self) -> None:
        """Test that empty extra routes list works."""
        node = EchoNode()
        app = create_node_app(node, extra_routes=[])
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200


class TestApiKeyAuthIntegration:
    """Tests for API Key authentication integration with FastAPI endpoints (Phase 2)."""

    def test_api_key_auth_allows_valid_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that valid API key allows access to all endpoints."""
        from canvastekk_workflow_sdk.auth import NodeAuth

        monkeypatch.setenv("CANVASTEKK_API_KEY", "test-secret-key")

        auth = NodeAuth.api_key()
        node = EchoNode()
        app = create_node_app(node, dependencies=[Depends(auth)])
        client = TestClient(app)

        headers = {"X-API-Key": "test-secret-key"}

        response = client.get("/health", headers=headers)
        assert response.status_code == 200

        response = client.get("/manifest", headers=headers)
        assert response.status_code == 200

        response = client.get("/metrics", headers=headers)
        assert response.status_code == 200

        response = client.post(
            "/execute", json={"run_id": "r1", "node_id": "n1", "inputs": {"message": "test"}}, headers=headers
        )
        assert response.status_code == 200

        response = client.post("/hook", json={"event": "test"}, headers=headers)
        assert response.status_code == 501

    def test_api_key_auth_rejects_invalid_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid API key is rejected."""
        from canvastekk_workflow_sdk.auth import NodeAuth

        monkeypatch.setenv("CANVASTEKK_API_KEY", "correct-key")

        auth = NodeAuth.api_key()
        node = EchoNode()
        app = create_node_app(node, dependencies=[Depends(auth)])
        client = TestClient(app)

        headers = {"X-API-Key": "wrong-key"}

        response = client.get("/health", headers=headers)
        assert response.status_code == 401

        response = client.post(
            "/execute", json={"run_id": "r1", "node_id": "n1", "inputs": {"message": "test"}}, headers=headers
        )
        assert response.status_code == 401

    def test_api_key_auth_rejects_missing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that missing API key is rejected."""
        from canvastekk_workflow_sdk.auth import NodeAuth

        monkeypatch.setenv("CANVASTEKK_API_KEY", "test-key")

        auth = NodeAuth.api_key()
        node = EchoNode()
        app = create_node_app(node, dependencies=[Depends(auth)])
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 401

    def test_api_key_auth_rejects_when_env_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that auth is rejected when env var is not set."""
        from canvastekk_workflow_sdk.auth import NodeAuth

        monkeypatch.delenv("CANVASTEKK_API_KEY", raising=False)

        auth = NodeAuth.api_key()
        node = EchoNode()
        app = create_node_app(node, dependencies=[Depends(auth)])
        client = TestClient(app)

        headers = {"X-API-Key": "any-key"}

        response = client.get("/health", headers=headers)
        assert response.status_code == 401

    def test_api_key_auth_bypass_in_dev_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that dev mode bypasses API key authentication."""
        from canvastekk_workflow_sdk.auth import NodeAuth

        monkeypatch.setenv("CANVASTEKK_DEV_MODE", "true")
        monkeypatch.delenv("CANVASTEKK_API_KEY", raising=False)

        auth = NodeAuth.api_key()
        node = EchoNode()
        app = create_node_app(node, dependencies=[Depends(auth)])
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200

    def test_api_key_auth_custom_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test API key auth with custom env var name."""
        from canvastekk_workflow_sdk.auth import NodeAuth

        monkeypatch.setenv("MY_CUSTOM_API_KEY", "custom-secret")

        auth = NodeAuth.api_key(key_env_var="MY_CUSTOM_API_KEY")
        node = EchoNode()
        app = create_node_app(node, dependencies=[Depends(auth)])
        client = TestClient(app)

        headers = {"X-API-Key": "custom-secret"}

        response = client.get("/health", headers=headers)
        assert response.status_code == 200


class TestIntegrationLifecycle:
    """Full integration test: auth + execute + S3 upload + lifecycle hooks."""

    def test_full_lifecycle_with_api_key_auth_and_s3_upload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from canvastekk_workflow_sdk.auth import NodeAuth

        monkeypatch.setenv("CANVASTEKK_API_KEY", "test-integration-key")

        auth = NodeAuth.api_key()
        node = FileOutputNode()
        startup_called: list[bool] = []
        shutdown_called: list[bool] = []

        original_startup = node.on_startup
        original_shutdown = node.on_shutdown

        async def custom_startup() -> None:
            startup_called.append(True)
            await original_startup()

        async def custom_shutdown() -> None:
            shutdown_called.append(True)
            await original_shutdown()

        node.on_startup = custom_startup
        node.on_shutdown = custom_shutdown

        app = create_node_app(node, dependencies=[Depends(auth)])
        headers = {"X-API-Key": "test-integration-key"}

        with TestClient(app) as client:
            assert startup_called

            response = client.get("/health", headers=headers)
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

            response = client.get("/manifest", headers=headers)
            assert response.status_code == 200
            assert response.json()["name"] == "file-output"

            with patch("canvastekk_workflow_sdk.uploads.S3PresignedUploader.upload_file") as mock_upload:
                response = client.post(
                    "/execute",
                    json={
                        "run_id": "integration-run",
                        "node_id": "integration-node",
                        "inputs": {"input_data": "integration test"},
                        "output_upload_url": {
                            "result_path": "https://s3.amazonaws.com/presigned-put",
                        },
                    },
                    headers=headers,
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "pass"
            assert data["outputs"]["summary"] == "done"
            mock_upload.assert_called_once()

            response = client.get(
                "/execute",
                headers=headers,
            )
            assert response.status_code == 405

            no_auth_response = client.post(
                "/execute",
                json={
                    "run_id": "integration-run",
                    "node_id": "integration-node",
                    "inputs": {"input_data": "should fail"},
                },
            )
            assert no_auth_response.status_code == 401

        assert shutdown_called


class TestManifestEndpoint:
    def test_manifest_includes_sdk_version(self, echo_client: TestClient) -> None:
        response = echo_client.get("/manifest")
        assert response.status_code == 200
        data = response.json()
        assert "sdk_version" in data
        assert data["sdk_version"] == __version__

    def test_manifest_includes_node_fields(self, echo_client: TestClient) -> None:
        response = echo_client.get("/manifest")
        data = response.json()
        assert data["name"] == "echo"
        assert data["version"] == "1.0.0"
        assert data["id"] == "echo-v1.0.0"
        assert "input_schema" in data
        assert "output_schema" in data

    def test_manifest_defaults_to_dev_mode(self, echo_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CANVASTEKK_NODE_ENV", raising=False)
        response = echo_client.get("/manifest")
        assert response.json()["mode"] == "dev"

    def test_manifest_dev_mode(self, echo_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CANVASTEKK_NODE_ENV", "dev")
        response = echo_client.get("/manifest")
        assert response.json()["mode"] == "dev"

    def test_manifest_development_mode(self, echo_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CANVASTEKK_NODE_ENV", "development")
        response = echo_client.get("/manifest")
        assert response.json()["mode"] == "dev"

    def test_manifest_staging_mode(self, echo_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CANVASTEKK_NODE_ENV", "staging")
        response = echo_client.get("/manifest")
        assert response.json()["mode"] == "uat"

    def test_manifest_uat_mode(self, echo_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CANVASTEKK_NODE_ENV", "uat")
        response = echo_client.get("/manifest")
        assert response.json()["mode"] == "uat"

    def test_manifest_production_mode(self, echo_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CANVASTEKK_NODE_ENV", "production")
        response = echo_client.get("/manifest")
        assert response.json()["mode"] == "production"

    def test_manifest_unknown_env_maps_to_production(
        self, echo_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CANVASTEKK_NODE_ENV", "qa")
        response = echo_client.get("/manifest")
        assert response.json()["mode"] == "production"


class TestSDKVersionHeader:
    def test_sdk_version_header_on_execute(self, echo_client: TestClient) -> None:
        response = echo_client.post(
            "/execute",
            json={"run_id": "r1", "node_id": "n1", "inputs": {"message": "hi"}},
        )
        assert response.headers.get("x-sdk-version") == __version__

    def test_sdk_version_header_on_manifest(self, echo_client: TestClient) -> None:
        response = echo_client.get("/manifest")
        assert response.headers.get("x-sdk-version") == __version__

    def test_sdk_version_header_on_health(self, echo_client: TestClient) -> None:
        response = echo_client.get("/health")
        assert response.headers.get("x-sdk-version") == __version__


class TestLivenessProbe:
    def test_liveness_returns_200(self, echo_client: TestClient) -> None:
        response = echo_client.get("/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}


class TestReadinessProbe:
    def test_readiness_returns_200_when_no_checks(self, echo_client: TestClient) -> None:
        response = echo_client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"] == {}

    def test_readiness_returns_200_when_all_checks_pass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class HealthyNode(BaseNode):
            definition = WorkflowNodeManifest(
                name="healthy",
                version="1.0.0",
                title="Healthy",
                description="Always healthy",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

            def health_check(self) -> dict[str, Any]:
                return {"db": True, "cache": True}

            def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
                return {}

        client = TestClient(create_node_app(HealthyNode()))
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_readiness_returns_503_when_check_fails(self) -> None:
        class UnhealthyNode(BaseNode):
            definition = WorkflowNodeManifest(
                name="unhealthy",
                version="1.0.0",
                title="Unhealthy",
                description="Always unhealthy",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            )

            def health_check(self) -> dict[str, Any]:
                return {"db": True, "model": False}

            def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
                return {}

        client = TestClient(create_node_app(UnhealthyNode()))
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"


class TestBodyLimitAndRedaction:
    """DA-1711 3.2/3.3: body-limit middleware, 4xx body-parse mapping,
    generic 500s."""

    def test_oversized_body_rejected_413(self, echo_client, monkeypatch):
        import json as jsonlib

        monkeypatch.setenv("CANVASTEKK_MAX_BODY_BYTES", "1000")
        big = "x" * 2000
        resp = echo_client.post(
            "/execute",
            content=jsonlib.dumps({"run_id": "r1", "node_id": "n1", "inputs": {"msg": big}}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 413

    def test_list_body_rejected_422(self, echo_client):
        resp = echo_client.post(
            "/execute",
            content="[1,2,3]",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_invalid_fields_rejected_422(self, echo_client):
        resp = echo_client.post(
            "/execute",
            content='{"run_id": "../../etc", "node_id": "n1"}',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_hook_invalid_json_400(self, echo_client):
        resp = echo_client.post("/hook", content="not json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 400

    def test_traversal_run_id_rejected_422(self, echo_client):
        resp = echo_client.post(
            "/execute",
            content='{"run_id": "../../etc", "node_id": "n1", "inputs": {}}',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


class TestCreateNodeAppAuthParam:
    """Tests for the auth= shorthand on create_node_app (DA-1955)."""

    def test_api_key_shorthand_requires_key_on_execute(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """auth='api-key' rejects unauthenticated /execute and accepts the key."""

        monkeypatch.setenv("CANVASTEKK_API_KEY", "test-key-123")
        app = create_node_app(EchoNode(), auth="api-key")
        client = TestClient(app)

        unauthenticated = client.post("/execute", json={"run_id": "r1", "node_id": "n1", "inputs": {}})
        assert unauthenticated.status_code == 401

        authenticated = client.post(
            "/execute",
            json={"run_id": "r1", "node_id": "n1", "inputs": {}},
            headers={"X-API-Key": "test-key-123"},
        )
        assert authenticated.status_code == 200

    def test_auth_none_keeps_current_behavior(self) -> None:
        """auth=None leaves every endpoint unauthenticated (default)."""
        app = create_node_app(EchoNode(), auth=None)
        client = TestClient(app)

        resp = client.post("/execute", json={"run_id": "r1", "node_id": "n1", "inputs": {}})
        assert resp.status_code == 200

    def test_node_auth_instance_honored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An explicit NodeAuth instance is used directly."""
        from canvastekk_workflow_sdk.auth import NodeAuth

        monkeypatch.setenv("CANVASTEKK_API_KEY", "test-key-123")
        app = create_node_app(EchoNode(), auth=NodeAuth.api_key())
        client = TestClient(app)

        with_key = client.post(
            "/execute",
            json={"run_id": "r1", "node_id": "n1", "inputs": {}},
            headers={"X-API-Key": "test-key-123"},
        )
        assert with_key.status_code == 200

    def test_unknown_shorthand_raises(self) -> None:
        """Unknown strings raise ValueError with the valid options."""
        with pytest.raises(ValueError, match="api-key"):
            create_node_app(EchoNode(), auth="oauth")  # type: ignore[arg-type]

    def test_dependencies_and_auth_merge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Custom dependencies and auth coexist on the same router."""
        from fastapi import Depends

        monkeypatch.setenv("CANVASTEKK_API_KEY", "test-key-123")
        calls: list[str] = []

        def custom_dep() -> None:
            calls.append("custom_dep")

        app = create_node_app(EchoNode(), dependencies=[Depends(custom_dep)], auth="api-key")
        client = TestClient(app)

        resp = client.post(
            "/execute",
            json={"run_id": "r1", "node_id": "n1", "inputs": {}},
            headers={"X-API-Key": "test-key-123"},
        )
        assert resp.status_code == 200
        assert calls == ["custom_dep"]

    def test_auth_skipped_when_dependencies_already_authed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Existing auth backend in dependencies wins; auth= is skipped."""
        from canvastekk_workflow_sdk.auth import NodeAuth

        monkeypatch.setenv("CANVASTEKK_API_KEY", "test-key-123")
        explicit = NodeAuth.api_key()
        app = create_node_app(EchoNode(), dependencies=[Depends(explicit)], auth="api-key")
        client = TestClient(app)

        with_key = client.post(
            "/execute",
            json={"run_id": "r1", "node_id": "n1", "inputs": {}},
            headers={"X-API-Key": "test-key-123"},
        )
        assert with_key.status_code == 200
