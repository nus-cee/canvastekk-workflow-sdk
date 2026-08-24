"""Tests for output upload functionality (Phase 1)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

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
        assert hasattr(call_kwargs["content"], "read")

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
        assert hasattr(call_kwargs["content"], "read")

    def test_upload_file_zero_byte_file(self, tmp_path: Path) -> None:
        """Test upload_file with a zero-byte file sends Content-Length: 0."""
        uploader = S3PresignedUploader()
        test_file = tmp_path / "empty.bin"
        test_file.write_bytes(b"")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.uploads.httpx.put", return_value=mock_response) as mock_put:
            uploader.upload_file(str(test_file), "https://example.com/presigned")

        mock_put.assert_called_once()
        call_kwargs = mock_put.call_args[1]
        assert call_kwargs["headers"]["Content-Length"] == "0"
        assert call_kwargs["headers"]["Content-Type"] == "application/octet-stream"

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

    def test_upload_outputs_raises_on_upload_failure(self, tmp_path: Path) -> None:
        """Upload failures now raise so the execution fails (DA-1711 4.1)."""
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

        with patch("canvastekk_workflow_sdk.uploads.httpx.put", side_effect=error):
            with pytest.raises(httpx.HTTPStatusError):
                uploader.upload_outputs(response, upload_urls, file_output_fields)

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


class TestUploadWireFormat:
    """Wire-contract regression pins (DA-1900).

    Asserts the actual bytes-on-the-wire for S3 presigned PUTs against a real local
    HTTP server: explicit Content-Length, no Transfer-Encoding: chunked, body intact.
    Passes on pre-DA-1900 code too (httpx 0.28 auto-sets Content-Length via os.fstat)
    — the pin exists to catch future httpx drift, not to gate the fix.
    """

    def test_upload_file_sends_fixed_length_identity_put(self, tmp_path: Path) -> None:
        """PUT wire format: Content-Length == file size, no chunked TE, body intact."""
        import http.server
        import threading

        payload = bytes(range(256)) * 64  # 16 KiB of non-repeating-pattern data
        test_file = tmp_path / "payload.bin"
        test_file.write_bytes(payload)

        captured: dict[str, object] = {}

        class _CaptureHandler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_PUT(self) -> None:  # noqa: N802 (stdlib naming)
                captured["content_length"] = self.headers.get("Content-Length")
                captured["transfer_encoding"] = self.headers.get("Transfer-Encoding")
                length = int(self.headers["Content-Length"])
                captured["body"] = self.rfile.read(length)
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args: object) -> None:
                pass  # keep test output clean

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _CaptureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/upload"
            S3PresignedUploader().upload_file(str(test_file), url)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        assert captured["content_length"] == str(len(payload))
        assert captured["transfer_encoding"] is None
        assert captured["body"] == payload


class TestUploadRetry:
    """Retry semantics for S3PresignedUploader.upload_file (DA-1955)."""

    def _write_file(self, tmp_path: Path) -> Path:
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        return test_file

    def test_transport_error_retries_then_succeeds(self, tmp_path: Path) -> None:
        """Two transport failures then success = 3 attempts, uploads."""
        uploader = S3PresignedUploader()
        test_file = self._write_file(tmp_path)

        mock_success = MagicMock()
        mock_success.raise_for_status = MagicMock()

        with patch(
            "canvastekk_workflow_sdk.uploads.httpx.put",
            side_effect=[httpx.TransportError("boom"), httpx.TransportError("boom"), mock_success],
        ) as mock_put:
            uploader.upload_file(str(test_file), "https://example.com/presigned")

        assert mock_put.call_count == 3

    def test_500_retries_then_raises_after_max_attempts(self, tmp_path: Path) -> None:
        """Persistent 500s exhaust 3 attempts then raise."""
        uploader = S3PresignedUploader()
        test_file = self._write_file(tmp_path)

        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_500.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=mock_500)
        )

        with (
            patch("canvastekk_workflow_sdk.uploads.httpx.put", return_value=mock_500) as mock_put,
            patch("canvastekk_workflow_sdk.uploads.time.sleep") as mock_sleep,
        ):
            with pytest.raises(httpx.HTTPStatusError):
                uploader.upload_file(str(test_file), "https://example.com/presigned")

        assert mock_put.call_count == 3
        assert mock_sleep.call_count == 2

    def test_403_never_retries(self, tmp_path: Path) -> None:
        """Deterministic 4xx client errors raise immediately."""
        uploader = S3PresignedUploader()
        test_file = self._write_file(tmp_path)

        mock_403 = MagicMock()
        mock_403.status_code = 403
        mock_403.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("403", request=MagicMock(), response=mock_403)
        )

        with patch("canvastekk_workflow_sdk.uploads.httpx.put", return_value=mock_403) as mock_put:
            with pytest.raises(httpx.HTTPStatusError):
                uploader.upload_file(str(test_file), "https://example.com/presigned")

        mock_put.assert_called_once()

    def test_success_single_attempt(self, tmp_path: Path) -> None:
        """Successful upload makes exactly one attempt."""
        uploader = S3PresignedUploader()
        test_file = self._write_file(tmp_path)

        mock_success = MagicMock()
        mock_success.raise_for_status = MagicMock()

        with patch("canvastekk_workflow_sdk.uploads.httpx.put", return_value=mock_success) as mock_put:
            uploader.upload_file(str(test_file), "https://example.com/presigned")

        mock_put.assert_called_once()

    def test_backoff_schedule_exponential(self, tmp_path: Path) -> None:
        """Backoff is 0.5s then 1.0s (0.5 * 2^(n-1))."""
        uploader = S3PresignedUploader()
        test_file = self._write_file(tmp_path)

        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_500.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=mock_500)
        )

        with (
            patch("canvastekk_workflow_sdk.uploads.httpx.put", return_value=mock_500),
            patch("canvastekk_workflow_sdk.uploads.time.sleep") as mock_sleep,
        ):
            with pytest.raises(httpx.HTTPStatusError):
                uploader.upload_file(str(test_file), "https://example.com/presigned")

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [0.5, 1.0]
