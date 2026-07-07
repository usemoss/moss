package mosscore

import (
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"testing"
)

var uuidRE = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`)

// redirectConfigDir points device-id persistence at a temp dir and keeps the
// test hermetic. deviceIDDir uses $XDG_CACHE_HOME/moss when set, else
// <home>/.moss, so we clear XDG_CACHE_HOME and set HOME/USERPROFILE at the temp
// dir; the file then lands at <dir>/.moss/.moss-device-id on every platform.
func redirectConfigDir(t *testing.T, dir string) {
	t.Helper()
	t.Setenv("XDG_CACHE_HOME", "")
	t.Setenv("HOME", dir)
	if runtime.GOOS == "windows" {
		t.Setenv("USERPROFILE", dir)
	}
}

func TestNewUUIDFormat(t *testing.T) {
	id := newUUID()
	if !uuidRE.MatchString(id) {
		t.Fatalf("newUUID() = %q, want a UUIDv4", id)
	}
	if newUUID() == id {
		t.Fatalf("newUUID() returned the same value twice: %q", id)
	}
}

func TestTelemetryDisabledParsesTruthy(t *testing.T) {
	cases := map[string]bool{
		"1": true, "true": true, "TRUE": true, "  yes  ": true, "on": true,
		"0": false, "false": false, "": false, "off": false,
	}
	for v, want := range cases {
		t.Setenv(disableTelemetryEnv, v)
		if got := telemetryDisabled(); got != want {
			t.Errorf("telemetryDisabled() with %q = %v, want %v", v, got, want)
		}
	}
}

func TestResolveDeviceIDPersistsAndReuses(t *testing.T) {
	dir := t.TempDir()
	redirectConfigDir(t, dir)
	t.Setenv(disableTelemetryEnv, "")

	first := resolveDeviceID()
	if !uuidRE.MatchString(first) {
		t.Fatalf("resolveDeviceID() = %q, want a UUIDv4", first)
	}
	// A second resolve must read back the same persisted id (cross-process
	// stability; memoization is separate, tested below).
	second := resolveDeviceID()
	if second != first {
		t.Fatalf("resolveDeviceID() not stable: %q then %q", first, second)
	}

	base, err := deviceIDDir()
	if err != nil {
		t.Fatalf("deviceIDDir() error: %v", err)
	}
	file := filepath.Join(base, deviceIDFileName)
	data, err := os.ReadFile(file)
	if err != nil {
		t.Fatalf("device-id file not written at %s: %v", file, err)
	}
	if string(data) != first {
		t.Fatalf("persisted id = %q, want %q", string(data), first)
	}
	// Cross-SDK scheme: dir ".moss", file ".moss-device-id" (matches JS/Python/Elixir).
	if filepath.Base(base) != ".moss" || filepath.Base(file) != ".moss-device-id" {
		t.Fatalf("unexpected path %s", file)
	}
}

func TestResolveDeviceIDHonorsPreseededFile(t *testing.T) {
	dir := t.TempDir()
	redirectConfigDir(t, dir)
	base, err := deviceIDDir()
	if err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(base, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(base, deviceIDFileName), []byte("preseeded-id-1\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if got := resolveDeviceID(); got != "preseeded-id-1" {
		t.Fatalf("resolveDeviceID() = %q, want trimmed preseeded value", got)
	}
}

func TestResolveDeviceIDRegeneratesBlankFile(t *testing.T) {
	dir := t.TempDir()
	redirectConfigDir(t, dir)
	base, err := deviceIDDir()
	if err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(base, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(base, deviceIDFileName), []byte("   \n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if got := resolveDeviceID(); !uuidRE.MatchString(got) {
		t.Fatalf("blank file should regenerate a UUID, got %q", got)
	}
}

func TestStableDeviceIDDisabled(t *testing.T) {
	dir := t.TempDir()
	redirectConfigDir(t, dir)
	t.Setenv(disableTelemetryEnv, "1")

	id, ok := stableDeviceID()
	if ok || id != "" {
		t.Fatalf("stableDeviceID() with telemetry disabled = (%q, %v), want (\"\", false)", id, ok)
	}
	// No store I/O when disabled: the config dir must not exist.
	base, err := deviceIDDir()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(base, deviceIDFileName)); !os.IsNotExist(err) {
		t.Fatalf("device-id file should not be written when telemetry disabled")
	}
}
