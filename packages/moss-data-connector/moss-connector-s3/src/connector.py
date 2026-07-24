"""Amazon S3 connector.

Reads objects from an S3 bucket via ``boto3`` and yields one
``DocumentInfo`` per object. Handles pagination automatically using
``list_objects_v2`` continuation tokens.

The connector accepts ``boto3.client`` kwargs (``region_name``,
``endpoint_url``, ``aws_access_key_id``, etc.) passed through to the S3
client so you can target MinIO, LocalStack, or a specific AWS region
without extra boilerplate.

Each object is turned into a plain ``dict`` ("row") before being handed
to your ``mapper``:

* ``key`` — the object key
* ``text`` — the object body decoded with ``encoding`` (default UTF-8)
* ``etag`` — the object's ETag with surrounding quotes stripped
* ``last_modified`` — ``datetime`` of the last modification
* ``size`` — object size in bytes
* ``content_type`` — the object's Content-Type, if any
* ``metadata`` — the object's S3 user metadata (``x-amz-meta-*``)

The mapper decides which of these become the ``DocumentInfo`` id / text /
metadata. Note that ``DocumentInfo.metadata`` requires ``dict[str, str]``,
so coerce non-string values (e.g. ``size``, ``last_modified``) to ``str``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any

import boto3
from botocore.exceptions import ClientError
from moss import DocumentInfo


class S3Connector:
    """List objects in an S3 bucket and yield one ``DocumentInfo`` per object.

    Objects are listed with ``list_objects_v2`` and paged automatically via
    continuation tokens; the caller sees a flat iterator regardless of how
    many pages S3 returns. Keys ending in ``/`` (zero-byte "folder"
    placeholders) are always skipped.

    Args:
        bucket: Name of the S3 bucket.
        mapper: Callable that turns a row (``dict[str, Any]``, see module
            docstring for the keys) into a ``DocumentInfo``.
        prefix: Optional key prefix to restrict listing server-side,
            e.g. ``"docs/"``.
        suffix: Optional key suffix (or tuple of suffixes) filtered
            client-side, e.g. ``".md"`` or ``(".md", ".txt")``. S3 has no
            server-side suffix filter, so non-matching objects are skipped
            without being downloaded.
        encoding: Text encoding used to decode object bodies. Defaults to
            ``"utf-8"``.
        encoding_errors: Error handling for decoding, passed to
            ``bytes.decode`` (e.g. ``"strict"``, ``"replace"``, ``"ignore"``).
        page_size: Number of keys to request per ``list_objects_v2`` page.
            Defaults to 1000 (the S3 maximum).
        **boto3_kwargs: Extra keyword arguments forwarded to
            ``boto3.client("s3", ...)`` — e.g. ``region_name``,
            ``endpoint_url``, ``aws_access_key_id``, ``aws_secret_access_key``.
    """

    def __init__(
        self,
        bucket: str,
        mapper: Callable[[dict[str, Any]], DocumentInfo],
        prefix: str = "",
        suffix: str | tuple[str, ...] | None = None,
        encoding: str = "utf-8",
        encoding_errors: str = "strict",
        page_size: int = 1000,
        **boto3_kwargs: Any,
    ) -> None:
        self.bucket = bucket
        self.mapper = mapper
        self.prefix = prefix
        self.suffix = suffix
        self.encoding = encoding
        self.encoding_errors = encoding_errors
        self.page_size = page_size
        self.boto3_kwargs = boto3_kwargs

    def _client(self) -> Any:
        return boto3.client("s3", **self.boto3_kwargs)

    def _matches(self, key: str) -> bool:
        if key.endswith("/"):
            return False
        return self.suffix is None or key.endswith(self.suffix)

    def _pages(self, s3: Any) -> Iterator[dict[str, Any]]:
        paginator = s3.get_paginator("list_objects_v2")
        kwargs: dict[str, Any] = {
            "Bucket": self.bucket,
            "PaginationConfig": {"PageSize": self.page_size},
        }
        if self.prefix:
            kwargs["Prefix"] = self.prefix
        yield from paginator.paginate(**kwargs)

    def _fetch_row(self, s3: Any, key: str) -> dict[str, Any] | None:
        """Download one object and build its mapper row.

        Returns ``None`` when the object vanished between listing and
        fetching (an actively modified bucket), so callers can skip it
        rather than abort — watch() picks the change up on the next poll.
        """
        try:
            response = s3.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                return None
            raise
        body: bytes = response["Body"].read()
        # etag / last_modified / size come from the get_object response, not
        # the (possibly stale) list entry, so each row describes a single
        # consistent object version.
        return {
            "key": key,
            "text": body.decode(self.encoding, errors=self.encoding_errors),
            "etag": str(response.get("ETag", "")).strip('"'),
            "last_modified": response.get("LastModified"),
            "size": response.get("ContentLength"),
            "content_type": response.get("ContentType"),
            "metadata": response.get("Metadata", {}),
        }

    def __iter__(self) -> Iterator[DocumentInfo]:
        s3 = self._client()
        for page in self._pages(s3):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not self._matches(key):
                    continue
                row = self._fetch_row(s3, key)
                if row is not None:
                    yield self.mapper(row)

    def fetch(self, keys: Iterable[str]) -> Iterator[tuple[str, DocumentInfo]]:
        """Yield ``(key, DocumentInfo)`` for each of the given keys.

        Downloads only the requested objects — this is what lets ``watch()``
        sync incrementally instead of re-reading the whole bucket. Keys that
        no longer exist are skipped.
        """
        s3 = self._client()
        for key in keys:
            row = self._fetch_row(s3, key)
            if row is not None:
                yield key, self.mapper(row)

    def snapshot(self) -> dict[str, str]:
        """Return ``{key: version marker}`` for every matching object.

        The marker combines ETag, LastModified, and Size — the ETag alone
        misses metadata-only rewrites, which keep the content hash but bump
        LastModified, and the mapper does expose ``metadata`` /
        ``content_type`` / ``last_modified``.

        Only lists keys — no object bodies are downloaded — so it is cheap
        to call repeatedly. ``watch()`` compares successive snapshots to
        detect added, removed, and modified objects.
        """
        s3 = self._client()
        snap: dict[str, str] = {}
        for page in self._pages(s3):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not self._matches(key):
                    continue
                etag = str(obj.get("ETag", "")).strip('"')
                last_modified = obj.get("LastModified")
                modified = last_modified.isoformat() if last_modified is not None else ""
                snap[key] = f"{etag}|{modified}|{obj.get('Size', '')}"
        return snap
