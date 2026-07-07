"""Unit tests for the MOS-14 device-id util (moss.client.device_id).

Modeled on the TypeScript reference test
(moss-sdks-internal/javascript/user-facing-sdk/test/deviceId.test.ts). These
tests are self-contained (stdlib + a fake set_device_id target) and do not
require the native moss_core binding.
"""

from __future__ import annotations

import uuid

import pytest

from moss.client.device_id import (
    DEVICE_ID_FILE,
    DeviceIdState,
    apply_device_id,
    apply_device_id_once,
    default_device_id_dir,
    resolve_client_device_id,
    resolve_device_id,
    telemetry_disabled,
)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


# -- telemetry_disabled ------------------------------------------------


class TestTelemetryDisabled:
    @pytest.mark.parametrize("val", ["1", "true", "TRUE", "  Yes ", "on"])
    def test_truthy_values_disable(self, val):
        assert telemetry_disabled({"MOSS_DISABLE_TELEMETRY": val}) is True

    @pytest.mark.parametrize("val", ["", "0", "false", "no", "off", "nope"])
    def test_falsy_values_enabled(self, val):
        assert telemetry_disabled({"MOSS_DISABLE_TELEMETRY": val}) is False

    def test_absent_is_enabled(self):
        assert telemetry_disabled({}) is False


# -- resolve_device_id -------------------------------------------------


class TestResolveDeviceId:
    def test_generates_and_persists_uuid(self, tmp_path):
        got = resolve_device_id(tmp_path, env={})
        assert got is not None and _is_uuid(got)
        assert (tmp_path / DEVICE_ID_FILE).read_text(encoding="utf-8") == got

    def test_stable_across_resolves(self, tmp_path):
        first = resolve_device_id(tmp_path, env={})
        second = resolve_device_id(tmp_path, env={})
        assert first == second

    def test_reads_existing_file(self, tmp_path):
        (tmp_path / DEVICE_ID_FILE).write_text("preexisting-id", encoding="utf-8")
        assert resolve_device_id(tmp_path, env={}) == "preexisting-id"

    def test_blank_existing_is_regenerated(self, tmp_path):
        (tmp_path / DEVICE_ID_FILE).write_text("   \n", encoding="utf-8")
        got = resolve_device_id(tmp_path, env={})
        assert got is not None and _is_uuid(got)

    def test_disabled_returns_none_and_writes_nothing(self, tmp_path):
        got = resolve_device_id(tmp_path, env={"MOSS_DISABLE_TELEMETRY": "1"})
        assert got is None
        assert not (tmp_path / DEVICE_ID_FILE).exists()


# -- default_device_id_dir ---------------------------------------------


class TestDefaultDeviceIdDir:
    def test_uses_home(self):
        d = default_device_id_dir({"HOME": "/home/alice"})
        assert str(d) == "/home/alice/.moss"

    def test_blank_home_falls_through(self, monkeypatch):
        # A blank HOME must not resolve `.moss` into the CWD; it falls through
        # to the real OS home via expanduser.
        d = default_device_id_dir({"HOME": "   "})
        assert d.name == ".moss"
        assert d.is_absolute()

    def test_userprofile_fallback(self):
        d = default_device_id_dir({"USERPROFILE": "/Users/bob"})
        assert str(d) == "/Users/bob/.moss"


# -- resolve_client_device_id (memoization) ----------------------------


class TestResolveClientDeviceId:
    def test_memoizes_on_state(self, tmp_path):
        state = DeviceIdState()
        first = resolve_client_device_id(state, str(tmp_path), env={})
        assert first == state.id
        # Corrupt the file; memoized value must be returned without re-reading.
        (tmp_path / DEVICE_ID_FILE).write_text("changed", encoding="utf-8")
        second = resolve_client_device_id(state, str(tmp_path), env={})
        assert second == first

    def test_disabled_checked_before_memo(self, tmp_path):
        state = DeviceIdState()
        state.id = "memoized"
        got = resolve_client_device_id(
            state, str(tmp_path), env={"MOSS_DISABLE_TELEMETRY": "1"}
        )
        assert got is None

    def test_blank_cache_path_uses_default_dir(self, tmp_path):
        state = DeviceIdState()
        got = resolve_client_device_id(state, "  ", env={"HOME": str(tmp_path)})
        assert got is not None
        assert (tmp_path / ".moss" / DEVICE_ID_FILE).exists()


# -- apply_device_id ---------------------------------------------------


class _FakeTarget:
    def __init__(self):
        self.calls = []

    def set_device_id(self, device_id):
        self.calls.append(device_id)


class _ThrowingTarget:
    def set_device_id(self, device_id):
        raise RuntimeError("boom")


class _NoSetterTarget:
    pass


class TestApplyDeviceId:
    def test_calls_setter(self):
        t = _FakeTarget()
        assert apply_device_id(t, "abc") is True
        assert t.calls == ["abc"]

    def test_missing_setter_is_terminal_success(self):
        assert apply_device_id(_NoSetterTarget(), "abc") is True

    def test_throwing_setter_returns_false(self):
        assert apply_device_id(_ThrowingTarget(), "abc") is False


# -- apply_device_id_once ----------------------------------------------


class TestApplyDeviceIdOnce:
    def test_applies_and_marks(self, tmp_path):
        t = _FakeTarget()
        state = DeviceIdState()
        apply_device_id_once(t, state, str(tmp_path), env={})
        assert state.applied is True
        assert len(t.calls) == 1

    def test_no_op_once_applied(self, tmp_path):
        t = _FakeTarget()
        state = DeviceIdState()
        apply_device_id_once(t, state, str(tmp_path), env={})
        apply_device_id_once(t, state, str(tmp_path), env={})
        assert len(t.calls) == 1

    def test_disabled_does_not_apply(self, tmp_path):
        t = _FakeTarget()
        state = DeviceIdState()
        apply_device_id_once(
            t, state, str(tmp_path), env={"MOSS_DISABLE_TELEMETRY": "1"}
        )
        assert state.applied is False
        assert t.calls == []
        assert not (tmp_path / DEVICE_ID_FILE).exists()

    def test_failed_apply_leaves_retryable(self, tmp_path):
        t = _ThrowingTarget()
        state = DeviceIdState()
        apply_device_id_once(t, state, str(tmp_path), env={})
        assert state.applied is False  # retryable

    def test_missing_setter_binding_is_terminal_success(self, tmp_path):
        t = _NoSetterTarget()
        state = DeviceIdState()
        apply_device_id_once(t, state, str(tmp_path), env={})
        assert state.applied is True  # nothing to retry
