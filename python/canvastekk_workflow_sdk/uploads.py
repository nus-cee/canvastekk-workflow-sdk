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

    def upload_file(self, file_path: str, presigned_url: str) -> None: ...

    def upload_outputs(
        self,
        response: NodeExecutionResponse,
        upload_urls: dict[str, str],
        file_output_fields: list[str],
    ) -> None: ...


class S3PresignedUploader:
    """Upload binary outputs to S3 via pre-signed PUT URLs.

    Uses httpx for HTTP requests.

    If an individual upload fails, the error is **logged but not raised**,
    so that one failed upload does not incorrectly report the entire
    execution as failed.
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
            resp = httpx.put(presigned_url, content=f, headers={"Content-Type": "application/octet-stream"})
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
            try:
                self.upload_file(value, presigned_url)
                logger.info("Uploaded output '%s' to S3 (%d bytes)", field_name, os.path.getsize(value))
            except Exception as e:
                logger.error("Failed to upload output '%s' to S3: %s", field_name, e)


_default_uploader = S3PresignedUploader()


def get_default_uploader() -> S3PresignedUploader:
    return _default_uploader
