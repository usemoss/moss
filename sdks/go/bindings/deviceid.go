package mosscore

// Device-id sourcing for MOS-14 "better tracking" parity.
//
// The closed Moss core owns the actual /telemetry POST, buffering, and 3s
// flush. This file's ONLY job is to source a stable, persisted, per-device id
// and hand it to the core through the native binding's device-id entry point
// (the constructor mechanism, R5.1 of the device-id contract). It contains
// zero telemetry HTTP/buffer/flush/event-composition code (N6).
//
// Go has no OS-blessed per-vendor id (R1.1 does not apply), so the id is a
// generated UUIDv4 persisted on first use (R1.2), stored in a plaintext file
// in a non-synced, per-user location (R2): $XDG_CACHE_HOME/moss/.moss-device-id
// when that env var is set, else <home>/.moss/.moss-device-id — the SAME scheme
// as the JS/Python/Elixir SDKs so one physical device resolves to a single id
// across languages (R2.3), the metric this contract exists to keep accurate.
//
// Reference implementations:
//   - Swift (constructor mechanism, Keychain persistence):
//     moss/sdks/swift/Sources/Moss/MossClient.swift stableDeviceId() 203-247.
//   - TypeScript (file persistence + opt-out semantics):
//     moss-sdks-internal/javascript/user-facing-sdk/src/utils/deviceId.ts.

import (
	"crypto/rand"
	"encoding/hex"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

const (
	// deviceIDDirName is the per-user subdirectory (under <home>) that holds
	// the device-id file, matching the JS/Python/Elixir SDKs so a single
	// physical device resolves to ONE id across languages (R2.3).
	deviceIDDirName = ".moss"
	// deviceIDCacheApp is the subdirectory used under $XDG_CACHE_HOME when set.
	deviceIDCacheApp = "moss"
	// deviceIDFileName is the plaintext file holding the persisted UUID,
	// identical to the other SDKs' ".moss-device-id".
	deviceIDFileName = ".moss-device-id"
	// disableTelemetryEnv, when truthy, opts the process out entirely: no id
	// is sourced, no store I/O happens, and no device-id ctor is called.
	// (R4.1, deviceId.ts:8-14.)
	disableTelemetryEnv = "MOSS_DISABLE_TELEMETRY"
)

// truthyTelemetryDisable is the set of values (trimmed + lowercased) that count
// as "telemetry disabled". Mirrors deviceId.ts:8 (`{"1","true","yes","on"}`).
var truthyTelemetryDisable = map[string]bool{
	"1":    true,
	"true": true,
	"yes":  true,
	"on":   true,
}

// telemetryDisabled reports whether MOSS_DISABLE_TELEMETRY is set to a truthy
// value (trimmed, lowercased). Checked at runtime before sourcing (R4.1/R4.2).
func telemetryDisabled() bool {
	return truthyTelemetryDisable[strings.ToLower(strings.TrimSpace(os.Getenv(disableTelemetryEnv)))]
}

var (
	deviceIDOnce  sync.Once
	deviceIDCache string
	deviceIDIsSet bool
)

// stableDeviceID resolves this device's stable id, memoized once per process
// (R3.1). Returns ("", false) when telemetry is disabled (R4.1) — callers must
// then use the non-device-id constructor. Returns (id, true) otherwise.
//
// Because the disable check must take effect at runtime (R4.2), it runs BEFORE
// the memo fast-path: toggling the env var mid-process immediately stops
// attribution even after an id was memoized.
func stableDeviceID() (string, bool) {
	if telemetryDisabled() {
		return "", false
	}
	deviceIDOnce.Do(func() {
		deviceIDCache = resolveDeviceID()
		deviceIDIsSet = deviceIDCache != ""
	})
	return deviceIDCache, deviceIDIsSet
}

// resolveDeviceID reads an existing persisted UUID or generates and persists a
// new one. On any persistence error it falls back to a fresh ephemeral
// (non-persisted) UUID so client construction never fails over device-id
// plumbing (R2.4, deviceId.ts:39-41). An empty/blank stored value is treated
// as absent and regenerated (R1.4, MossClient.swift:228-230).
func resolveDeviceID() string {
	dir, err := deviceIDDir()
	if err != nil {
		return newUUID()
	}
	file := filepath.Join(dir, deviceIDFileName)

	if data, err := os.ReadFile(file); err == nil {
		if existing := strings.TrimSpace(string(data)); existing != "" {
			return existing
		}
	}

	id := newUUID()
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return id // ephemeral: persistence failed, but never break the client
	}
	if err := os.WriteFile(file, []byte(id), 0o600); err != nil {
		return id // ephemeral
	}
	return id
}

// deviceIDDir returns the non-synced, per-user directory that holds the
// device-id file: $XDG_CACHE_HOME/moss when that env var is set, else
// <home>/.moss. This matches the JS/Python/Elixir SDKs so one physical device
// resolves to a single id (R2.3). home = $HOME -> %USERPROFILE% -> OS home,
// with blank values skipped so a blank $HOME never resolves into the CWD (R2).
func deviceIDDir() (string, error) {
	if xdg := strings.TrimSpace(os.Getenv("XDG_CACHE_HOME")); xdg != "" {
		return filepath.Join(xdg, deviceIDCacheApp), nil
	}
	home, err := homeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, deviceIDDirName), nil
}

// homeDir resolves the user home, skipping blank env values so a blank $HOME
// never resolves into the CWD (R2).
func homeDir() (string, error) {
	if h := strings.TrimSpace(os.Getenv("HOME")); h != "" {
		return h, nil
	}
	if h := strings.TrimSpace(os.Getenv("USERPROFILE")); h != "" {
		return h, nil
	}
	return os.UserHomeDir()
}

// newUUID returns a fresh random UUIDv4 as an opaque string, handed through
// unchanged (R1.2/R1.3, deviceId.ts:36, MossClient.swift:233). Implemented
// from crypto/rand (stdlib only) to avoid an external module dependency.
func newUUID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		// crypto/rand should not fail; if it does the id would be all-zero,
		// which is still a valid opaque string and never breaks the client.
		return "00000000-0000-4000-8000-000000000000"
	}
	// Set the RFC 4122 version (4) and variant (10xx) bits.
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80

	var buf [36]byte
	hex.Encode(buf[0:8], b[0:4])
	buf[8] = '-'
	hex.Encode(buf[9:13], b[4:6])
	buf[13] = '-'
	hex.Encode(buf[14:18], b[6:8])
	buf[18] = '-'
	hex.Encode(buf[19:23], b[8:10])
	buf[23] = '-'
	hex.Encode(buf[24:36], b[10:16])
	return string(buf[:])
}
