"""
Output Upload Handlers

Provides the OutputUploader protocol and concrete implementations
for uploading node output files to external storage (e.g., S3).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import httpx

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

        Args:
            response: The node execution response.
            upload_urls: Mapping of field name to pre-signed URL.
            file_output_fields: List of output fields that produce files.
        """
        ...


class S3PresignedUploader:
    """Upload binary outputs to S3 via pre-signed PUT URLs.

    Uses httpx for HTTP requests. A failed upload raises
    :class:`OutputUploadError` so the caller can fail the execution —
    silently reporting success with local-only paths would strand
    downstream consumers (DA-1711 4.1).
    """

    def upload_file(self, file_path: str, presigned_url: str) -> None:
        """Upload a single file to a pre-signed S3 PUT URL.

        Args:
            file_path: Local path to the file.
            presigned_url: Pre-signed S3 PUT URL.

        Raises:
            httpx.HTTPStatusError: If the upload fails.
        """
        with open(file_path, "rb") as f:
            resp = httpx.put(
                presigned_url,
                content=f,
                headers={"Content-Type": "application/octet-stream"},
                timeout=_UPLOAD_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()

    def upload_outputs(
        self,
        response: NodeExecutionResponse,
        upload_urls: dict[str, str],
        file_output_fields: list[str],
    ) -> None:
        """Upload binary output files to S3 via pre-signed URLs.

        Args:
            response: The node execution response containing output values.
            upload_urls: Mapping of output field name to pre-signed PUT URL.
            file_output_fields: Output field names that produce files.
        """
        if not response.outputs:
            return

        for field_name in file_output_fields:
            if field_name not in upload_urls:
                continue

            value = response.outputs.get(field_name)
            if not isinstance(value, str):
                continue

            if not os.path.isfile(value):
                logger.warning("Output field '%s' value is not a local file: %s", field_name, value)
                continue

            presigned_url = upload_urls[field_name]
            self.upload_file(value, presigned_url)
            logger.info("Uploaded output '%s' to S3 (%d bytes)", field_name, os.path.getsize(value))


_default_uploader = S3PresignedUploader()


def get_default_uploader() -> S3PresignedUploader:
    """Return the process-wide default :class:`S3PresignedUploader` instance."""
    return _default_uploader
