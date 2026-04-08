defmodule Moss.ModelRef do
  @moduledoc "Model reference (id + version)."
  defstruct [:id, :version]
end

defmodule Moss.DocumentInfo do
  @moduledoc "A document with id, text, optional metadata, and optional embedding."
  defstruct [:id, :text, metadata: nil, embedding: nil]
end

defmodule Moss.QueryResultDoc do
  @moduledoc "A query result document with a relevance score."
  defstruct [:id, :text, :score, metadata: nil]
end

defmodule Moss.SearchResult do
  @moduledoc "The result of a search/query operation."
  defstruct [:docs, :query, :index_name, :time_taken_ms]
end

defmodule Moss.IndexInfo do
  @moduledoc "Metadata about a cloud or local index."
  defstruct [:id, :name, :version, :status, :doc_count, :created_at, :updated_at, :model]
end

defmodule Moss.PushIndexResult do
  @moduledoc "Result of a push_index operation."
  defstruct [:job_id, :index_name, :doc_count, :status]
end

defmodule Moss.RefreshResult do
  @moduledoc "Result of a refresh_index operation."
  defstruct [:index_name, :previous_updated_at, :new_updated_at, :was_updated]
end

defmodule Moss.SerializedIndex do
  @moduledoc false
  defstruct [:name, :version, :model, :dimension, :embeddings, :doc_ids]
end

defmodule Moss.MutationResult do
  @moduledoc "Result of a cloud mutation (create, add_docs, delete_docs)."
  defstruct [:job_id, :index_name, :doc_count]
end

defmodule Moss.JobStatusResponse do
  @moduledoc "Full job status response from the cloud."
  defstruct [
    :job_id,
    :status,
    :progress,
    :current_phase,
    :error,
    :created_at,
    :updated_at,
    :completed_at
  ]
end

defmodule Moss.CredentialsInfo do
  @moduledoc false
  defstruct [:project_name, :project_id]
end
