defmodule Moss.DeviceId do
  @moduledoc """
  Stable, per-device identifier sourcing for MOS-14 "better tracking" parity.

  This module's ONLY job is to source a stable, persisted, per-device id and
  hand it to the closed core, which owns the actual `/telemetry` POST + buffer
  + 3s flush. The SDK never touches telemetry transport.

  Contract (see the canonical MOS-14 device-id spec):

    * Elixir is a server/CLI platform with no OS-blessed vendor id, so the id
      is a generated UUIDv4 persisted on first use (spec R1.2). There is no
      Apple `identifierForVendor` equivalent here.
    * The id is an opaque string handed through unchanged (R1.3). A blank
      persisted value is treated as absent and regenerated (R1.4).
    * Persistence (R2.2, file-platform class): a plaintext file named exactly
      `.moss-device-id`. When a client cache dir is known it lives at
      `<cachePath>/.moss-device-id`; otherwise it falls back to a single
      per-user dir so a device counts once toward Monthly Active Devices
      (R2.3). The per-user dir mirrors the naming intent `dev.moss.sdk` /
      account `device_id` from the Keychain platforms by using a stable
      `moss` user-cache dir plus a `.moss` fallback.
    * The store is device-scoped and MUST NOT sync/migrate to another device
      (R2). A user-cache / home dir is non-synced by construction.
    * Persistence failure must never break the client: on any error we fall
      back to a fresh ephemeral (non-persisted) UUID (R2.4).
    * `MOSS_DISABLE_TELEMETRY` (truthy set, trimmed + lowercased) is honored,
      checked before the memo fast-path, at runtime: when disabled we source
      no id, do no store I/O, and hand nothing to the core (R4).

  Memoization (R3) and "apply once" tracking are held per-client in the
  GenServer/struct state that calls this module; this module is a pure
  resolver plus a best-effort apply helper.

  NOTE (native binding gap): the mono-repo Elixir NIF does not yet expose a
  `set_device_id` entry point (setter mechanism, R5.2). Until that NIF exists,
  `apply/2` degrades gracefully (R5.4). See `Moss.DeviceId.apply/2` and the
  `MOS-14` TODOs in `Moss.IndexManager` / `Moss.Session` / `Moss.ManageClient`.
  """

  require Logger

  # This module defines a local `apply/2` (best-effort setter invocation); it
  # deliberately shadows Kernel.apply/2, which is not used here.
  import Kernel, except: [apply: 2]

  @device_id_file ".moss-device-id"
  @fallback_dir_name ".moss"
  @user_cache_app "moss"
  @truthy ~w(1 true yes on)

  @typedoc "Per-client device-id memo state: the resolved id and whether it was applied to the core."
  @type state :: %{optional(:id) => String.t() | nil, applied: boolean()}

  @doc """
  True when usage telemetry is disabled via `MOSS_DISABLE_TELEMETRY`.

  Truthy set (trimmed + lowercased): `#{inspect(@truthy)}`. Checked at runtime
  so toggling the env var mid-process takes effect immediately (R4.2).
  """
  @spec telemetry_disabled?() :: boolean()
  def telemetry_disabled?, do: telemetry_disabled?(System.get_env())

  @doc false
  @spec telemetry_disabled?(map()) :: boolean()
  def telemetry_disabled?(env) when is_map(env) do
    case Map.get(env, "MOSS_DISABLE_TELEMETRY") do
      nil -> false
      v -> v |> to_string() |> String.trim() |> String.downcase() |> Kernel.in(@truthy)
    end
  end

  @doc """
  Per-user fallback directory for the device-id file, used when no `cache_path`
  is available (e.g. the session API, which has no cache dir of its own).

  Resolves to a stable, per-user, non-synced location so a device's id is the
  same across processes and surfaces — it counts once toward Monthly Active
  Devices (R2.3). Uses `$XDG_CACHE_HOME/moss` when that env var is set,
  falling back to `<home>/.moss` where `home` = `$HOME` -> `%USERPROFILE%` ->
  OS home, with blank values skipped so a blank `$HOME` does not resolve into
  the CWD (R2.2).
  """
  @spec default_dir() :: String.t()
  def default_dir, do: default_dir(System.get_env())

  @doc false
  @spec default_dir(map()) :: String.t()
  def default_dir(env) when is_map(env) do
    case xdg_cache_home(env) do
      dir when is_binary(dir) -> Path.join(dir, @user_cache_app)
      _ -> Path.join(home_dir(env), @fallback_dir_name)
    end
  end

  @doc """
  Resolve the stable per-device id persisted at `<dir>/.moss-device-id`.

  Reads an existing non-blank UUID, or generates and writes one. Returns `nil`
  when telemetry is disabled (no store I/O). On any filesystem error, returns a
  fresh ephemeral UUID (NOT persisted) so telemetry can still attribute within
  this run — device-id persistence must never break a real operation (R2.4).
  """
  @spec resolve(String.t()) :: String.t() | nil
  def resolve(dir), do: resolve(dir, System.get_env())

  @doc false
  @spec resolve(String.t(), map()) :: String.t() | nil
  def resolve(dir, env) when is_binary(dir) and is_map(env) do
    if telemetry_disabled?(env) do
      nil
    else
      do_resolve(Path.expand(dir))
    end
  end

  defp do_resolve(dir) do
    file = Path.join(dir, @device_id_file)

    case read_existing(file) do
      {:ok, existing} ->
        existing

      :none ->
        write_new(dir, file)
    end
  rescue
    # Any unexpected error must not break the client: fall back to an ephemeral id.
    e ->
      Logger.debug("Moss.DeviceId: persistence failed (#{inspect(e)}); using ephemeral id")
      generate_uuid()
  end

  defp read_existing(file) do
    case File.read(file) do
      {:ok, contents} ->
        trimmed = String.trim(contents)
        # A persisted value that reads back empty is treated as absent (R1.4).
        if trimmed == "", do: :none, else: {:ok, trimmed}

      {:error, _} ->
        :none
    end
  end

  defp write_new(dir, file) do
    id = generate_uuid()

    case File.mkdir_p(dir) do
      :ok ->
        case File.write(file, id) do
          :ok -> id
          # Write failed: still return the (ephemeral) id rather than crashing.
          {:error, _} -> id
        end

      {:error, _} ->
        id
    end
  end

  @doc """
  Resolve the client's device id ONCE and memoize it on `state`, so every
  telemetry surface a client touches (the IndexManager, ManageClient, and any
  sessions) reports the same id — one device, one id (R3.1, R5.5).

  Persists under `cache_path` when a non-blank one is given, otherwise under
  `default_dir/0`. Returns `{id_or_nil, new_state}`. Returns `nil` (without
  memoizing) when telemetry is disabled, and — because the disabled-check runs
  before the memo fast-path — a runtime opt-out takes effect immediately even
  after an id was memoized (R3.3, R4.2).
  """
  @spec resolve_client(state(), String.t() | nil) :: {String.t() | nil, state()}
  def resolve_client(state, cache_path), do: resolve_client(state, cache_path, System.get_env())

  @doc false
  @spec resolve_client(state(), String.t() | nil, map()) :: {String.t() | nil, state()}
  def resolve_client(state, cache_path, env) when is_map(state) and is_map(env) do
    cond do
      # Disabled-check first, before the memo fast-path (R4.2).
      telemetry_disabled?(env) ->
        {nil, state}

      is_binary(Map.get(state, :id)) ->
        {state.id, state}

      true ->
        dir =
          case cache_path do
            p when is_binary(p) -> if String.trim(p) == "", do: default_dir(env), else: p
            _ -> default_dir(env)
          end

        case resolve(dir, env) do
          nil -> {nil, state}
          id -> {id, Map.put(state, :id, id)}
        end
    end
  end

  @doc """
  Best-effort push of `id` to the core via `apply_fun`, which should call the
  binding's setter NIF (setter mechanism, R5.2). Never raises (R5.3).

  Returns `true` when the id is now settled — on success, OR when the setter is
  not available in this build (an older/mono NIF that predates the device-id
  entry point: terminal, nothing to retry, R5.4). Returns `false` only when the
  apply raised, so the caller may retry later (R3.3).

  `apply_fun` is an arity-1 function returning one of:

    * `:ok` / `{:ok, _}`         -> success
    * `:unsupported`             -> setter not present in this build (terminal success)
    * `{:error, _}` / raises     -> transient failure (retry)

  Passing `nil` (no setter wired at all) is treated as `:unsupported`, so the
  SDK-layer sourcing/persistence is fully exercisable and MOS-14-compliant now,
  and flips to real applies the moment the `set_device_id` NIF lands.
  """
  @spec apply((String.t() -> term()) | nil, String.t()) :: boolean()
  def apply(nil, _id), do: true

  def apply(apply_fun, id) when is_function(apply_fun, 1) and is_binary(id) do
    case apply_fun.(id) do
      :ok -> true
      {:ok, _} -> true
      :unsupported -> true
      _ -> false
    end
  rescue
    e ->
      Logger.debug("Moss.DeviceId: apply failed (#{inspect(e)}); will retry")
      false
  end

  @doc """
  Resolve the device id (once, shared via `state`) and push it to the core via
  `apply_fun`. No-op once applied or when telemetry is disabled (R3.2).

  On a transient apply failure `state.applied` stays `false` so the next call
  retries rather than permanently suppressing the id (R3.3). Returns the new
  `state`.
  """
  @spec apply_once(state(), (String.t() -> term()) | nil, String.t() | nil) :: state()
  def apply_once(state, apply_fun, cache_path),
    do: apply_once(state, apply_fun, cache_path, System.get_env())

  @doc false
  @spec apply_once(state(), (String.t() -> term()) | nil, String.t() | nil, map()) :: state()
  def apply_once(state, apply_fun, cache_path, env) when is_map(state) and is_map(env) do
    if Map.get(state, :applied, false) do
      state
    else
      {id, state} = resolve_client(state, cache_path, env)

      case id do
        nil -> state
        _ -> Map.put(state, :applied, apply(apply_fun, id))
      end
    end
  end

  @doc "A fresh, empty per-client memo state."
  @spec new_state() :: state()
  def new_state, do: %{id: nil, applied: false}

  # ---------------------------------------------------------------------------
  # Private helpers
  # ---------------------------------------------------------------------------

  # `||` semantics: blank ("" after trim) $HOME / %USERPROFILE% must fall
  # through to the OS home rather than producing a relative ".moss" that would
  # land in the CWD (R2.2).
  defp home_dir(env) do
    trimmed = fn key ->
      case Map.get(env, key) do
        v when is_binary(v) ->
          t = String.trim(v)
          if t == "", do: nil, else: t

        _ ->
          nil
      end
    end

    trimmed.("HOME") || trimmed.("USERPROFILE") || System.user_home!() || System.tmp_dir!()
  end

  # Honors $XDG_CACHE_HOME from the (injectable) env for testability and Linux
  # convention; blank/absent falls through to <home>/.moss (R2.2).
  defp xdg_cache_home(env) do
    case Map.get(env, "XDG_CACHE_HOME") do
      v when is_binary(v) ->
        t = String.trim(v)
        if t == "", do: nil, else: t

      _ ->
        nil
    end
  end

  # UUIDv4, opaque string, returned as-is (R1.2, R1.3). Uses the same `uniq`
  # dep the SDK already relies on for client_id.
  defp generate_uuid, do: Uniq.UUID.uuid4()
end
