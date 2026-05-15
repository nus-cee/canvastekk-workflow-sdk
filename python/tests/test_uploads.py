"""Tests for output upload functionality (Phase 1)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from canvastekk_workflow_sdk.response import NodeExecutionResponse
from canvastekk_workflow_sdk.uploads import OutputUploader, S3PresignedUploader, get_default_uploader


class MockUploader(OutputUploader):
    """Mock uploader for testing protocol compliance."""

    def __init__(self) -> None:
        self.uploaded: list[tuple[NodeExecutionResponse, dict[str, str], list[str]]] = []

    def upload_outputs(
        self,
        response: NodeExecutionResponse,
        upload_urls: dict[str, str],
        file_output_fields: list[str],
    ) -> None:
        self.uploaded.append((response, upload_urls, file_output_fields))


class TestOutputUploaderProtocol:
    """Tests for OutputUploader protocol (Phase 1)."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that OutputUploader protocol is runtime checkable."""
        uploader = MockUploader()
        assert isinstance(uploader, OutputUploader)

    def test_s3_uploader_implements_protocol(self) -> None:
        """Test that S3PresignedUploader implements OutputUploader protocol."""
        uploader = S3PresignedUploader()
        assert isinstance(uploader, OutputUploader)


class TestS3PresignedUploader:
    """Tests for S3PresignedUploader class (Phase 1)."""

    def test_upload_file_with_valid_file(self, tmp_path: Path) -> None:
        """Test upload_file works with a valid file."""
        uploader = S3PresignedUploader()
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.uploads.httpx.put", return_value=mock_response) as mock_put:
            uploader.upload_file(str(test_file), "https://example.com/presigned")

        mock_put.assert_called_once()
        call_kwargs = mock_put.call_args[1]
        assert call_kwargs["headers"]["Content-Type"] == "application/octet-stream"
        assert call_kwargs["content"] == b"test content"

    def test_upload_file_sets_headers(self, tmp_path: Path) -> None:
        """Test that upload_file sets correct headers."""
        uploader = S3PresignedUploader()
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"x" * 1000)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.uploads.httpx.put", return_value=mock_response) as mock_put:
            uploader.upload_file(str(test_file), "https://example.com/presigned")

        mock_put.assert_called_once()
        call_kwargs = mock_put.call_args[1]
        assert call_kwargs["headers"]["Content-Type"] == "application/octet-stream"
        assert call_kwargs["content"] == b"x" * 1000

    def test_upload_outputs_with_valid_file_and_url(self, tmp_path: Path) -> None:
        """Test upload_outputs with valid file and URL."""
        uploader = S3PresignedUploader()
        test_file = tmp_path / "result.ply"
        test_file.write_bytes(b"ply data")

        response = NodeExecutionResponse.success(
            execution_id="exec-1",
            outputs={"result_path": str(test_file), "summary": "done"},
            duration_ms=100,
        )
        upload_urls = {"result_path": "https://s3.amazonaws.com/upload"}
        file_output_fields = ["result_path"]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.uploads.httpx.put", return_value=mock_response) as mock_put:
            uploader.upload_outputs(response, upload_urls, file_output_fields)

        mock_put.assert_called_once()

    def test_upload_outputs_skips_non_file_values(self) -> None:
        """Test that upload_outputs skips non-string file values."""
        uploader = S3PresignedUploader()
        response = NodeExecutionResponse.success(
            execution_id="exec-1",
            outputs={"result": 123, "summary": "done"},
            duration_ms=100,
        )
        upload_urls = {"result": "https://s3.amazonaws.com/upload"}
        file_output_fields = ["result"]

        mock_put = MagicMock()
        with patch("canvastekk_workflow_sdk.uploads.httpx.put", mock_put):
            uploader.upload_outputs(response, upload_urls, file_output_fields)
            mock_put.assert_not_called()

    def test_upload_outputs_skips_missing_urls(self, tmp_path: Path) -> None:
        """Test that upload_outputs skips fields without upload URLs."""
        uploader = S3PresignedUploader()
        test_file = tmp_path / "result.ply"
        test_file.write_bytes(b"ply data")

        response = NodeExecutionResponse.success(
            execution_id="exec-1",
            outputs={"result_path": str(test_file), "summary": "done"},
            duration_ms=100,
        )
        upload_urls: dict[str, str] = {}
        file_output_fields = ["result_path"]

        mock_put = MagicMock()
        with patch("canvastekk_workflow_sdk.uploads.httpx.put", mock_put):
            uploader.upload_outputs(response, upload_urls, file_output_fields)
            mock_put.assert_not_called()

    def test_upload_outputs_logs_warning_for_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that upload_outputs logs warning for non-existent file."""
        uploader = S3PresignedUploader()
        response = NodeExecutionResponse.success(
            execution_id="exec-1",
            outputs={"result_path": "/nonexistent/file.ply"},
            duration_ms=100,
        )
        upload_urls = {"result_path": "https://s3.amazonaws.com/upload"}
        file_output_fields = ["result_path"]

        with patch("canvastekk_workflow_sdk.uploads.logger") as mock_logger:
            uploader.upload_outputs(response, upload_urls, file_output_fields)
            mock_logger.warning.assert_called_once()
            assert "Output field '%s' value is not a local file" in str(mock_logger.warning.call_args)

    def test_upload_outputs_logs_error_but_doesnt_raise(self, tmp_path: Path) -> None:
        """Test that upload failure logs error but doesn't raise exception."""
        uploader = S3PresignedUploader()
        test_file = tmp_path / "result.ply"
        test_file.write_bytes(b"ply data")

        response = NodeExecutionResponse.success(
            execution_id="exec-1",
            outputs={"result_path": str(test_file), "summary": "done"},
            duration_ms=100,
        )
        upload_urls = {"result_path": "https://s3.amazonaws.com/upload"}
        file_output_fields = ["result_path"]

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Error"
        error = httpx.HTTPStatusError("Upload failed", request=MagicMock(), response=mock_response)

        with patch("canvastekk_workflow_sdk.uploads.httpx.put", side_effect=error), patch("canvastekk_workflow_sdk.uploads.logger") as mock_logger:
            uploader.upload_outputs(response, upload_urls, file_output_fields)
            mock_logger.error.assert_called_once()
            assert "Failed to upload output '%s' to S3" in str(mock_logger.error.call_args)

    def test_upload_outputs_with_no_outputs(self) -> None:
        """Test that upload_outputs returns early when outputs is None."""
        uploader = S3PresignedUploader()
        response = NodeExecutionResponse.failure(
            execution_id="exec-1",
            error="test error",
            error_type="ValueError",
            duration_ms=100,
        )
        upload_urls = {"result_path": "https://s3.amazonaws.com/upload"}
        file_output_fields = ["result_path"]

        mock_put = MagicMock()
        with patch("canvastekk_workflow_sdk.uploads.httpx.put", mock_put):
            uploader.upload_outputs(response, upload_urls, file_output_fields)
            mock_put.assert_not_called()


class TestDefaultUploaderSingleton:
    """Tests for get_default_uploader singleton (Phase 1)."""

    def test_get_default_uploader_returns_singleton(self) -> None:
        """Test that get_default_uploader returns the same instance."""
        uploader1 = get_default_uploader()
        uploader2 = get_default_uploader()
        assert uploader1 is uploader2

    def test_default_uploader_is_s3_presigned_uploader(self) -> None:
        """Test that default uploader is S3PresignedUploader instance."""
        uploader = get_default_uploader()
        assert isinstance(uploader, S3PresignedUploader)

    def test_default_uploader_implements_protocol(self) -> None:
        """Test that default uploader implements OutputUploader protocol."""
        uploader = get_default_uploader()
        assert isinstance(uploader, OutputUploader)
