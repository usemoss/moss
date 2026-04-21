defmodule MossCore.Nif do
  @moduledoc """
  Rustler NIF declarations for the moss library.

  All functions raise `:not_loaded` if the NIF is not compiled.
  Functions that can fail return `{:ok, result}` or `{:error, reason}`.
  """

  @version Mix.Project.config()[:version]

  use RustlerPrecompiled,
    otp_app: :moss_core,
    crate: :moss_core,
    base_url:
      "https://github.com/usemoss/moss-core-nif/releases/download/elixir-nif-v#{@version}",
    version: @version,
    targets: ~w[
      x86_64-unknown-linux-gnu
      aarch64-unknown-linux-gnu
      aarch64-apple-darwin
      x86_64-pc-windows-msvc
    ],
    nif_versions: ["2.16"],
    force_build: System.get_env("MOSS_NIF_BUILD") in ["1", "true"]

  # ---------------------------------------------------------------------------
  # SessionIndex NIFs
  # ---------------------------------------------------------------------------

  @doc "Create a new SessionIndex resource."
  def session_new(_name, _model_id, _project_id, _project_key, _client_id),
    do: :erlang.nif_error(:not_loaded)

  @doc "Get the document count of a SessionIndex."
  def session_doc_count(_ref), do: :erlang.nif_error(:not_loaded)

  @doc "Get the name of a SessionIndex."
  def session_name(_ref), do: :erlang.nif_error(:not_loaded)

  @doc "Add documents to a SessionIndex. Returns `{:ok, {added, updated}}` or `{:error, reason}`."
  def session_add_docs(_ref, _docs, _embeddings, _upsert),
    do: :erlang.nif_error(:not_loaded)

  @doc "Add documents to a SessionIndex using built-in embeddings from document text."
  def session_add_docs_text(_ref, _docs, _upsert), do: :erlang.nif_error(:not_loaded)

  @doc "Delete documents from a SessionIndex by IDs. Returns count deleted."
  def session_delete_docs(_ref, _doc_ids), do: :erlang.nif_error(:not_loaded)

  @doc "Get documents from a SessionIndex. `doc_ids` may be nil for all docs."
  def session_get_docs(_ref, _doc_ids), do: :erlang.nif_error(:not_loaded)

  @doc "Query a SessionIndex. Returns `{:ok, SearchResult}` or `{:error, reason}`."
  def session_query(_ref, _query, _top_k, _embedding, _alpha, _filter),
    do: :erlang.nif_error(:not_loaded)

  @doc "Query a SessionIndex using built-in embeddings from the query text."
  def session_query_text(_ref, _query, _top_k, _alpha, _filter),
    do: :erlang.nif_error(:not_loaded)

  @doc "Preload the built-in embedding model for a SessionIndex."
  def session_load_model(_ref), do: :erlang.nif_error(:not_loaded)

  @doc "Load an existing cloud index into the session. Returns `{:ok, doc_count}` or `{:error, reason}`."
  def session_load_index(_ref, _index_name), do: :erlang.nif_error(:not_loaded)

  @doc "Push the session index to the cloud. Returns `{:ok, PushIndexResult}` or `{:error, reason}`."
  def session_push_index(_ref), do: :erlang.nif_error(:not_loaded)

  # ---------------------------------------------------------------------------
  # IndexManager NIFs
  # ---------------------------------------------------------------------------

  @doc "Create a new IndexManager resource. Returns `{:ok, ref}` or `{:error, reason}`."
  def manager_new(_project_id, _project_key, _base_url, _client_id),
    do: :erlang.nif_error(:not_loaded)

  @doc "Load an index from cloud. Returns `{:ok, IndexInfo}` or `{:error, reason}`."
  def manager_load_index(_ref, _index_name, _auto_refresh, _polling_interval),
    do: :erlang.nif_error(:not_loaded)

  @doc "Unload an index. Returns `{:ok, :ok}` or `{:error, reason}`."
  def manager_unload_index(_ref, _index_name), do: :erlang.nif_error(:not_loaded)

  @doc "Check if an index is loaded. Returns boolean."
  def manager_has_index(_ref, _index_name), do: :erlang.nif_error(:not_loaded)

  @doc "Query a loaded index. Returns `{:ok, SearchResult}` or `{:error, reason}`."
  def manager_query(_ref, _index_name, _query, _embedding, _top_k, _alpha, _filter),
    do: :erlang.nif_error(:not_loaded)

  @doc "Query a loaded index using built-in embeddings from the query text."
  def manager_query_text(_ref, _index_name, _query, _top_k, _alpha, _filter),
    do: :erlang.nif_error(:not_loaded)

  @doc "Preload the built-in embedding model for a loaded index."
  def manager_load_query_model(_ref, _index_name), do: :erlang.nif_error(:not_loaded)

  @doc "Force refresh an index from cloud. Returns `{:ok, RefreshResult}` or `{:error, reason}`."
  def manager_refresh_index(_ref, _index_name), do: :erlang.nif_error(:not_loaded)

  @doc "Get index metadata. Returns `{:ok, IndexInfo}` or `{:error, reason}`."
  def manager_get_index_info(_ref, _index_name), do: :erlang.nif_error(:not_loaded)

  # ---------------------------------------------------------------------------
  # ManageClient NIFs
  # ---------------------------------------------------------------------------

  @doc "Create a new ManageClient resource. Returns `{:ok, ref}` or `{:error, reason}`."
  def manage_new(_project_id, _project_key, _base_url, _client_id),
    do: :erlang.nif_error(:not_loaded)

  @doc "Create an index in the cloud. Returns `{:ok, MutationResult}` or `{:error, reason}`."
  def manage_create_index(_ref, _name, _docs, _model_id),
    do: :erlang.nif_error(:not_loaded)

  @doc "Add docs to a cloud index. Returns `{:ok, MutationResult}` or `{:error, reason}`."
  def manage_add_docs(_ref, _name, _docs, _upsert),
    do: :erlang.nif_error(:not_loaded)

  @doc "Delete docs from a cloud index. Returns `{:ok, MutationResult}` or `{:error, reason}`."
  def manage_delete_docs(_ref, _name, _doc_ids),
    do: :erlang.nif_error(:not_loaded)

  @doc "Get job status. Returns `{:ok, JobStatusResponse}` or `{:error, reason}`."
  def manage_get_job_status(_ref, _job_id), do: :erlang.nif_error(:not_loaded)

  @doc "Get a cloud index's metadata. Returns `{:ok, IndexInfo}` or `{:error, reason}`."
  def manage_get_index(_ref, _name), do: :erlang.nif_error(:not_loaded)

  @doc "List all cloud indexes. Returns `{:ok, [IndexInfo]}` or `{:error, reason}`."
  def manage_list_indexes(_ref), do: :erlang.nif_error(:not_loaded)

  @doc "Delete a cloud index. Returns `{:ok, bool}` or `{:error, reason}`."
  def manage_delete_index(_ref, _name), do: :erlang.nif_error(:not_loaded)

  @doc "Get docs from a cloud index. Returns `{:ok, [DocumentInfo]}` or `{:error, reason}`."
  def manage_get_docs(_ref, _name, _doc_ids), do: :erlang.nif_error(:not_loaded)

  @doc "Validate project credentials. Returns `{:ok, CredentialsInfo}` or `{:error, reason}`."
  def manage_validate_credentials(_ref), do: :erlang.nif_error(:not_loaded)
end
