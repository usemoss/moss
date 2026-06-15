package moss

import (
	"context"
	"fmt"
	"strings"
	"time"

	mosscore "github.com/usemoss/moss/sdks/go/bindings"
)

const (
	defaultPollInterval      = 2 * time.Second
	defaultMutationTimeout   = 30 * time.Minute
	maxConsecutivePollErrors = 3
)

// CreateIndex creates a new index through the native bindings and polls until completion.
func (c *Client) CreateIndex(ctx context.Context, indexName string, docs []DocumentInfo, options *CreateIndexOptions) (MutationResult, error) {
	if err := ctx.Err(); err != nil {
		return MutationResult{}, err
	}
	if err := c.validateManageRequest(indexName); err != nil {
		return MutationResult{}, err
	}
	if len(docs) == 0 {
		return MutationResult{}, ErrEmptyDocuments
	}

	modelID := resolveModelID(docs, options)
	if _, err := resolveEmbeddingDimension(docs, modelID); err != nil {
		return MutationResult{}, err
	}

	manage, err := c.ensureManageClient()
	if err != nil {
		return MutationResult{}, err
	}

	response, err := manage.CreateIndex(indexName, toCoreDocumentInfos(docs), string(modelID))
	if err != nil {
		return MutationResult{}, err
	}

	var onProgress func(JobProgress)
	if options != nil {
		onProgress = options.OnProgress
	}

	return c.pollJobUntilComplete(ctx, response, onProgress)
}

// AddDocs appends or upserts documents and polls the async job until completion.
func (c *Client) AddDocs(ctx context.Context, indexName string, docs []DocumentInfo, options *MutationOptions) (MutationResult, error) {
	if err := ctx.Err(); err != nil {
		return MutationResult{}, err
	}
	if err := c.validateManageRequest(indexName); err != nil {
		return MutationResult{}, err
	}
	if len(docs) == 0 {
		return MutationResult{}, ErrEmptyDocuments
	}

	var bindingOptions *mosscore.MutationOptions
	var onProgress func(JobProgress)
	if options != nil {
		bindingOptions = &mosscore.MutationOptions{Upsert: options.Upsert}
		onProgress = options.OnProgress
	}

	manage, err := c.ensureManageClient()
	if err != nil {
		return MutationResult{}, err
	}

	response, err := manage.AddDocs(indexName, toCoreDocumentInfos(docs), bindingOptions)
	if err != nil {
		return MutationResult{}, err
	}

	return c.pollJobUntilComplete(ctx, response, onProgress)
}

// DeleteDocs removes documents by ID and polls the async job until completion.
func (c *Client) DeleteDocs(ctx context.Context, indexName string, docIDs []string, options *MutationOptions) (MutationResult, error) {
	if err := ctx.Err(); err != nil {
		return MutationResult{}, err
	}
	if err := c.validateManageRequest(indexName); err != nil {
		return MutationResult{}, err
	}
	if len(docIDs) == 0 {
		return MutationResult{}, ErrEmptyDocumentIDs
	}

	var onProgress func(JobProgress)
	if options != nil {
		onProgress = options.OnProgress
	}

	manage, err := c.ensureManageClient()
	if err != nil {
		return MutationResult{}, err
	}

	response, err := manage.DeleteDocs(indexName, docIDs)
	if err != nil {
		return MutationResult{}, err
	}

	return c.pollJobUntilComplete(ctx, response, onProgress)
}

// GetJobStatus fetches the current status of an async mutation job.
func (c *Client) GetJobStatus(ctx context.Context, jobID string) (JobStatusResponse, error) {
	if err := ctx.Err(); err != nil {
		return JobStatusResponse{}, err
	}
	if err := validateCredentials(c.projectID, c.projectKey); err != nil {
		return JobStatusResponse{}, err
	}
	if strings.TrimSpace(jobID) == "" {
		return JobStatusResponse{}, ErrEmptyJobID
	}

	manage, err := c.ensureManageClient()
	if err != nil {
		return JobStatusResponse{}, err
	}

	response, err := manage.GetJobStatus(jobID)
	if err != nil {
		return JobStatusResponse{}, err
	}
	return fromCoreJobStatusResponse(response), nil
}

func resolveModelID(docs []DocumentInfo, options *CreateIndexOptions) MossModel {
	if options != nil && options.ModelID != "" {
		return options.ModelID
	}

	for _, doc := range docs {
		if len(doc.Embedding) > 0 {
			return ModelCustom
		}
	}

	return ModelMossMiniLM
}

func resolveEmbeddingDimension(docs []DocumentInfo, modelID MossModel) (int, error) {
	withEmbeddings := 0
	for _, doc := range docs {
		if len(doc.Embedding) > 0 {
			withEmbeddings++
		}
	}

	withoutEmbeddings := len(docs) - withEmbeddings
	if withEmbeddings > 0 && withoutEmbeddings > 0 {
		return 0, fmt.Errorf("moss: all documents must either all have embeddings or none should have embeddings")
	}

	if withEmbeddings == 0 {
		if modelID == ModelCustom {
			return 0, fmt.Errorf("moss: cannot use model %q without pre-computed embeddings", ModelCustom)
		}
		return 0, nil
	}

	dimension := len(docs[0].Embedding)
	for _, doc := range docs[1:] {
		if len(doc.Embedding) != dimension {
			return 0, fmt.Errorf("moss: document %q has mismatched embedding dimension (expected %d, got %d)", doc.ID, dimension, len(doc.Embedding))
		}
	}

	return dimension, nil
}

func (c *Client) pollJobUntilComplete(
	ctx context.Context,
	result mosscore.MutationResult,
	onProgress func(JobProgress),
) (MutationResult, error) {
	timeoutCtx, cancel := context.WithTimeout(ctx, defaultMutationTimeout)
	defer cancel()

	ticker := time.NewTicker(defaultPollInterval)
	defer ticker.Stop()

	consecutiveErrors := 0
	completed := fromCoreMutationResult(result)

	for {
		status, err := c.GetJobStatus(timeoutCtx, result.JobID)
		if err != nil {
			consecutiveErrors++
			if consecutiveErrors >= maxConsecutivePollErrors {
				return MutationResult{}, fmt.Errorf("moss: job status polling failed after %d consecutive errors: %w", maxConsecutivePollErrors, err)
			}
		} else {
			consecutiveErrors = 0
			if onProgress != nil {
				onProgress(JobProgress{
					JobID:        status.JobID,
					Status:       status.Status,
					Progress:     status.Progress,
					CurrentPhase: status.CurrentPhase,
				})
			}

			switch status.Status {
			case JobStatusCompleted:
				return completed, nil
			case JobStatusFailed:
				if status.Error != nil && *status.Error != "" {
					return MutationResult{}, fmt.Errorf("moss: job failed: %s", *status.Error)
				}
				return MutationResult{}, fmt.Errorf("moss: job failed")
			}
		}

		select {
		case <-timeoutCtx.Done():
			return MutationResult{}, timeoutCtx.Err()
		case <-ticker.C:
		}
	}
}
