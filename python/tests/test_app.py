"""Tests for FastAPI app factory."""

import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from canvastekk_workflow_sdk import BaseNode, ExecutionContext, NodeDefinition, create_node_app
from canvastekk_workflow_sdk.app import _coerce_form_value


class EchoNode(BaseNode):
    """Simple echo node for testing."""

    definition = NodeDefinition(
        id="echo-v1.0.0",
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

    definition = NodeDefinition(
        id="file-proc-v1.0.0",
        name="file-proc",
        version="1.0.0",
        title="File Processor",
        description="Processes uploaded files",
        input_schema={
            "type": "object",
            "properties": {
                "point_cloud": {"type": "string", "format": "binary", "description": "Point cloud file"},
                "threshold": {"type": "number", "default": 0.5},
                "iterations": {"type": "integer", "default": 10},
                "verbose": {"type": "boolean", "default": False},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "result_path": {"type": "string"},
                "threshold_used": {"type": "number"},
            },
        },
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

    definition = NodeDefinition(
        id="failing-v1.0.0",
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

    definition = NodeDefinition(
        id="degraded-v1.0.0",
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


@pytest.fixture
def file_proc_client() -> TestClient:
    """Create test client for file processing node."""
    node = FileProcessingNode()
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


class TestMultipartExecuteEndpoint:
    """Tests for POST /execute with multipart/form-data."""

    def test_multipart_with_file_upload(self, file_proc_client: TestClient) -> None:
        """Test multipart execution with a file upload."""
        file_content = b"x,y,z\n1.0,2.0,3.0\n4.0,5.0,6.0"
        response = file_proc_client.post(
            "/execute",
            data={
                "run_id": "test-run",
                "node_id": "test-node",
            },
            files={
                "point_cloud": ("cloud.csv", io.BytesIO(file_content), "text/csv"),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pass"
        assert data["outputs"]["file_content"] == file_content.decode()
        assert data["outputs"]["file_name"] == "cloud.csv"

    def test_multipart_with_mixed_inputs(self, file_proc_client: TestClient) -> None:
        """Test multipart execution with file + scalar inputs."""
        file_content = b"point cloud data"
        response = file_proc_client.post(
            "/execute",
            data={
                "run_id": "test-run",
                "node_id": "test-node",
                "threshold": "0.75",
                "iterations": "20",
                "verbose": "true",
            },
            files={
                "point_cloud": ("data.ply", io.BytesIO(file_content), "application/octet-stream"),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pass"
        outputs = data["outputs"]
        assert outputs["file_content"] == "point cloud data"
        assert outputs["file_name"] == "data.ply"
        assert outputs["threshold_used"] == 0.75
        assert outputs["iterations_used"] == 20
        assert outputs["verbose_used"] is True

    def test_json_still_works(self, file_proc_client: TestClient) -> None:
        """Test that JSON payloads still work (backward compatibility)."""
        response = file_proc_client.post(
            "/execute",
            json={
                "run_id": "test-run",
                "node_id": "test-node",
                "inputs": {"threshold": 0.9},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pass"
        assert data["outputs"]["threshold_used"] == 0.9


class TestCoerceFormValue:
    """Tests for _coerce_form_value helper."""

    def test_coerce_number(self) -> None:
        assert _coerce_form_value("x", "3.14", {"type": "number"}) == 3.14

    def test_coerce_integer(self) -> None:
        assert _coerce_form_value("x", "42", {"type": "integer"}) == 42

    def test_coerce_boolean_true(self) -> None:
        assert _coerce_form_value("x", "true", {"type": "boolean"}) is True

    def test_coerce_boolean_yes(self) -> None:
        assert _coerce_form_value("x", "yes", {"type": "boolean"}) is True

    def test_coerce_boolean_one(self) -> None:
        assert _coerce_form_value("x", "1", {"type": "boolean"}) is True

    def test_coerce_boolean_false(self) -> None:
        assert _coerce_form_value("x", "false", {"type": "boolean"}) is False

    def test_coerce_string(self) -> None:
        assert _coerce_form_value("x", "hello", {"type": "string"}) == "hello"

    def test_coerce_no_type(self) -> None:
        """No type in schema defaults to string passthrough."""
        assert _coerce_form_value("x", "hello", {}) == "hello"


class TestDefinitionEndpoint:
    """Tests for GET /definition endpoint."""

    def test_definition(self, echo_client: TestClient) -> None:
        """Test getting node definition."""
        response = echo_client.get("/definition")
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
    """Node that produces binary file outputs for S3 upload testing."""

    definition = NodeDefinition(
        id="file-output-v1.0.0",
        name="file-output",
        version="1.0.0",
        title="File Output",
        description="Produces a binary file output",
        input_schema={
            "type": "object",
            "properties": {"input_data": {"type": "string"}},
        },
        output_schema={
            "type": "object",
            "properties": {
                "result_path": {"type": "string", "format": "binary"},
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

    definition = NodeDefinition(
        id="fail-output-v1.0.0",
        name="fail-output",
        version="1.0.0",
        title="Fail Output",
        description="Always fails",
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {
                "result_path": {"type": "string", "format": "binary"},
            },
        },
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        raise RuntimeError("Node execution failed")


class FileInOutNode(BaseNode):
    """Node with both binary input and binary output for multipart + S3 upload tests."""

    definition = NodeDefinition(
        id="file-inout-v1.0.0",
        name="file-inout",
        version="1.0.0",
        title="File In/Out",
        description="Accepts file input and produces file output",
        input_schema={
            "type": "object",
            "properties": {
                "point_cloud": {"type": "string", "format": "binary"},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "result_path": {"type": "string", "format": "binary"},
            },
        },
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        fd, path = tempfile.mkstemp(suffix=".ply")
        os.close(fd)
        Path(path).write_bytes(b"output data")
        return {"result_path": path}


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
        """When output_upload_url is provided and status=pass, _upload_to_presigned is called."""
        with patch("canvastekk_workflow_sdk.app._upload_to_presigned") as mock_upload:
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

            # Verify _upload_to_presigned was called with the file path and presigned URL
            mock_upload.assert_called_once()
            call_args = mock_upload.call_args
            assert call_args[0][1] == "https://s3.amazonaws.com/presigned-put"
            # First arg is the file path — verify it exists
            uploaded_file = call_args[0][0]
            assert uploaded_file == data["outputs"]["result_path"]

    def test_output_upload_url_skipped_on_failure(self, failing_output_client: TestClient) -> None:
        """When node returns status=fail, _upload_to_presigned should NOT be called."""
        with patch("canvastekk_workflow_sdk.app._upload_to_presigned") as mock_upload:
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
        with patch("canvastekk_workflow_sdk.app._upload_to_presigned") as mock_upload:
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

    def test_multipart_output_upload_url_parsed_from_json(self) -> None:
        """When output_upload_url is sent as JSON string in multipart form data, it's correctly parsed."""
        node = FileInOutNode()
        client = TestClient(create_node_app(node))
        upload_urls = {"result_path": "https://s3.amazonaws.com/presigned-put"}

        file_content = b"point cloud data"
        with patch("canvastekk_workflow_sdk.app._upload_to_presigned") as mock_upload:
            response = client.post(
                "/execute",
                data={
                    "run_id": "run-1",
                    "node_id": "node-1",
                    "output_upload_url": json.dumps(upload_urls),
                },
                files={
                    "point_cloud": ("cloud.ply", io.BytesIO(file_content), "application/octet-stream"),
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "pass"

            # Verify upload was triggered (parsed from JSON string in form data)
            mock_upload.assert_called_once()
            call_args = mock_upload.call_args
            assert call_args[0][1] == "https://s3.amazonaws.com/presigned-put"
