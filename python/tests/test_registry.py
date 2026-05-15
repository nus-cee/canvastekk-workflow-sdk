"""Tests for registry helper."""

import json
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from canvastekk_workflow_sdk import NodeDefinition
from canvastekk_workflow_sdk.base import BaseNode
from canvastekk_workflow_sdk.context import ExecutionContext
from canvastekk_workflow_sdk.registry import RegistrationError, register_node


class DummyNode(BaseNode):
    definition = NodeDefinition(
        id="test-v1.0.0",
        name="test",
        version="1.0.0",
        title="Test Node",
        description="A test node",
        input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"output": {"type": "string"}}},
    )

    def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        return {"output": inputs.get("input", "")}


class TestRegisterNode:
    """Tests for register_node function."""

    def test_successful_registration_returns_parsed_response(self) -> None:
        """Test that successful registration returns parsed JSON response."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        response_body = {"id": "node-123", "status": "registered"}

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_body).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("canvastekk_workflow_sdk.registry.urllib.request.urlopen", return_value=mock_response):
            result = register_node(node, registry_url)

        assert result == response_body

    def test_posts_correct_manifest_json(self) -> None:
        """Test that POSTs correct manifest JSON with all required fields."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        invoke_url = "https://node.example.com"
        api_key = "secret-key"

        captured_request: Any = None

        def capture_request(req: Any, **kwargs: Any) -> MagicMock:
            nonlocal captured_request
            captured_request = req
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"id":"123"}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("canvastekk_workflow_sdk.registry.urllib.request.urlopen", side_effect=capture_request):
            register_node(node, registry_url, invoke_url=invoke_url, api_key=api_key)

        assert captured_request is not None
        assert captured_request.method == "POST"
        assert captured_request.full_url == registry_url

        request_body = json.loads(captured_request.data)
        assert request_body["name"] == "test"
        assert request_body["version"] == "1.0.0"
        assert request_body["title"] == "Test Node"
        assert request_body["invoke_type"] == "http"
        assert request_body["invoke_url"] == invoke_url

    def test_includes_api_key_header_when_provided(self) -> None:
        """Test that X-API-Key header is included when api_key is provided."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        api_key = "secret-key"

        captured_request: Any = None

        def capture_request(req: Any, **kwargs: Any) -> MagicMock:
            nonlocal captured_request
            captured_request = req
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"id":"123"}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("canvastekk_workflow_sdk.registry.urllib.request.urlopen", side_effect=capture_request):
            register_node(node, registry_url, api_key=api_key)

        assert captured_request is not None
        headers_lower = {k.lower(): v for k, v in captured_request.headers.items()}
        assert "x-api-key" in headers_lower
        assert headers_lower["x-api-key"] == api_key

    def test_omits_api_key_header_when_not_provided(self) -> None:
        """Test that X-API-Key header is omitted when api_key is not provided."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        captured_request: Any = None

        def capture_request(req: Any, **kwargs: Any) -> MagicMock:
            nonlocal captured_request
            captured_request = req
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"id":"123"}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("canvastekk_workflow_sdk.registry.urllib.request.urlopen", side_effect=capture_request):
            register_node(node, registry_url)

        assert captured_request is not None
        headers_lower = {k.lower(): v for k, v in captured_request.headers.items()}
        assert "x-api-key" not in headers_lower

    def test_raises_registration_error_on_network_failure(self) -> None:
        """Test that RegistrationError is raised on network failure."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        with patch(
            "canvastekk_workflow_sdk.registry.urllib.request.urlopen",
            side_effect=URLError("Network error"),
        ):
            with pytest.raises(RegistrationError) as exc_info:
                register_node(node, registry_url)

        assert "Registration failed" in str(exc_info.value)
        assert exc_info.value.status_code is None
        assert exc_info.value.body is None

    def test_raises_registration_error_on_http_401(self) -> None:
        """Test that RegistrationError is raised on HTTP 401 error."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        error = HTTPError(
            url=registry_url,
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

        with patch("canvastekk_workflow_sdk.registry.urllib.request.urlopen", side_effect=error):
            with pytest.raises(RegistrationError) as exc_info:
                register_node(node, registry_url)

        assert exc_info.value.status_code == 401

    def test_raises_registration_error_on_http_500(self) -> None:
        """Test that RegistrationError is raised on HTTP 500 error."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        error = HTTPError(
            url=registry_url,
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        with patch("canvastekk_workflow_sdk.registry.urllib.request.urlopen", side_effect=error):
            with pytest.raises(RegistrationError) as exc_info:
                register_node(node, registry_url)

        assert exc_info.value.status_code == 500

    def test_invoke_url_included_in_manifest_when_provided(self) -> None:
        """Test that invoke_url is included in manifest when provided."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        invoke_url = "https://my-node.example.com"

        captured_request: Any = None

        def capture_request(req: Any, **kwargs: Any) -> MagicMock:
            nonlocal captured_request
            captured_request = req
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"id":"123"}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("canvastekk_workflow_sdk.registry.urllib.request.urlopen", side_effect=capture_request):
            register_node(node, registry_url, invoke_url=invoke_url)

        assert captured_request is not None
        request_body = json.loads(captured_request.data)
        assert "invoke_url" in request_body
        assert request_body["invoke_url"] == invoke_url

    def test_invoke_url_omitted_from_manifest_when_none(self) -> None:
        """Test that invoke_url is omitted from manifest when None."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        captured_request: Any = None

        def capture_request(req: Any, **kwargs: Any) -> MagicMock:
            nonlocal captured_request
            captured_request = req
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"id":"123"}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("canvastekk_workflow_sdk.registry.urllib.request.urlopen", side_effect=capture_request):
            register_node(node, registry_url)

        assert captured_request is not None
        request_body = json.loads(captured_request.data)
        assert "invoke_url" not in request_body

    def test_custom_invoke_type_in_manifest(self) -> None:
        """Test that custom invoke_type is included in manifest."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        invoke_type = "lambda"

        captured_request: Any = None

        def capture_request(req: Any, **kwargs: Any) -> MagicMock:
            nonlocal captured_request
            captured_request = req
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"id":"123"}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("canvastekk_workflow_sdk.registry.urllib.request.urlopen", side_effect=capture_request):
            register_node(node, registry_url, invoke_type=invoke_type)

        assert captured_request is not None
        request_body = json.loads(captured_request.data)
        assert request_body["invoke_type"] == invoke_type

    def test_default_invoke_type_is_http(self) -> None:
        """Test that default invoke_type is 'http'."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        captured_request: Any = None

        def capture_request(req: Any, **kwargs: Any) -> MagicMock:
            nonlocal captured_request
            captured_request = req
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"id":"123"}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("canvastekk_workflow_sdk.registry.urllib.request.urlopen", side_effect=capture_request):
            register_node(node, registry_url)

        assert captured_request is not None
        request_body = json.loads(captured_request.data)
        assert request_body["invoke_type"] == "http"

    def test_custom_timeout_passed_to_urlopen(self) -> None:
        """Test that custom timeout is passed to urlopen."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        timeout = 60

        captured_timeout: list[int] = []

        def capture_timeout(url: Any, timeout: int | None = None, **kwargs: Any) -> MagicMock:
            captured_timeout.append(timeout or 30)
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"id":"123"}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("canvastekk_workflow_sdk.registry.urllib.request.urlopen", side_effect=capture_timeout):
            register_node(node, registry_url, timeout=timeout)

        assert captured_timeout == [timeout]


class TestRegistrationError:
    """Tests for RegistrationError exception."""

    def test_error_message(self) -> None:
        """Test that error message is stored correctly."""
        error = RegistrationError("Failed to register")
        assert str(error) == "Failed to register"

    def test_status_code_attribute(self) -> None:
        """Test that status_code attribute is stored correctly."""
        error = RegistrationError("Failed", status_code=401)
        assert error.status_code == 401

    def test_body_attribute(self) -> None:
        """Test that body attribute is stored correctly."""
        error = RegistrationError("Failed", body='{"error": "details"}')
        assert error.body == '{"error": "details"}'

    def test_all_attributes(self) -> None:
        """Test that all attributes are stored correctly."""
        error = RegistrationError("Failed", status_code=500, body='{"error": "details"}')
        assert str(error) == "Failed"
        assert error.status_code == 500
        assert error.body == '{"error": "details"}'

    def test_chaining_from_exception(self) -> None:
        """Test that error can be chained from another exception."""
        original_error = URLError("Network error")
        try:
            raise RegistrationError("Registration failed", status_code=None, body=None) from original_error
        except RegistrationError as e:
            assert str(e) == "Registration failed"
            assert e.__cause__ is original_error
