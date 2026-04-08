defmodule Moss.IndexManager do
  @moduledoc false

  use GenServer

  alias MossCore.Nif

  # ---------------------------------------------------------------------------
  # Public API
  # ---------------------------------------------------------------------------

  @doc """
  Start an IndexManager GenServer.

  Required options:
    - `:project_id`
    - `:project_key`

  Optional:
    - `:base_url` — override the default cloud API URL
    - `:server_name` — GenServer name registration
  """
  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(opts) do
    {server_name_opts, opts} =
      case Keyword.pop(opts, :server_name) do
        {nil, rest} -> {[], rest}
        {name, rest} -> {[name: name], rest}
      end

    GenServer.start_link(__MODULE__, opts, server_name_opts)
  end

  @doc """
  Load a cloud index into memory.

  Options:
    - `:auto_refresh` (boolean, default false)
    - `:polling_interval` (integer seconds, default 600)

  Returns `{:ok, Moss.IndexInfo.t()}` or `{:error, reason}`.
  """
  @spec load_index(GenServer.server(), String.t(), keyword()) ::
          {:ok, Moss.IndexInfo.t()} | {:error, String.t()}
  def load_index(pid, index_name, opts \\ []) do
    auto_refresh = Keyword.get(opts, :auto_refresh, false)
    polling_interval = Keyword.get(opts, :polling_interval, 600)
    GenServer.call(pid, {:load_index, index_name, auto_refresh, polling_interval}, :infinity)
  end

  @doc "Unload an index from memory."
  @spec unload_index(GenServer.server(), String.t()) :: {:ok, :ok} | {:error, String.t()}
  def unload_index(pid, index_name) do
    GenServer.call(pid, {:unload_index, index_name}, :infinity)
  end

  @doc "Check if an index is loaded."
  @spec has_index(GenServer.server(), String.t()) :: boolean()
  def has_index(pid, index_name) do
    GenServer.call(pid, {:has_index, index_name}, :infinity)
  end

  @doc """
  Query a loaded index.

  For built-in models, the query is embedded automatically in Rust. For indexes
  created with `model_id: "custom"`, pass the query embedding via `embedding: [...]`.

  Options:
    - `:top_k` (integer, default 5)
    - `:alpha` (float, default 0.8)
    - `:filter` (map)
    - `:embedding` (list of floats, required for `model_id: "custom"`)

  Returns `{:ok, Moss.SearchResult.t()}` or `{:error, reason}`.
  """
  @spec query(GenServer.server(), String.t(), String.t(), keyword()) ::
          {:ok, Moss.SearchResult.t()} | {:error, String.t()}
  def query(pid, index_name, query_text, opts \\ []) do
    top_k = Keyword.get(opts, :top_k, 5)
    alpha = Keyword.get(opts, :alpha, 0.8)
    filter = Keyword.get(opts, :filter, nil)
    embedding = Keyword.get(opts, :embedding, nil)
    GenServer.call(pid, {:query, index_name, query_text, embedding, top_k, alpha, filter}, :infinity)
  end

  @doc false
  @spec load_query_model(GenServer.server(), String.t()) :: {:ok, :ok} | {:error, String.t()}
  def load_query_model(pid, index_name) do
    GenServer.call(pid, {:load_query_model, index_name}, :infinity)
  end

  @doc "Force an immediate refresh of a loaded index from the cloud."
  @spec refresh_index(GenServer.server(), String.t()) ::
          {:ok, Moss.RefreshResult.t()} | {:error, String.t()}
  def refresh_index(pid, index_name) do
    GenServer.call(pid, {:refresh_index, index_name}, :infinity)
  end

  @doc "Get metadata for a loaded index."
  @spec get_index_info(GenServer.server(), String.t()) ::
          {:ok, Moss.IndexInfo.t()} | {:error, String.t()}
  def get_index_info(pid, index_name) do
    GenServer.call(pid, {:get_index_info, index_name}, :infinity)
  end

  # ---------------------------------------------------------------------------
  # GenServer callbacks
  # ---------------------------------------------------------------------------

  @impl true
  def init(opts) do
    project_id = Keyword.fetch!(opts, :project_id)
    project_key = Keyword.fetch!(opts, :project_key)
    base_url = Keyword.get(opts, :base_url, nil)
    client_id = Keyword.get(opts, :client_id, nil)

    case Nif.manager_new(project_id, project_key, base_url, client_id) do
      {:ok, ref} -> {:ok, %{ref: ref}}
      {:error, reason} -> {:stop, reason}
    end
  end

  @impl true
  def handle_call({:load_index, index_name, auto_refresh, polling_interval}, _from, state) do
    reply =
      case Nif.manager_load_index(state.ref, index_name, auto_refresh, polling_interval) do
        {:ok, info} ->
          if built_in_model?(info) do
            case Nif.manager_load_query_model(state.ref, index_name) do
              {:ok, :ok} -> {:ok, info}
              {:error, reason} -> {:error, reason}
            end
          else
            {:ok, info}
          end

        {:error, reason} ->
          {:error, reason}
      end

    {:reply, reply, state}
  end

  def handle_call({:unload_index, index_name}, _from, state) do
    {:reply, Nif.manager_unload_index(state.ref, index_name), state}
  end

  def handle_call({:has_index, index_name}, _from, state) do
    {:reply, Nif.manager_has_index(state.ref, index_name), state}
  end

  def handle_call({:query, index_name, query_text, nil, top_k, alpha, filter}, _from, state) do
    reply =
      state.ref
      |> Nif.manager_query_text(index_name, query_text, top_k, alpha, filter)
      |> normalize_query_text_error()

    {:reply, reply, state}
  end

  def handle_call({:query, index_name, query_text, embedding, top_k, alpha, filter}, _from, state) do
    {:reply,
     Nif.manager_query(state.ref, index_name, query_text, embedding, top_k, alpha, filter),
     state}
  end

  def handle_call({:load_query_model, index_name}, _from, state) do
    {:reply, Nif.manager_load_query_model(state.ref, index_name), state}
  end

  def handle_call({:refresh_index, index_name}, _from, state) do
    {:reply, Nif.manager_refresh_index(state.ref, index_name), state}
  end

  def handle_call({:get_index_info, index_name}, _from, state) do
    {:reply, Nif.manager_get_index_info(state.ref, index_name), state}
  end

  # ---------------------------------------------------------------------------
  # Private helpers
  # ---------------------------------------------------------------------------

  defp normalize_query_text_error({:error, reason}) when is_binary(reason) do
    if String.contains?(reason, "requires explicit query embeddings") and
         not String.contains?(reason, "Pass embedding:") do
      {:error, reason <> " Pass embedding: [...] in query opts."}
    else
      {:error, reason}
    end
  end

  defp normalize_query_text_error(result), do: result

  defp built_in_model?(%Moss.IndexInfo{model: %Moss.ModelRef{id: model_id}}) do
    model_id in ["moss-minilm", "moss-mediumlm"]
  end

  defp built_in_model?(_), do: false
end
