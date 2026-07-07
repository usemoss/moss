"""
Stable per-device id sourcing for usage telemetry (MOS-14).

The closed Moss core owns the actual /telemetry POST + buffering + 3s flush.
This module's ONLY job is to source a stable, persisted, per-device id and hand
it to the core through the native binding's device-id entry point. It contains
zero telemetry HTTP / buffering / flush / event-composition code.

Python is a "file platform": the fallback UUID is persisted in a plaintext file
named exactly ``.moss-device-id``. When the client has a cache directory the file
lives at ``<cachePath>/.moss-device-id``; otherwise it falls back to a single
per-user directory ``<home>/.moss/.moss-device-id`` so the device resolves to the
same id across processes (one device, one id -> counts once toward Monthly
Active Devices). The store is per-user / device-local and is never synced.

Modeled on the TypeScript reference
(moss-sdks-internal/javascript/user-facing-sdk/src/utils/deviceId.ts) and the
canonical MOS-14 device-id contract.

NATIVE-BINDING STATUS (as of this change): the pyo3 binding ``moss_core`` does
NOT yet expose a ``set_device_id`` setter on ``IndexManager`` (nor a device-id
constructor). See ``apply_device_id`` / ``apply_device_id_once`` below: the apply
path degrades gracefully (terminal success) when the setter is absent, exactly
as the TS reference tolerates an older core. Full parity requires the Rust
change flagged in the module TODO.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Mapping, Optional, Protocol

# ---------------------------------------------------------------------------
# TODO(MOS-14, native/Rust — needs CI to build the wheel):
#   Add ``set_device_id(&self, device_id: Option<String>)`` to ``PyIndexManager``
#   in moss/sdks/python/bindings/src/indexmanager.rs, delegating to core
#   ``IndexManager::set_device_id`` (verified to exist in moss-sdks-internal:
#   src/manager/indexmanager.rs:256 -> src/telemetry.rs:167). Until that method
#   exists on the built ``moss_core.IndexManager``, ``apply_device_id`` treats
#   the missing setter as terminal success and the id is sourced/persisted but
#   not yet handed to the core.
# ---------------------------------------------------------------------------

DEVICE_ID_FILE = ".moss-device-id"
DEFAULT_DIR_NAME = ".moss"

# Persistence "identity" intent, mirroring the Apple Keychain reference
# (service="dev.moss.sdk", account="device_id"). On file platforms these are
# not separately addressable; the fixed filename ``.moss-device-id`` under the
# ``.moss`` per-user dir plays the same role.
KEYCHAIN_SERVICE_INTENT = "dev.moss.sdk"
KEYCHAIN_ACCOUNT_INTENT = "device_id"

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def telemetry_disabled(env: Optional[Mapping[str, str]] = None) -> bool:
    """True when usage telemetry is disabled via ``MOSS_DISABLE_TELEMETRY``.

    Truthy set = {"1","true","yes","on"}, trimmed + lowercased.
    """
    environ = os.environ if env is None else env
    value = environ.get("MOSS_DISABLE_TELEMETRY")
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY


def default_device_id_dir(env: Optional[Mapping[str, str]] = None) -> Path:
    """Per-user fallback directory for the device-id file (``<home>/.moss``).

    Used when no cache directory is available. ``home`` comes from ``$HOME`` ->
    ``%USERPROFILE%`` -> OS home, with blank values skipped so a blank ``$HOME``
    does not resolve the ``.moss`` dir into the current working directory. A
    single per-user location keeps a device's id stable across processes.
    """
    environ = os.environ if env is None else env

    def _clean(name: str) -> Optional[str]:
        raw = environ.get(name)
        if raw is None:
            return None
        trimmed = raw.strip()
        return trimmed or None

    home = _clean("HOME") or _clean("USERPROFILE")
    if home is None:
        # os.path.expanduser("~") consults the real OS home / password db and
        # does not depend on the (possibly-cleared) env mapping passed in.
        home = os.path.expanduser("~")
    return Path(home) / DEFAULT_DIR_NAME


def resolve_device_id(
    cache_path: str | os.PathLike[str],
    env: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Resolve the stable per-device id persisted at ``<cache_path>/.moss-device-id``.

    Reads an existing UUID, or generates and writes one. Returns ``None`` when
    telemetry is disabled. On a filesystem error, returns a fresh *ephemeral*
    UUID (not persisted) so telemetry can still attribute within this run —
    device-id persistence must never break the client (loadIndex/query).
    """
    if telemetry_disabled(env):
        return None
    try:
        directory = Path(cache_path).expanduser().resolve()
        file = directory / DEVICE_ID_FILE
        if file.exists():
            existing = file.read_text(encoding="utf-8").strip()
            if existing:  # Never send an empty/blank id; regenerate if blank.
                return existing
        directory.mkdir(parents=True, exist_ok=True)
        new_id = str(uuid.uuid4())
        file.write_text(new_id, encoding="utf-8")
        return new_id
    except OSError:
        # Persistence failure must never break the client — fall back to a fresh
        # ephemeral (non-persisted) UUID and continue.
        return str(uuid.uuid4())


