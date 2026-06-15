package mosscore

type DocumentInfo struct {
	ID        string
	Text      string
	Metadata  map[string]string
	Embedding []float32
}

type MutationOptions struct {
	Upsert *bool
}

type MutationResult struct {
	JobID     string
	IndexName string
	DocCount  int
}

type ModelRef struct {
	ID      string
	Version *string
}

type IndexInfo struct {
	ID        string
	Name      string
	Version   *string
	Status    string
	DocCount  int
	CreatedAt *string
	UpdatedAt *string
	Model     ModelRef
}

type JobStatusResponse struct {
	JobID        string
	Status       string
	Progress     float64
	CurrentPhase *string
	Error        *string
	CreatedAt    string
	UpdatedAt    string
	CompletedAt  *string
}

type LoadIndexOptions struct {
	AutoRefresh              bool
	PollingIntervalInSeconds uint64
}

type QueryResultDocumentInfo struct {
	ID       string
	Text     string
	Metadata map[string]string
	Score    float64
}

type SearchResult struct {
	Docs        []QueryResultDocumentInfo
	Query       string
	IndexName   *string
	TimeTakenMs int
}

type RefreshResult struct {
	IndexName         string
	PreviousUpdatedAt string
	NewUpdatedAt      string
	WasUpdated        bool
}
