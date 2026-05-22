package moss

// MossModel identifies the embedding model backing an index.
type MossModel string

const (
	ModelMossMiniLM   MossModel = "moss-minilm"
	ModelMossMediumLM MossModel = "moss-mediumlm"
	ModelCustom       MossModel = "custom"
)

// IndexStatus describes the current lifecycle state of an index.
type IndexStatus string

const (
	IndexStatusNotStarted IndexStatus = "NotStarted"
	IndexStatusBuilding   IndexStatus = "Building"
	IndexStatusReady      IndexStatus = "Ready"
	IndexStatusFailed     IndexStatus = "Failed"
)

// JobStatus describes the current lifecycle state of a mutation job.
type JobStatus string

const (
	JobStatusPendingUpload JobStatus = "pending_upload"
	JobStatusUploading     JobStatus = "uploading"
	JobStatusBuilding      JobStatus = "building"
	JobStatusCompleted     JobStatus = "completed"
	JobStatusFailed        JobStatus = "failed"
)

// JobPhase describes the current phase of a mutation job.
type JobPhase string

const (
	JobPhaseDownloading          JobPhase = "downloading"
	JobPhaseDeserializing        JobPhase = "deserializing"
	JobPhaseGeneratingEmbeddings JobPhase = "generating_embeddings"
	JobPhaseBuildingIndex        JobPhase = "building_index"
	JobPhaseUploading            JobPhase = "uploading"
	JobPhaseCleanup              JobPhase = "cleanup"
)

// ModelRef points at the model used by an index.
type ModelRef struct {
	ID      string  `json:"id"`
	Version *string `json:"version,omitempty"`
}

// IndexInfo describes persisted index metadata.
type IndexInfo struct {
	ID        string      `json:"id"`
	Name      string      `json:"name"`
	Version   *string     `json:"version,omitempty"`
	Status    IndexStatus `json:"status"`
	DocCount  int         `json:"docCount"`
	CreatedAt *string     `json:"createdAt,omitempty"`
	UpdatedAt *string     `json:"updatedAt,omitempty"`
	Model     ModelRef    `json:"model"`
}

// DocumentInfo is the canonical index document representation.
type DocumentInfo struct {
	ID        string            `json:"id"`
	Text      string            `json:"text"`
	Metadata  map[string]string `json:"metadata,omitempty"`
	Embedding []float32         `json:"embedding,omitempty"`
}

// QueryResultDocumentInfo is a document returned from a query with a score.
type QueryResultDocumentInfo struct {
	ID       string            `json:"id"`
	Text     string            `json:"text"`
	Metadata map[string]string `json:"metadata,omitempty"`
	Score    float64           `json:"score"`
}

// SearchResult is the response returned by query operations.
type SearchResult struct {
	Docs        []QueryResultDocumentInfo `json:"docs"`
	Query       string                    `json:"query"`
	IndexName   *string                   `json:"indexName,omitempty"`
	TimeTakenMs *int                      `json:"timeTakenMs,omitempty"`
}

// QueryOptions customizes cloud query behavior.
type QueryOptions struct {
	Embedding []float32      `json:"embedding,omitempty"`
	TopK      int            `json:"topK,omitempty"`
	Alpha     *float64       `json:"alpha,omitempty"`
	Filter    map[string]any `json:"filter,omitempty"`
}

// GetDocumentsOptions optionally narrows document retrieval by ID.
type GetDocumentsOptions struct {
	DocIDs []string `json:"docIds,omitempty"`
}

// CreateIndexOptions customizes index creation behavior.
type CreateIndexOptions struct {
	ModelID MossModel `json:"modelId,omitempty"`
}

// MutationOptions customizes add/update/delete document behavior.
type MutationOptions struct {
	Upsert *bool `json:"upsert,omitempty"`
}

// MutationResult is returned when a mutation job completes.
type MutationResult struct {
	JobID     string `json:"jobId"`
	IndexName string `json:"indexName"`
	DocCount  int    `json:"docCount"`
}

// JobProgress is emitted while a mutation job is running.
type JobProgress struct {
	JobID        string    `json:"jobId"`
	Status       JobStatus `json:"status"`
	Progress     float64   `json:"progress"`
	CurrentPhase *JobPhase `json:"currentPhase,omitempty"`
}

// JobStatusResponse is the persisted status view for a mutation job.
type JobStatusResponse struct {
	JobID        string    `json:"jobId"`
	Status       JobStatus `json:"status"`
	Progress     float64   `json:"progress"`
	CurrentPhase *JobPhase `json:"currentPhase,omitempty"`
	Error        *string   `json:"error,omitempty"`
	CreatedAt    string    `json:"createdAt"`
	UpdatedAt    string    `json:"updatedAt"`
	CompletedAt  *string   `json:"completedAt,omitempty"`
}
