defmodule Moss.Session do
  @moduledoc """
  Local in-session index — index documents in memory during a session and
  query them with no cloud round trips.

  Sessions are opened via `Moss.Client.session/3`, which handles credentials
  and auto-loading from the cloud:

      {:ok, session} = Moss.Client.session(client, "session-abc", model_id: "moss-minilm")

      docs = [%Moss.DocumentInfo{id: "1", text: "hello"}]
      {:ok, {1, 0}} = Moss.Session.add_docs(session, docs)

      {:ok, result} = Moss.Session.query(session, "hello")
      {:ok, push_result} = Moss.Session.push_index(session)

  For `model_id: "custom"`, each document must have `.embedding` set and
  `query/3` requires `embedding: [...]` in opts.
  """

  use GenServer

  alias MossCore.Nif

  @doc false
  def child_spec(opts), do: super(opts)

  # ---------------------------------------------------------------------------
  # Public API
  # ---------------------------------------------------------------------------

  @doc false
  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(opts) do
    {server_name_opts, opts} =
      case Keyword.pop(opts, :server_name) do
        {nil, rest} -> {[], rest}
        {name, rest} -> {[name: name], rest}
      end

    GenServer.start_link(__MODULE__, opts, server_name_opts)
  end

  @doc "Number of documents in the session index."
  @spec doc_count(GenServer.server()) :: non_neg_integer()
  def doc_count(pid) do
    GenServer.call(pid, :doc_count)
  end

  @doc "The index name."
  @spec name(GenServer.server()) :: String.t()
  def name(pid) do
    GenServer.call(pid, :name)
  end

  @doc """
  Add documents to the session index.

  For built-in models (`"moss-minilm"`, `"moss-mediumlm"`), embeddings are
  computed automatically in Rust. For `model_id: "custom"`, each document must
  have `.embedding` set.

  Options:
    - `:upsert` (boolean, default true)

  Returns `{:ok, {added, updated}}` or `{:error, reason}`.
  """
  @spec add_docs(GenServer.server(), list(), keyword()) ::
          {:ok, {non_neg_integer(), non_neg_integer()}} | {:error, String.t()}
  def add_docs(pid, docs, opts \\ []) do
    upsert = Keyword.get(opts, :upsert, true)
    GenServer.call(pid, {:add_docs, docs, upsert}, :infinity)
  end

  @doc "Delete documents by IDs. Returns the count deleted."
  @spec delete_docs(GenServer.server(), list(String.t())) :: non_neg_integer()
  def delete_docs(pid, doc_ids) do
    GenServer.call(pid, {:delete_docs, doc_ids})
  end

  @doc """
  Get documents from the index.

  Options:
    - `:doc_ids` (list of strings)
  """
  @spec get_docs(GenServer.server(), keyword()) :: list(Moss.DocumentInfo.t())
  def get_docs(pid, opts \\ []) do
    doc_ids = Keyword.get(opts, :doc_ids, nil)
    GenServer.call(pid, {:get_docs, doc_ids})
  end

  @doc """
  Query the session index.

  For built-in models, the query is embedded automatically in Rust. For
  `model_id: "custom"`, pass the query embedding via `embedding: [...]`.

  Options:
    - `:top_k` (integer, default 5)
    - `:alpha` (float, default 0.8)
    - `:filter` (map)
    - `:embedding` (list of floats, required for `model_id: "custom"`)

  Returns `{:ok, Moss.SearchResult.t()}` or `{:error, reason}`.
  """
  @spec query(GenServer.server(), String.t(), keyword()) ::
          {:ok, Moss.SearchResult.t()} | {:error, String.t()}
  def query(pid, query_text, opts \\ []) do
    top_k = Keyword.get(opts, :top_k, 5)
    alpha = Keyword.get(opts, :alpha, 0.8)
    filter = Keyword.get(opts, :filter, nil)
    embedding = Keyword.get(opts, :embedding, nil)
    GenServer.call(pid, {:query, query_text, embedding, top_k, alpha, filter}, :infinity)
  end

  @doc false
  @spec load_model(GenServer.server()) :: {:ok, :ok} | {:error, String.t()}
  def load_model(pid) do
    GenServer.call(pid, :load_model, :infinity)
  end

  @doc """
  Load an existing cloud index into this session.

  Returns `{:ok, doc_count}` or `{:error, reason}`.
  """
  @spec load_index(GenServer.server(), String.t()) ::
          {:ok, non_neg_integer()} | {:error, String.t()}
  def load_index(pid, index_name) do
    GenServer.call(pid, {:load_index, index_name}, :infinity)
  end

  @doc """
  Push the local session index to the cloud.

  Returns `{:ok, Moss.PushIndexResult.t()}` or `{:error, reason}`.
  """
  @spec push_index(GenServer.server()) ::
          {:ok, Moss.PushIndexResult.t()} | {:error, String.t()}
  def push_index(pid) do
    GenServer.call(pid, :push_index, :infinity)
  end

  # ---------------------------------------------------------------------------
  # GenServer callbacks
  # ---------------------------------------------------------------------------

  @impl true
  def init(opts) do
    name        = Keyword.fetch!(opts, :name)
    model_id    = Keyword.fetch!(opts, :model_id)
    project_id  = Keyword.fetch!(opts, :project_id)
    project_key = Keyword.fetch!(opts, :project_key)
    client_id   = Keyword.get(opts, :client_id, nil)

    case Nif.session_new(name, model_id, project_id, project_key, client_id) do
      {:ok, ref}       -> {:ok, %{ref: ref, model_id: model_id}}
      {:error, reason} -> {:stop, reason}
    end
  end

  @impl true
  def handle_call(:doc_count, _from, state) do
    {:reply, Nif.session_doc_count(state.ref), state}
  end

  def handle_call(:name, _from, state) do
    {:reply, Nif.session_name(state.ref), state}
  end

  def handle_call({:add_docs, docs, upsert}, _from, %{model_id: "custom"} = state) do
    reply =
      case extract_embeddings(docs) do
        {:ok, embeddings} -> Nif.session_add_docs(state.ref, docs, embeddings, upsert)
        {:error, _} = err -> err
      end

    {:reply, reply, state}
  end

  def handle_call({:add_docs, docs, upsert}, _from, state) do
    {:reply, Nif.session_add_docs_text(state.ref, docs, upsert), state}
  end

  def handle_call({:delete_docs, doc_ids}, _from, state) do
    {:reply, Nif.session_delete_docs(state.ref, doc_ids), state}
  end

  def handle_call({:get_docs, doc_ids}, _from, state) do
    {:reply, Nif.session_get_docs(state.ref, doc_ids), state}
  end

  def handle_call({:query, _query_text, nil, _top_k, _alpha, _filter}, _from, %{model_id: "custom"} = state) do
    {:reply,
     {:error,
      ~s(model_id: "custom" requires a query embedding. Pass embedding: [...] in query opts.)},
     state}
  end

  def handle_call({:query, query_text, nil, top_k, alpha, filter}, _from, state) do
    {:reply, Nif.session_query_text(state.ref, query_text, top_k, alpha, filter), state}
  end

  def handle_call({:query, query_text, embedding, top_k, alpha, filter}, _from, state) do
    {:reply, Nif.session_query(state.ref, query_text, top_k, embedding, alpha, filter), state}
  end

  def handle_call(:load_model, _from, state) do
    {:reply, Nif.session_load_model(state.ref), state}
  end

  def handle_call({:load_index, index_name}, _from, state) do
    {:reply, Nif.session_load_index(state.ref, index_name), state}
  end

  def handle_call(:push_index, _from, state) do
    {:reply, Nif.session_push_index(state.ref), state}
  end

  # ---------------------------------------------------------------------------
  # Private helpers
  # ---------------------------------------------------------------------------

  defp extract_embeddings(docs) do
    missing = docs |> Enum.filter(&is_nil(&1.embedding)) |> Enum.map(& &1.id)

    if missing == [] do
      {:ok, Enum.map(docs, & &1.embedding)}
    else
      {:error,
       ~s(Documents missing .embedding for model_id: "custom": #{inspect(missing)}. ) <>
         "Set embedding on each %Moss.DocumentInfo{}."}
    end
  end
end
