"""
Output Upload Handlers

Provides the OutputUploader protocol and concrete implementations
for uploading node output files to external storage (e.g., S3).
"""

from __future__ import annotations

import logging
import os
import urllib.request
from typing import TYPE_CHECKING, Protocol, runtime_checkable

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

    def upload_outputs(
        self,
        response: NodeExecutionResponse,
        upload_urls: dict[str, str],
        file_output_fields: list[str],
    ) -> None: ...


class S3PresignedUploader:
    """Upload binary outputs to S3 via pre-signed PUT URLs.

    Uses only stdlib ``urllib`` — no ``boto3`` dependency required.

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
            urllib.error.URLError: If the upload fails.
        """
        file_size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            req = urllib.request.Request(
                presigned_url,
                data=f,
                method="PUT",
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(file_size),
                },
            )
            urllib.request.urlopen(req)

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
                logger.warning(f"Output field '{field_name}' value is not a local file: {value}")
                continue

            presigned_url = upload_urls[field_name]
            try:
                self.upload_file(value, presigned_url)
                logger.info(f"Uploaded output '{field_name}' to S3 ({os.path.getsize(value)} bytes)")
            except Exception as e:
                logger.error(f"Failed to upload output '{field_name}' to S3: {e}")


_default_uploader = S3PresignedUploader()


def get_default_uploader() -> S3PresignedUploader:
    return _default_uploader
