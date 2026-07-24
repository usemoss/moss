"""Keep a Moss index in sync with an S3 bucket.

``watch()`` reconciles the index with the bucket once, then polls and
applies incremental updates whenever the bucket contents change. Change
detection compares ``{key: version marker}`` snapshots from
``S3Connector.snapshot()`` (ETag + LastModified + Size), so added, removed,
and modified objects — including metadata-only rewrites — are all synced.

Updates are diff-based: only changed objects are downloaded and re-embedded
(``add_docs`` with upsert for additions and modifications, ``delete_docs``
for removals). The live index is never deleted while a replacement is
pending — a transient S3 or Moss failure mid-sync raises with the existing
index intact and searchable. The index is deleted outright only when the
bucket empties, so stale documents never linger.

S3 network I/O is synchronous under the hood (``boto3``), so snapshots and
object downloads run in a worker thread via ``asyncio.to_thread`` and never
block the event loop.

Because updates are applied by document id, the mapper must produce a
*stable* id for each object (``row["key"]`` is the natural choice) — random
ids would duplicate documents on every update.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from moss import MossClient, MutationOptions

from .connector import S3Connector


async def _delete_index_if_exists(client: MossClient, index_name: str) -> None:
    """Delete the index, treating only confirmed absence as a no-op.

    The SDK has no typed not-found error, so absence is confirmed via
    ``list_indexes()`` instead of by swallowing delete failures — an auth,
    network, or server error from ``delete_index`` propagates, because
    treating it as success would leave stale documents searchable while
    watch() believes the index is gone.
    """
    names = {idx.name for idx in await client.list_indexes()}
    if index_name not in names:
        return  # confirmed missing (e.g. deleted externally) — nothing to do
    await client.delete_index(index_name)


async def watch(
    source: S3Connector,
    project_id: str,
    project_key: str,
    index_name: str,
    *,
    poll_interval: float = 60.0,
    model_id: str | None = None,
    on_change: Callable[[dict[str, str]], Any] | None = None,
    max_polls: int | None = None,
) -> int:
    """Sync the bucket into ``index_name``, then apply every change to it.

    On startup the index is reconciled with the bucket: created from the
    current objects if it does not exist, otherwise upserted and purged of
    documents whose objects are gone — a survivor from a prior run is
    reused, never deleted and re-created. After that, each poll downloads
    only the objects whose version markers changed and pushes the diff.

    Snapshots are taken *before* the corresponding sync, so objects that
    change while a sync is running are picked up on the next poll rather
    than lost.

    Args:
        source: The ``S3Connector`` to read from. Its ``mapper`` must assign
            stable document ids (e.g. ``row["key"]``).
        project_id: Moss project id.
        project_key: Moss project key.
        index_name: Name of the Moss index to keep in sync.
        poll_interval: Seconds to wait between bucket snapshots.
        model_id: Optional Moss model id, used when the index is created.
        on_change: Optional callback invoked after each applied change with
            the new ``{key: version marker}`` snapshot. May be sync or async.
        max_polls: Stop after this many polls (useful for tests and one-shot
            sync jobs). ``None`` (the default) polls until cancelled.

    Returns:
        The number of change-syncs applied (not counting the initial
        reconciliation).
    """
    client = MossClient(project_id, project_key)

    previous = await asyncio.to_thread(source.snapshot)
    pairs = await asyncio.to_thread(lambda: list(source.fetch(list(previous))))
    docs = [doc for _, doc in pairs]
    key_ids = {key: doc.id for key, doc in pairs}

    index_exists = any(idx.name == index_name for idx in await client.list_indexes())
    if index_exists and not docs:
        # Bucket is empty but a prior run left an index — stale docs must
        # not stay searchable.
        await _delete_index_if_exists(client, index_name)
        index_exists = False
    elif index_exists:
        await client.add_docs(index_name, docs, options=MutationOptions(upsert=True))
        current_ids = {doc.id for doc in docs}
        stale = [d.id for d in await client.get_docs(index_name) if d.id not in current_ids]
        if stale:
            await client.delete_docs(index_name, stale)
    elif docs:
        await client.create_index(index_name, docs, model_id=model_id)
        index_exists = True

    synced = 0
    polls = 0
    while max_polls is None or polls < max_polls:
        await asyncio.sleep(poll_interval)
        polls += 1
        current = await asyncio.to_thread(source.snapshot)
        if current == previous:
            continue

        if not current:
            # Bucket emptied: nothing to replace the docs with, so drop the
            # index entirely rather than leave stale documents searchable.
            if index_exists:
                await _delete_index_if_exists(client, index_name)
                index_exists = False
            key_ids.clear()
        else:
            changed = [k for k, marker in current.items() if previous.get(k) != marker]
            removed = [k for k in previous if k not in current]

            pairs = await asyncio.to_thread(lambda keys=changed: list(source.fetch(keys)))
            fetched = {key for key, _ in pairs}
            # Objects that vanished between the snapshot and the fetch are
            # removals; drop them from `current` too so the next poll's
            # comparison stays consistent.
            for key in changed:
                if key not in fetched:
                    removed.append(key)
                    current.pop(key, None)

            delete_ids = [key_ids.pop(key) for key in removed if key in key_ids]
            new_docs = []
            for key, doc in pairs:
                old_id = key_ids.get(key)
                if old_id is not None and old_id != doc.id:
                    delete_ids.append(old_id)  # mapper id changed for this key
                key_ids[key] = doc.id
                new_docs.append(doc)

            if new_docs:
                if index_exists:
                    await client.add_docs(
                        index_name, new_docs, options=MutationOptions(upsert=True)
                    )
                else:
                    await client.create_index(index_name, new_docs, model_id=model_id)
                    index_exists = True
            if delete_ids and index_exists:
                await client.delete_docs(index_name, delete_ids)

        synced += 1
        previous = current
        if on_change is not None:
            maybe_awaitable = on_change(current.copy())
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
    return synced
