"""
Tests for Echo Node example.

Demonstrates unit and integration testing patterns for nodes with file I/O.
"""

from pathlib import Path
from unittest.mock import patch

from canvastekk_workflow_sdk import NodeExecutionRequest

from handler import EchoNode, app, definition

import pytest
from fastapi.testclient import TestClient


class TestEchoNodeUnit:
    def test_definition_file_fields(self):
        assert definition.file_input_fields == ["input_file"]
        assert definition.file_output_fields == ["output_file"]

    def test_definition_format(self):
        props = definition.input_schema["properties"]["input_file"]
        assert props["format"] == "file"
        assert props["type"] == "string"

    def test_definition_extensions(self):
        props = definition.input_schema["properties"]["input_file"]
        assert props["x-accept"] == [".txt", ".csv", ".json"]
        assert props["x-maxSizeBytes"] == 10485760

    @patch("canvastekk_workflow_sdk.base.httpx.get")
    def test_execute_returns_output_path(self, mock_get, tmp_path):
        input_content = b"hello world"

        class MockResponse:
            status_code = 200
            headers = {}

            def iter_bytes(self, chunk_size):
                yield input_content

        mock_get.return_value = MockResponse()

        node = EchoNode()
        request = NodeExecutionRequest(
            run_id="test-run",
            node_id="echo-1",
            inputs={"input_file": "https://example.com/test.txt"},
        )
        response = node.run(request)

        assert response.status == "pass"
        assert response.outputs is not None
        assert "output_file" in response.outputs


class TestEchoNodeAPI:
    client = TestClient(app)

    def test_health(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["node_id"] == "echo-v1.0.0"

    def test_manifest(self):
        resp = self.client.get("/manifest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "echo"
        input_file = data["input_schema"]["properties"]["input_file"]
        assert input_file["format"] == "file"
        assert input_file["x-accept"] == [".txt", ".csv", ".json"]

    @patch("canvastekk_workflow_sdk.base.httpx.get")
    def test_execute_json(self, mock_get):
        input_content = b"test content"

        class MockResponse:
            status_code = 200
            headers = {}

            def iter_bytes(self, chunk_size):
                yield input_content

        mock_get.return_value = MockResponse()

        resp = self.client.post(
            "/execute",
            json={
                "run_id": "run-1",
                "node_id": "echo-1",
                "inputs": {"input_file": "https://example.com/test.txt"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pass"
        assert "output_file" in data["outputs"]