class DeviceIdState:
    """Per-client memo state so every telemetry surface reports the same id.

    ``id`` is the resolved device id (once resolved); ``applied`` tracks whether
    the id has been pushed to the core successfully so we don't re-set it.
    """

    __slots__ = ("id", "applied")

    def __init__(self) -> None:
        self.id: Optional[str] = None
        self.applied: bool = False


def resolve_client_device_id(
    state: DeviceIdState,
    cache_path: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Resolve the client's stable device id once and memoize it on ``state``.

    Every surface a client touches reports the same id — one device, one id.
    Persists under ``cache_path`` when given, otherwise under the per-user
    fallback dir. Returns ``None`` (without memoizing) when telemetry is
    disabled. The disabled check runs *before* the memo fast-path so a runtime
    opt-out takes effect immediately.
    """
    if telemetry_disabled(env):
        return None
    if state.id:
        return state.id
    # Treat a blank cache_path as absent (an empty path would resolve to CWD).
    directory: str | os.PathLike[str]
    if cache_path is not None and cache_path.strip():
        directory = cache_path
    else:
        directory = default_device_id_dir(env)
    resolved = resolve_device_id(directory, env)
    if resolved:
        state.id = resolved
    return resolved


class DeviceIdTarget(Protocol):
    """A core binding surface that accepts a device id via ``set_device_id``."""

    def set_device_id(self, device_id: str) -> None: ...


def apply_device_id(target: object, device_id: str) -> bool:
    """Push ``device_id`` to a telemetry ``target``. Best-effort: never raises.

    Returns whether the id is now settled: ``True`` on success, or when the
    target's ``moss_core`` build predates ``set_device_id`` (terminal — a newer
    binding won't appear mid-process, so there's nothing to retry). Returns
    ``False`` only when the call raised, so the caller may retry later.
    """
    setter = getattr(target, "set_device_id", None)
    if not callable(setter):
        # Older core binding without the device-id entry point — treat as
        # terminal success (R5.4). NOTE: the current mono pyo3 binding is in
        # this state until the native TODO above lands.
        return True
    try:
        setter(device_id)
        return True
    except Exception:
        return False


def apply_device_id_once(
    target: object,
    state: DeviceIdState,
    cache_path: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> None:
    """Resolve the device id (once, shared via ``state``) and push it to ``target``.

    No-op once applied or when telemetry is disabled. On a transient failure
    ``state.applied`` stays ``False`` so the next call retries rather than
    permanently suppressing the id. Never raises.
    """
    if state.applied:
        return
    device_id = resolve_client_device_id(state, cache_path, env)
    if not device_id:
        return
    state.applied = apply_device_id(target, device_id)
