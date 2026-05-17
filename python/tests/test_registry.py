"""Tests for registry helper."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from canvastekk_workflow_sdk import NodeDefinition
from canvastekk_workflow_sdk.base import BaseNode
from canvastekk_workflow_sdk.context import ExecutionContext
from canvastekk_workflow_sdk.registry import RegistrationError, _extract_node_data, register_node


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
        mock_response.status_code = 200
        mock_response.json.return_value = response_body
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            result = register_node(node, registry_url, api_key="key")

        mock_post.assert_called_once()
        assert result == response_body

    def test_posts_correct_manifest_json(self) -> None:
        """Test that POSTs correct manifest JSON with all required fields."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        invoke_url = "https://node.example.com"
        api_key = "secret-key"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            register_node(node, registry_url, invoke_url=invoke_url, api_key=api_key)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["name"] == "test"
        assert call_kwargs["json"]["version"] == "1.0.0"
        assert call_kwargs["json"]["title"] == "Test Node"
        assert call_kwargs["json"]["invoke_type"] == "http"
        assert call_kwargs["json"]["invoke_url"] == invoke_url
        assert "X-API-Key" in call_kwargs["headers"]
        assert call_kwargs["headers"]["X-API-Key"] == api_key

    def test_includes_api_key_header_when_provided(self) -> None:
        """Test that X-API-Key header is included when api_key is provided."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        api_key = "secret-key"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            register_node(node, registry_url, api_key=api_key)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert "X-API-Key" in call_kwargs["headers"]
        assert call_kwargs["headers"]["X-API-Key"] == api_key
        assert "X-Service-Token" not in call_kwargs["headers"]

    def test_includes_service_token_header_when_provided(self) -> None:
        """Test that X-Service-Token header is included when service_token is provided."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        service_token = "svs_abc123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            register_node(node, registry_url, service_token=service_token)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert "X-Service-Token" in call_kwargs["headers"]
        assert call_kwargs["headers"]["X-Service-Token"] == service_token
        assert "X-API-Key" not in call_kwargs["headers"]

    def test_service_token_takes_precedence_over_api_key(self) -> None:
        """Test that service_token takes precedence when both are provided."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            register_node(node, registry_url, api_key="old-key", service_token="svs_xyz")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["X-Service-Token"] == "svs_xyz"
        assert "X-API-Key" not in call_kwargs["headers"]

    def test_raises_value_error_when_no_auth_provided(self) -> None:
        """Test that ValueError is raised when neither api_key nor service_token is provided."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        with pytest.raises(ValueError, match="api_key.*service_token"):
            register_node(node, registry_url)

    def test_raises_value_error_when_empty_string_auth_provided(self) -> None:
        """Test that ValueError is raised when auth params are empty strings."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        with pytest.raises(ValueError, match="api_key.*service_token"):
            register_node(node, registry_url, api_key="", service_token="")

    def test_raises_registration_error_on_network_failure(self) -> None:
        """Test that RegistrationError is raised on network failure."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        with patch("canvastekk_workflow_sdk.registry.httpx.post", side_effect=httpx.ConnectError("Network error")):
            with pytest.raises(RegistrationError) as exc_info:
                register_node(node, registry_url, api_key="key")

        assert "Registration failed" in str(exc_info.value)
        assert exc_info.value.status_code is None
        assert exc_info.value.body is None

    def test_raises_registration_error_on_http_401(self) -> None:
        """Test that RegistrationError is raised on HTTP 401 error."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        error = httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response)

        with patch("canvastekk_workflow_sdk.registry.httpx.post", side_effect=error):
            with pytest.raises(RegistrationError) as exc_info:
                register_node(node, registry_url, api_key="key")

        assert exc_info.value.status_code == 401

    def test_raises_registration_error_on_http_500(self) -> None:
        """Test that RegistrationError is raised on HTTP 500 error."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        error = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)

        with patch("canvastekk_workflow_sdk.registry.httpx.post", side_effect=error):
            with pytest.raises(RegistrationError) as exc_info:
                register_node(node, registry_url, service_token="svs_xxx")

        assert exc_info.value.status_code == 500

    def test_invoke_url_included_in_manifest_when_provided(self) -> None:
        """Test that invoke_url is included in manifest when provided."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        invoke_url = "https://my-node.example.com"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            register_node(node, registry_url, invoke_url=invoke_url, api_key="key")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert "invoke_url" in call_kwargs["json"]
        assert call_kwargs["json"]["invoke_url"] == invoke_url

    def test_invoke_url_omitted_from_manifest_when_none(self) -> None:
        """Test that invoke_url is omitted from manifest when None."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            register_node(node, registry_url, api_key="key")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert "invoke_url" not in call_kwargs["json"]

    def test_custom_invoke_type_in_manifest(self) -> None:
        """Test that custom invoke_type is included in manifest."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        invoke_type = "lambda"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            register_node(node, registry_url, invoke_type=invoke_type, api_key="key")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["invoke_type"] == invoke_type

    def test_default_invoke_type_is_http(self) -> None:
        """Test that default invoke_type is 'http'."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            register_node(node, registry_url, api_key="key")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["invoke_type"] == "http"

    def test_custom_timeout_passed_to_httpx(self) -> None:
        """Test that custom timeout is passed to httpx.post."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"
        timeout = 60

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            register_node(node, registry_url, timeout=timeout, api_key="key")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["timeout"] == timeout

    def test_network_error_with_service_token(self) -> None:
        """Test that RegistrationError is raised on network failure with service_token."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        with patch("canvastekk_workflow_sdk.registry.httpx.post", side_effect=httpx.ConnectError("Network error")):
            with pytest.raises(RegistrationError) as exc_info:
                register_node(node, registry_url, service_token="svs_xxx")

        assert "Registration failed" in str(exc_info.value)

    def test_successful_registration_unwraps_register_node_response(self) -> None:
        """Test that RegisterNodeResponse wrapper is unwrapped via register_node."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"id": "node-123", "name": "test"}, "action": "created"}
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            result = register_node(node, registry_url, api_key="key")

        mock_post.assert_called_once()
        assert result == {"id": "node-123", "name": "test"}
        assert "action" not in result

    def test_successful_registration_returns_old_format_directly(self) -> None:
        """Test that old response format (no data wrapper) is returned as-is."""
        node = DummyNode()
        registry_url = "https://registry.example.com/api/nodes"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "node-123", "name": "test"}
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.registry.httpx.post", return_value=mock_response) as mock_post:
            result = register_node(node, registry_url, api_key="key")

        mock_post.assert_called_once()
        assert result == {"id": "node-123", "name": "test"}


class TestExtractNodeData:
    """Tests for _extract_node_data helper."""

    def test_returns_data_field_from_wrapper_response(self) -> None:
        """Test that data dict is extracted from wrapper format."""
        payload = {"data": {"id": "node-123", "name": "test"}, "action": "created"}
        result = _extract_node_data(payload)
        assert result == {"id": "node-123", "name": "test"}

    def test_returns_payload_directly_when_no_data_key(self) -> None:
        """Test that payload is returned as-is when no data key."""
        payload = {"id": "node-123", "name": "test"}
        result = _extract_node_data(payload)
        assert result == {"id": "node-123", "name": "test"}

    def test_returns_payload_when_data_is_not_dict(self) -> None:
        """Test that payload is returned when data is not a dict."""
        payload = {"data": "not-a-dict", "id": "node-123"}
        result = _extract_node_data(payload)
        assert result == {"data": "not-a-dict", "id": "node-123"}

    def test_empty_data_dict(self) -> None:
        """Test that empty data dict is returned as-is."""
        payload = {"data": {}}
        result = _extract_node_data(payload)
        assert result == {}


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
        original_error = httpx.ConnectError("Network error")
        try:
            raise RegistrationError("Registration failed", status_code=None, body=None) from original_error
        except RegistrationError as e:
            assert str(e) == "Registration failed"
            assert e.__cause__ is original_error
