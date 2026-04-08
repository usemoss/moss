defmodule Moss.Client do
  @moduledoc """
  High-level entry point for the moss Elixir SDK.

  Counterpart to `MossClient` in the Python SDK.

  Example:

      {:ok, client} = Moss.Client.new("project-id", "project-key")

      # Cloud CRUD
      {:ok, result} = Moss.Client.create_index(client, "my-index", docs)
      {:ok, info}   = Moss.Client.get_index(client, "my-index")

      # Load and query a cloud index locally
      {:ok, _}       = Moss.Client.load_index(client, "faq-index")
      {:ok, results} = Moss.Client.query(client, "faq-index", "cancel")

      # Session workflow with built-in embeddings
      {:ok, session} = Moss.Client.session(client, "session-abc")
      {:ok, {2, 0}}  = Moss.Session.add_docs(session, docs)
      {:ok, result}  = Moss.Session.query(session, "billing issue")
      {:ok, _}       = Moss.Session.push_index(session)

      # Custom models still use explicit embeddings
      {:ok, custom_session} = Moss.Client.session(client, "custom-session", model_id: "custom")
      {:ok, {1, 0}} = Moss.Session.add_docs(custom_session, docs)
      {:ok, custom_result} = Moss.Session.query(custom_session, "billing issue", embedding: my_vec)
  """

  @default_model_id "moss-minilm"

  defstruct [:project_id, :project_key, :base_url, :client_id, :manage_ref, :manager_pid]

  @type t :: %__MODULE__{
          project_id: String.t(),
          project_key: String.t(),
          base_url: String.t() | nil,
          client_id: String.t(),
          manage_ref: reference(),
          manager_pid: pid()
        }

  @doc """
  Create a new Moss.Client.

  Options:
    - `:base_url` — override the default cloud API URL (nil uses the Rust-side default)
  """
  @spec new(String.t(), String.t(), keyword()) :: {:ok, t()} | {:error, String.t()}
  def new(project_id, project_key, opts \\ []) do
    base_url = Keyword.get(opts, :base_url, nil)
    client_id = Uniq.UUID.uuid4()

    with {:ok, ref} <- Moss.ManageClient.new(project_id, project_key,
                         base_url: base_url, client_id: client_id),
         {:ok, pid} <- Moss.IndexManager.start_link(
                         project_id: project_id,
                         project_key: project_key,
                         base_url: base_url,
                         client_id: client_id
                       ) do
      {:ok,
       %__MODULE__{
         project_id: project_id,
         project_key: project_key,
         base_url: base_url,
         client_id: client_id,
         manage_ref: ref,
         manager_pid: pid
       }}
    end
  end

  # ---------------------------------------------------------------------------
  # Cloud CRUD (delegates to Moss.ManageClient)
  # ---------------------------------------------------------------------------

  @doc "Create a cloud index with initial documents."
  @spec create_index(t(), String.t(), list(Moss.DocumentInfo.t()), String.t()) ::
          {:ok, Moss.MutationResult.t()} | {:error, String.t()}
  def create_index(%__MODULE__{manage_ref: ref}, name, docs, model_id \\ @default_model_id) do
    Moss.ManageClient.create_index(ref, name, docs, model_id)
  end

  @doc """
  Add documents to an existing cloud index.

  Options:
    - `:upsert` (boolean, default nil — use server default)
  """
  @spec add_docs(t(), String.t(), list(Moss.DocumentInfo.t()), keyword()) ::
          {:ok, Moss.MutationResult.t()} | {:error, String.t()}
  def add_docs(%__MODULE__{manage_ref: ref}, name, docs, opts \\ []) do
    Moss.ManageClient.add_docs(ref, name, docs, opts)
  end

  @doc "Delete documents by IDs from a cloud index."
  @spec delete_docs(t(), String.t(), list(String.t())) ::
          {:ok, Moss.MutationResult.t()} | {:error, String.t()}
  def delete_docs(%__MODULE__{manage_ref: ref}, name, doc_ids) do
    Moss.ManageClient.delete_docs(ref, name, doc_ids)
  end

  @doc "Poll the status of an async job."
  @spec get_job_status(t(), String.t()) ::
          {:ok, Moss.JobStatusResponse.t()} | {:error, String.t()}
  def get_job_status(%__MODULE__{manage_ref: ref}, job_id) do
    Moss.ManageClient.get_job_status(ref, job_id)
  end

  @doc "Get metadata for a cloud index."
  @spec get_index(t(), String.t()) ::
          {:ok, Moss.IndexInfo.t()} | {:error, String.t()}
  def get_index(%__MODULE__{manage_ref: ref}, name) do
    Moss.ManageClient.get_index(ref, name)
  end

  @doc "List all cloud indexes for this project."
  @spec list_indexes(t()) ::
          {:ok, list(Moss.IndexInfo.t())} | {:error, String.t()}
  def list_indexes(%__MODULE__{manage_ref: ref}) do
    Moss.ManageClient.list_indexes(ref)
  end

  @doc "Delete a cloud index."
  @spec delete_index(t(), String.t()) ::
          {:ok, boolean()} | {:error, String.t()}
  def delete_index(%__MODULE__{manage_ref: ref}, name) do
    Moss.ManageClient.delete_index(ref, name)
  end

  @doc """
  Get documents from a cloud index.

  Options:
    - `:doc_ids` (list of strings) — if provided, only fetch those docs
  """
  @spec get_docs(t(), String.t(), keyword()) ::
          {:ok, list(Moss.DocumentInfo.t())} | {:error, String.t()}
  def get_docs(%__MODULE__{manage_ref: ref}, name, opts \\ []) do
    Moss.ManageClient.get_docs(ref, name, opts)
  end

  # ---------------------------------------------------------------------------
  # Local index ops (delegates to Moss.IndexManager)
  # ---------------------------------------------------------------------------

  @doc """
  Load a cloud index into memory.

  Options:
    - `:auto_refresh` (boolean, default false)
    - `:polling_interval` (integer seconds, default 600)

  Returns `{:ok, Moss.IndexInfo.t()}` or `{:error, reason}`.
  """
  @spec load_index(t(), String.t(), keyword()) ::
          {:ok, Moss.IndexInfo.t()} | {:error, String.t()}
  def load_index(%__MODULE__{manager_pid: pid}, name, opts \\ []) do
    Moss.IndexManager.load_index(pid, name, opts)
  end

  @doc "Unload an index from memory."
  @spec unload_index(t(), String.t()) :: {:ok, :ok} | {:error, String.t()}
  def unload_index(%__MODULE__{manager_pid: pid}, name) do
    Moss.IndexManager.unload_index(pid, name)
  end

  @doc "Check if an index is loaded."
  @spec has_index(t(), String.t()) :: boolean()
  def has_index(%__MODULE__{manager_pid: pid}, name) do
    Moss.IndexManager.has_index(pid, name)
  end

  @doc """
  Query a locally loaded index.

  For built-in models, the query is embedded automatically. For indexes created
  with `model_id: "custom"`, pass the query embedding via `embedding: [...]`.

  Options:
    - `:top_k` (integer, default 5)
    - `:alpha` (float, default 0.8)
    - `:filter` (map)
    - `:embedding` (list of floats, required for `model_id: "custom"`)

  Returns `{:ok, Moss.SearchResult.t()}` or `{:error, reason}`.
  """
  @spec query(t(), String.t(), String.t(), keyword()) ::
          {:ok, Moss.SearchResult.t()} | {:error, String.t()}
  def query(%__MODULE__{manager_pid: pid}, name, query_text, opts \\ []) do
    Moss.IndexManager.query(pid, name, query_text, opts)
  end

  @doc "Force an immediate refresh of a loaded index from the cloud."
  @spec refresh_index(t(), String.t()) ::
          {:ok, Moss.RefreshResult.t()} | {:error, String.t()}
  def refresh_index(%__MODULE__{manager_pid: pid}, name) do
    Moss.IndexManager.refresh_index(pid, name)
  end

  @doc "Get metadata for a loaded index."
  @spec get_index_info(t(), String.t()) ::
          {:ok, Moss.IndexInfo.t()} | {:error, String.t()}
  def get_index_info(%__MODULE__{manager_pid: pid}, name) do
    Moss.IndexManager.get_index_info(pid, name)
  end

  # ---------------------------------------------------------------------------
  # Session
  # ---------------------------------------------------------------------------

  @doc """
  Create or resume a local session index.

  If a cloud index with `index_name` already exists, it is silently loaded
  into the session. If not, the session starts empty.

  Options:
    - `:model_id` (String.t(), default "moss-minilm")
    - `:server_name` — GenServer name for the Session process

  Returns `{:ok, pid}` on success.
  """
  @spec session(t(), String.t(), keyword()) ::
          {:ok, GenServer.server()} | {:error, String.t()}
  def session(%__MODULE__{} = client, index_name, opts \\ []) do
    model_id = Keyword.get(opts, :model_id, @default_model_id)

    with {:ok, pid} <-
           Moss.Session.start_link(
             Keyword.merge(opts,
               name: index_name,
               model_id: model_id,
               project_id: client.project_id,
               project_key: client.project_key,
               client_id: client.client_id
             )
           ) do
      # Silently attempt to load from cloud — ignore errors (index may not exist yet).
      case Moss.Session.load_index(pid, index_name) do
        {:ok, _doc_count} -> :ok
        {:error, reason} ->
          require Logger
          Logger.warning("Could not load existing index '#{index_name}' — starting fresh. Reason: #{reason}")
      end

      case maybe_warm_session_model(pid, model_id) do
        :ok ->
          {:ok, pid}

        {:error, reason} ->
          if Process.alive?(pid), do: GenServer.stop(pid)
          {:error, reason}
      end
    end
  end

  # ---------------------------------------------------------------------------
  # Private helpers
  # ---------------------------------------------------------------------------

  defp maybe_warm_session_model(pid, model_id) do
    if model_id in ["moss-minilm", "moss-mediumlm"] do
      case Moss.Session.load_model(pid) do
        {:ok, :ok} -> :ok
        {:error, reason} -> {:error, reason}
      end
    else
      :ok
    end
  end
end
