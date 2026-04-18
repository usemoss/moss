"""S3 data loader for Image Search Demo backend.

Streams photos on-demand from S3. Uses the IAM task role for
credentials in ECS (no explicit AWS keys needed). For local
development, reads AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
from environment or ~/.aws/credentials.
"""

from __future__ import annotations

import logging
import re

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("image_search_demo")

_MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10 MB
_PHOTO_ID_RE = re.compile(r"^\d+$")


class S3DataLoader:
    """Streams photos on-demand from S3."""

    def __init__(self, bucket: str, region: str = "us-east-1") -> None:
        self._bucket = bucket
        self._s3 = boto3.client("s3", region_name=region)

    def get_photo_bytes(self, photo_id: str) -> bytes | None:
        """Fetch a single photo from ``photos/{photo_id}.jpg`` in S3.

        Returns the raw JPEG bytes, or ``None`` if not found or too large.
        """
        if not _PHOTO_ID_RE.match(photo_id):
            return None

        key = f"photos/{photo_id}.jpg"
        try:
            resp = self._s3.get_object(Bucket=self._bucket, Key=key)
            body = resp["Body"].read(_MAX_PHOTO_BYTES + 1)
            if len(body) > _MAX_PHOTO_BYTES:
                logger.warning("Photo %s exceeds size limit (%d bytes)", key, len(body))
                return None
            return body
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                return None
            logger.warning("S3 error fetching %s: %s", key, exc)
            return None
