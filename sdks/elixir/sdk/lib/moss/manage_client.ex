defmodule Moss.ManageClient do
  @moduledoc false

  alias MossCore.Nif

  @doc """
  Create a new ManageClient reference.

  Options:
    - `:base_url` — override default cloud API URL
  """
  @spec new(String.t(), String.t(), keyword()) ::
          {:ok, reference()} | {:error, String.t()}
  def new(project_id, project_key, opts \\ []) do
    base_url = Keyword.get(opts, :base_url, nil)
    client_id = Keyword.get(opts, :client_id, nil)
    Nif.manage_new(project_id, project_key, base_url, client_id)
  end

  @doc "Create a cloud index with initial documents."
  @spec create_index(reference(), String.t(), list(Moss.DocumentInfo.t()), String.t()) ::
          {:ok, Moss.MutationResult.t()} | {:error, String.t()}
  def create_index(ref, name, docs, model_id) do
    Nif.manage_create_index(ref, name, docs, model_id)
  end

  @doc """
  Add documents to an existing cloud index.

  Options:
    - `:upsert` (boolean, default nil — use server default)
  """
  @spec add_docs(reference(), String.t(), list(Moss.DocumentInfo.t()), keyword()) ::
          {:ok, Moss.MutationResult.t()} | {:error, String.t()}
  def add_docs(ref, name, docs, opts \\ []) do
    upsert = Keyword.get(opts, :upsert, nil)
    Nif.manage_add_docs(ref, name, docs, upsert)
  end

  @doc "Delete documents by IDs from a cloud index."
  @spec delete_docs(reference(), String.t(), list(String.t())) ::
          {:ok, Moss.MutationResult.t()} | {:error, String.t()}
  def delete_docs(ref, name, doc_ids) do
    Nif.manage_delete_docs(ref, name, doc_ids)
  end

  @doc "Poll the status of an async job."
  @spec get_job_status(reference(), String.t()) ::
          {:ok, Moss.JobStatusResponse.t()} | {:error, String.t()}
  def get_job_status(ref, job_id) do
    Nif.manage_get_job_status(ref, job_id)
  end

  @doc "Get metadata for a cloud index."
  @spec get_index(reference(), String.t()) ::
          {:ok, Moss.IndexInfo.t()} | {:error, String.t()}
  def get_index(ref, name) do
    Nif.manage_get_index(ref, name)
  end

  @doc "List all cloud indexes for this project."
  @spec list_indexes(reference()) ::
          {:ok, list(Moss.IndexInfo.t())} | {:error, String.t()}
  def list_indexes(ref) do
    Nif.manage_list_indexes(ref)
  end

  @doc "Delete a cloud index."
  @spec delete_index(reference(), String.t()) ::
          {:ok, boolean()} | {:error, String.t()}
  def delete_index(ref, name) do
    Nif.manage_delete_index(ref, name)
  end

  @doc """
  Get documents from a cloud index.

  Options:
    - `:doc_ids` (list of strings) — if provided, only fetch those docs
  """
  @spec get_docs(reference(), String.t(), keyword()) ::
          {:ok, list(Moss.DocumentInfo.t())} | {:error, String.t()}
  def get_docs(ref, name, opts \\ []) do
    doc_ids = Keyword.get(opts, :doc_ids, nil)
    Nif.manage_get_docs(ref, name, doc_ids)
  end

  @doc "Validate project credentials."
  @spec validate_credentials(reference()) ::
          {:ok, Moss.CredentialsInfo.t()} | {:error, String.t()}
  def validate_credentials(ref) do
    Nif.manage_validate_credentials(ref)
  end
end
