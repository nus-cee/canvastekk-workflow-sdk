"""
Output Upload Handlers

Provides the OutputUploader protocol and concrete implementations
for uploading node output files to external storage (e.g., S3).
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import httpx

from canvastekk_workflow_sdk.exceptions import NodeIOError

# Explicit generous timeout for output uploads: httpx's implicit default
# (5 s per operation) aborts legitimate multi-GB uploads on slower links.
_UPLOAD_TIMEOUT_SECONDS = 600.0

if TYPE_CHECKING:
    from canvastekk_workflow_sdk.response import NodeExecutionResponse

logger = logging.getLogger(__name__)


@runtime_checkable
class OutputUploader(Protocol):
    """Protocol for output upload handlers.

    Implement this protocol to provide custom upload behaviour
    (e.g., GCS, Azure Blob, local NFS). The SDK calls ``upload_outputs``
    after a successful execution when upload URLs are available.
    """

    def upload_file(self, file_path: str, presigned_url: str) -> None:
        """Upload a single file to storage via pre-signed URL.

        Args:
            file_path: Local path to the file.
            presigned_url: Pre-signed upload URL.
        """
        ...

    def upload_outputs(
        self,
        response: NodeExecutionResponse,
        upload_urls: dict[str, str],
        file_output_fields: list[str],
    ) -> None:
        """Upload multiple output files to storage.

        Implementations MUST raise (not skip) when a file-output field that
        is present in ``response.outputs`` and has a pre-signed URL holds a
        value that is not an existing local file — silently skipping would
        report success while the engine stamps a storage URI for the
        missing object, corrupting downstream consumers (DA-2337).

        Args:
            response: The node execution response.
            upload_urls: Mapping of field name to pre-signed URL.
            file_output_fields: List of output fields that produce files.
        """
        ...


class S3PresignedUploader:
    """Upload binary outputs to S3 via pre-signed PUT URLs.

    Uses httpx for HTTP requests. A failed upload raises
    :class:`httpx.HTTPStatusError`, which the router layer
    (``app.py``) converts into a ``fail``/``UPLOAD_FAILED`` response —
    silently reporting success with local-only paths would strand
    downstream consumers (DA-1711 4.1).
    """

    _MAX_ATTEMPTS = 3
    _INITIAL_BACKOFF_SECONDS = 0.5

    def upload_file(self, file_path: str, presigned_url: str) -> None:
        """Upload a single file to a pre-signed S3 PUT URL.

        The ``Content-Length`` header is set explicitly so the fixed-length
        identity wire contract does not rely on httpx internals (httpx
        currently auto-sets it for seekable files via ``os.fstat``; this
        pins the contract against transport drift, mirroring the TS SDK's
        DA-1811 fix). The file is still streamed (never buffered) to
        preserve the multi-GB upload contract. ``timeout`` is per-operation
        (connect/read/write/pool), not a wall-clock deadline.

        Retries transient failures (network/transport errors and HTTP 5xx)
        up to 3 attempts with exponential backoff (0.5s, 1s). Deterministic
        client errors (4xx) are never retried. The file is reopened per
        attempt because the request consumed the stream.

        Args:
            file_path: Local path to the file.
            presigned_url: Pre-signed S3 PUT URL.

        Raises:
            httpx.HTTPStatusError: If the upload fails after retries.
            httpx.TransportError: If the connection fails after retries.
        """
        last_error: Exception | None = None
        for attempt in range(1, self._MAX_ATTEMPTS + 1):
            try:
                with open(file_path, "rb") as f:
                    resp = httpx.put(
                        presigned_url,
                        content=f,
                        headers={
                            "Content-Type": "application/octet-stream",
                            "Content-Length": str(os.path.getsize(file_path)),
                        },
                        timeout=_UPLOAD_TIMEOUT_SECONDS,
                    )
                    resp.raise_for_status()
                return
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    raise
                last_error = e
            except httpx.TransportError as e:
                last_error = e

            if attempt < self._MAX_ATTEMPTS:
                backoff = self._INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "Upload attempt %d/%d failed (%s); retrying in %.1fs",
                    attempt,
                    self._MAX_ATTEMPTS,
                    last_error,
                    backoff,
                )
                time.sleep(backoff)

        assert last_error is not None
        raise last_error

    def upload_outputs(
        self,
        response: NodeExecutionResponse,
        upload_urls: dict[str, str],
        file_output_fields: list[str],
    ) -> None:
        """Upload binary output files to S3 via pre-signed URLs.

        A declared file-output field that HAS a pre-signed URL but whose
        value is not a string referencing an existing local file RAISES
        :class:`NodeIOError` — the engine stamps an ``s3://`` URI for every
        present output field on pass, so skipping the upload would report
        success while corrupting every downstream consumer (DA-2337).

        Args:
            response: The node execution response containing output values.
            upload_urls: Mapping of output field name to pre-signed PUT URL.
            file_output_fields: Output field names that produce files.

        Raises:
            NodeIOError: If a present file-output field with a pre-signed
                URL holds a non-string value or a path that is not an
                existing local file.
        """
        if not response.outputs:
            return

        for field_name in file_output_fields:
            if field_name not in upload_urls:
                continue

            if field_name not in response.outputs:
                # Omitted output: the engine stamps s3:// URIs only for
                # fields present in the response, so omission is legal.
                continue

            value = response.outputs[field_name]
            if not isinstance(value, str):
                logger.error("Output field '%s' value is not a string: %s", field_name, type(value).__name__)
                raise NodeIOError(
                    f"Output field '{field_name}' value is not a string: {type(value).__name__}"
                )

            if not os.path.isfile(value):
                logger.error("Output field '%s' value is not a local file: %s", field_name, value)
                raise NodeIOError(
                    f"Output field '{field_name}' value is not a local file: {value}",
                    path=value,
                )

            presigned_url = upload_urls[field_name]
            self.upload_file(value, presigned_url)
            logger.info("Uploaded output '%s' to S3 (%d bytes)", field_name, os.path.getsize(value))


_default_uploader = S3PresignedUploader()


def get_default_uploader() -> S3PresignedUploader:
    """Return the process-wide default :class:`S3PresignedUploader` instance."""
    return _default_uploader
