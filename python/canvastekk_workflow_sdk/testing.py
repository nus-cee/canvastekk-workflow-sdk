"""
Test Utilities

Helpers for testing CanvasTEKK workflow nodes locally, including
a lightweight HTTP file server for simulating presigned URL downloads.
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Silent HTTP handler that logs nothing to stderr/stdout."""

    def log_message(self, fmt, *args):
        pass


def _make_handler(directory: str) -> type[_Handler]:
    """Create a handler class that serves from the given directory."""

    class _DirHandler(_Handler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

    return _DirHandler


class LocalFileServer:
    """Serve files from a local directory over HTTP.

    Designed for testing nodes that download files via presigned URLs.
    The SDK's built-in ``_prepare_file_inputs`` only triggers on
    ``http://`` / ``https://`` values — a plain local path bypasses the
    download pipeline entirely.  This server lets you exercise the full
    download → validate → execute path without S3 or mocking.

    Usage::

        from canvastekk_workflow_sdk import LocalFileServer
        from canvastekk_workflow_sdk import NodeExecutionRequest

        with LocalFileServer(tmp_path) as server:
            url = server.url_for("scan.las")
            request = NodeExecutionRequest(
                run_id="test",
                node_id="n1",
                inputs={"input_file": url},
            )
            response = MyNode().run(request)

    Args:
        directory: Path to the directory to serve files from.
        host: Interface to bind to (default ``127.0.0.1``).
        port: Port to bind to. ``0`` picks a free port (default).
    """

    def __init__(
        self,
        directory: str | Path,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        self._directory = str(Path(directory).resolve())
        self._host = host
        self._port = port
        self._server: http.server.HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._actual_port: int = 0
        self._lock = threading.Lock()

    @property
    def base_url(self) -> str:
        """Base URL of the running server (e.g. ``http://127.0.0.1:9876``)."""
        if self._server is None:
            raise RuntimeError("Server is not running. Use as a context manager.")
        return f"http://{self._host}:{self._actual_port}"

    def url_for(self, filename: str) -> str:
        """Get a full URL for a file in the served directory.

        Args:
            filename: Name of the file relative to the served directory.

        Returns:
            Full HTTP URL (e.g. ``http://127.0.0.1:9876/scan.las``).
        """
        return f"{self.base_url}/{filename}"

    def start(self) -> None:
        """Start the server in a background thread."""
        with self._lock:
            if self._server is not None:
                return

            handler = _make_handler(self._directory)
            self._server = http.server.HTTPServer((self._host, self._port), handler)
            self._actual_port = self._server.server_address[1]
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                kwargs={"poll_interval": 0.05},
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop the server and wait for the thread to finish."""
        with self._lock:
            if self._server is not None:
                self._server.shutdown()
                self._server.server_close()
                if self._thread is not None:
                    self._thread.join(timeout=5.0)
                self._server = None
                self._thread = None

    def __enter__(self) -> LocalFileServer:
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()


@contextmanager
def serve_files(
    directory: str | Path,
    host: str = "127.0.0.1",
    port: int = 0,
) -> Generator[LocalFileServer, None, None]:
    """Context manager that serves files from a directory over HTTP.

    Convenience wrapper around :class:`LocalFileServer`::

        from canvastekk_workflow_sdk.testing import serve_files

        with serve_files(tmp_path) as server:
            url = server.url_for("data.csv")
            # pass url to node as if it were a presigned URL

    Args:
        directory: Path to the directory to serve.
        host: Interface to bind to (default ``127.0.0.1``).
        port: Port to bind to. ``0`` picks a free port.

    Yields:
        A running :class:`LocalFileServer` instance.
    """
    with LocalFileServer(directory, host, port) as server:
        yield server
