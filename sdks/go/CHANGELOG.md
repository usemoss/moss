# Changelog

All notable changes to the Moss Go SDK are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- Device-id contract (MOS-14 "better tracking" parity). The SDK now sources a
  stable, persisted, per-device id and hands it to the core at construction via
  the device-id constructor (`moss_client_new_with_device_id`). Both
  `NewIndexManager` and `NewManageClient` route through this path.
  - The id is a UUIDv4 persisted in a plaintext file `.moss-device-id` under
    `$XDG_CACHE_HOME/moss` (when set) else `<home>/.moss` — a non-synced,
    per-user, per-device location. This is the same scheme as the
    JS/Python/Elixir SDKs, so one physical device resolves to a single id
    across languages (the metric this contract keeps accurate).
  - Honors `MOSS_DISABLE_TELEMETRY` (truthy set `{1,true,yes,on}`, trimmed and
    lowercased): when disabled, no id is sourced, no store I/O happens, and the
    plain `moss_client_new` constructor is used instead.
  - Memoized once per process; persistence failures fall back to an ephemeral
    (non-persisted) UUID and never fail client construction.
  - The SDK contains no telemetry HTTP/buffer/flush/event-composition code; the
    closed core owns transport.

### Notes

- The device-id constructor requires a `libmoss` build whose header declares
  `moss_client_new_with_device_id`. The mono repo does not vendor `libmoss.h`
  (it is supplied at build time), so linking against an older `libmoss` that
  predates the device-id ABI will fail at cgo compile time. See
  `bindings/libmoss.go` for details.
