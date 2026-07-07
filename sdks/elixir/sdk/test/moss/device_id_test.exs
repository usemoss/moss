defmodule Moss.DeviceIdTest do
  @moduledoc """
  SDK-layer tests for the MOS-14 device-id contract. These exercise
  sourcing / persistence / memoization / opt-out / best-effort apply against a
  fake apply function — exactly as the TS reference `deviceId.test.ts` uses a
  fake `setDeviceId` target — so the contract is verifiable independently of
  the (not-yet-existing) `set_device_id` NIF.
  """
  use ExUnit.Case, async: true

  alias Moss.DeviceId

  @uuid_re ~r/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

  setup do
    dir = Path.join(System.tmp_dir!(), "moss-devid-#{System.unique_integer([:positive])}")
    File.mkdir_p!(dir)
    on_exit(fn -> File.rm_rf(dir) end)
    {:ok, dir: dir}
  end

  # --- resolve/2 (R1, R2.2, R2.4) ---

  test "creates and persists a UUID on first resolve", %{dir: dir} do
    id = DeviceId.resolve(dir, %{})
    assert id =~ @uuid_re
    file = Path.join(dir, ".moss-device-id")
    assert File.exists?(file)
    assert File.read!(file) |> String.trim() == id
  end

  test "returns the same id on subsequent resolves", %{dir: dir} do
    first = DeviceId.resolve(dir, %{})
    assert DeviceId.resolve(dir, %{}) == first
  end

  test "honors a pre-seeded id file", %{dir: dir} do
    File.write!(Path.join(dir, ".moss-device-id"), "preseeded-id-1")
    assert DeviceId.resolve(dir, %{}) == "preseeded-id-1"
  end

  test "treats a blank persisted value as absent and regenerates", %{dir: dir} do
    File.write!(Path.join(dir, ".moss-device-id"), "   \n")
    id = DeviceId.resolve(dir, %{})
    assert id =~ @uuid_re
  end

  test "returns nil when telemetry is disabled and writes nothing", %{dir: dir} do
    assert DeviceId.resolve(dir, %{"MOSS_DISABLE_TELEMETRY" => "true"}) == nil
    refute File.exists?(Path.join(dir, ".moss-device-id"))
  end

  # --- telemetry_disabled?/1 (R4.1) ---

  test "telemetry_disabled? parses common truthy values" do
    assert DeviceId.telemetry_disabled?(%{"MOSS_DISABLE_TELEMETRY" => "1"})
    assert DeviceId.telemetry_disabled?(%{"MOSS_DISABLE_TELEMETRY" => "TRUE"})
    assert DeviceId.telemetry_disabled?(%{"MOSS_DISABLE_TELEMETRY" => " Yes "})
    refute DeviceId.telemetry_disabled?(%{})
    refute DeviceId.telemetry_disabled?(%{"MOSS_DISABLE_TELEMETRY" => "0"})
  end

  # --- resolve_client/3 (R3, R2.3) ---

  test "resolve_client persists under cache_path when provided", %{dir: dir} do
    {id, state} = DeviceId.resolve_client(DeviceId.new_state(), dir, %{})
    assert id =~ @uuid_re
    assert File.read!(Path.join(dir, ".moss-device-id")) |> String.trim() == id
    assert state.id == id
  end

  test "resolve_client memoizes the first id across calls and locations", %{dir: dir} do
    {first, state} = DeviceId.resolve_client(DeviceId.new_state(), dir, %{})
    # A later call with no cache_path must reuse the memoized id — one device, one id.
    {second, _state} =
      DeviceId.resolve_client(state, nil, %{"HOME" => Path.join(dir, "other")})

    assert second == first
    refute File.exists?(Path.join([dir, "other", ".moss", ".moss-device-id"]))
  end

  test "resolve_client returns nil and does not memoize when telemetry disabled", %{dir: dir} do
    {id, state} =
      DeviceId.resolve_client(DeviceId.new_state(), dir, %{"MOSS_DISABLE_TELEMETRY" => "1"})

    assert id == nil
    assert state.id == nil
  end

  test "resolve_client honors runtime disable even after an id was memoized", %{dir: dir} do
    state = %{id: "preset-id", applied: true}
    {id, _} = DeviceId.resolve_client(state, dir, %{"MOSS_DISABLE_TELEMETRY" => "1"})
    assert id == nil
  end

  test "resolve_client treats a blank cache_path as absent, uses fallback dir", %{dir: dir} do
    {id, _} = DeviceId.resolve_client(DeviceId.new_state(), "   ", %{"HOME" => dir})
    assert id =~ @uuid_re
    # persisted under the fallback dir, not the CWD
    assert File.read!(Path.join([dir, ".moss", ".moss-device-id"])) |> String.trim() == id
  end

  # --- apply/2 (R5.3, R5.4) ---

  test "apply pushes the id to the target and reports success" do
    parent = self()
    ok? = DeviceId.apply(fn id -> send(parent, {:applied, id}) && :ok end, "abc")
    assert ok?
    assert_received {:applied, "abc"}
  end

  test "apply treats a nil apply_fun (older/absent binding) as terminal success" do
    assert DeviceId.apply(nil, "abc")
  end

  test "apply treats :unsupported as terminal success" do
    assert DeviceId.apply(fn _ -> :unsupported end, "abc")
  end

  test "apply reports failure when apply_fun raises (so caller can retry)" do
    refute DeviceId.apply(fn _ -> raise "transient binding error" end, "abc")
  end

  test "apply reports failure on {:error, _}" do
    refute DeviceId.apply(fn _ -> {:error, :nope} end, "abc")
  end

  # --- apply_once/4 (R3.2, R3.3) ---

  test "apply_once sets the id exactly once and memoizes", %{dir: dir} do
    parent = self()
    fun = fn id -> send(parent, {:call, id}) && :ok end

    state = DeviceId.apply_once(DeviceId.new_state(), fun, dir, %{})
    state = DeviceId.apply_once(state, fun, dir, %{})

    assert state.applied
    assert_received {:call, id}
    assert id =~ @uuid_re
    refute_received {:call, _}
  end

  test "apply_once does nothing when telemetry disabled", %{dir: dir} do
    parent = self()
    fun = fn id -> send(parent, {:call, id}) && :ok end
    state = DeviceId.apply_once(DeviceId.new_state(), fun, dir, %{"MOSS_DISABLE_TELEMETRY" => "yes"})
    refute state.applied
    refute_received {:call, _}
  end

  test "apply_once marks applied without raising when apply_fun is nil", %{dir: dir} do
    state = DeviceId.apply_once(DeviceId.new_state(), nil, dir, %{})
    assert state.applied
  end

  test "apply_once leaves applied=false (retries) when apply_fun raises", %{dir: dir} do
    parent = self()
    fun = fn _ -> send(parent, :called) && raise("transient") end

    state = DeviceId.apply_once(DeviceId.new_state(), fun, dir, %{})
    refute state.applied
    _ = DeviceId.apply_once(state, fun, dir, %{})
    # called twice: retried on the second call
    assert_received :called
    assert_received :called
  end
end
