package moss

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"strings"
	"time"
)

const (
	defaultPollInterval      = 2 * time.Second
	defaultMutationTimeout   = 30 * time.Minute
	maxConsecutivePollErrors = 3
	maxUploadRetries         = 3
	baseUploadRetryDelay     = 1 * time.Second
)

// CreateIndex initializes an upload, sends the bulk payload, starts the build, and polls until completion.
func (c *Client) CreateIndex(ctx context.Context, indexName string, docs []DocumentInfo, options *CreateIndexOptions) (MutationResult, error) {
	if err := c.validateManageRequest(indexName); err != nil {
		return MutationResult{}, err
	}
	if len(docs) == 0 {
		return MutationResult{}, ErrEmptyDocuments
	}

	modelID := resolveModelID(docs, options)
	dimension, err := resolveEmbeddingDimension(docs, modelID)
	if err != nil {
		return MutationResult{}, err
	}

	initResponse, err := c.manageAPI.InitUpload(ctx, c.manageURL, c.projectID, c.projectKey, indexName, string(modelID), len(docs), dimension)
	if err != nil {
		return MutationResult{}, normalizeError(err)
	}

	payload, err := serializeBulkPayload(docs, dimension)
	if err != nil {
		return MutationResult{}, err
	}

	if err := c.uploadBulkPayload(ctx, initResponse.UploadURL, payload); err != nil {
		return MutationResult{}, err
	}

	if _, err := c.manageAPI.StartBuild(ctx, c.manageURL, c.projectID, c.projectKey, initResponse.JobID); err != nil {
		return MutationResult{}, normalizeError(err)
	}

	var onProgress func(JobProgress)
	if options != nil {
		onProgress = options.OnProgress
	}

	return c.pollJobUntilComplete(ctx, initResponse.JobID, indexName, len(docs), onProgress)
}

// AddDocs appends or upserts documents and polls the async job until completion.
func (c *Client) AddDocs(ctx context.Context, indexName string, docs []DocumentInfo, options *MutationOptions) (MutationResult, error) {
	if err := c.validateManageRequest(indexName); err != nil {
		return MutationResult{}, err
	}
	if len(docs) == 0 {
		return MutationResult{}, ErrEmptyDocuments
	}

	var upsert *bool
	var onProgress func(JobProgress)
	if options != nil {
		upsert = options.Upsert
		onProgress = options.OnProgress
	}

	response, err := c.manageAPI.AddDocs(ctx, c.manageURL, c.projectID, c.projectKey, indexName, toDocumentInfoResponses(docs), upsert)
	if err != nil {
		return MutationResult{}, normalizeError(err)
	}

	return c.pollJobUntilComplete(ctx, response.JobID, indexName, len(docs), onProgress)
}

// DeleteDocs removes documents by ID and polls the async job until completion.
func (c *Client) DeleteDocs(ctx context.Context, indexName string, docIDs []string, options *MutationOptions) (MutationResult, error) {
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

	response, err := c.manageAPI.DeleteDocs(ctx, c.manageURL, c.projectID, c.projectKey, indexName, docIDs)
	if err != nil {
		return MutationResult{}, normalizeError(err)
	}

	return c.pollJobUntilComplete(ctx, response.JobID, indexName, len(docIDs), onProgress)
}

// GetJobStatus fetches the current status of an async mutation job.
func (c *Client) GetJobStatus(ctx context.Context, jobID string) (JobStatusResponse, error) {
	if err := validateCredentials(c.projectID, c.projectKey); err != nil {
		return JobStatusResponse{}, err
	}
	if strings.TrimSpace(c.manageURL) == "" {
		return JobStatusResponse{}, ErrMissingManageURL
	}
	if strings.TrimSpace(jobID) == "" {
		return JobStatusResponse{}, ErrEmptyJobID
	}

	response, err := c.manageAPI.GetJobStatus(ctx, c.manageURL, c.projectID, c.projectKey, jobID)
	if err != nil {
		return JobStatusResponse{}, normalizeError(err)
	}
	return toJobStatusResponse(response), nil
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

func serializeBulkPayload(docs []DocumentInfo, dimension int) ([]byte, error) {
	metadataDocs := make([]map[string]any, 0, len(docs))
	for _, doc := range docs {
		item := map[string]any{
			"id":   doc.ID,
			"text": doc.Text,
		}
		if len(doc.Metadata) > 0 {
			item["metadata"] = doc.Metadata
		}
		metadataDocs = append(metadataDocs, item)
	}

	metadataBytes, err := json.Marshal(metadataDocs)
	if err != nil {
		return nil, err
	}

	const headerSize = 20
	embeddingsSize := 0
	if dimension > 0 {
		embeddingsSize = len(docs) * dimension * 4
	}

	buf := bytes.NewBuffer(make([]byte, 0, headerSize+len(metadataBytes)+embeddingsSize))
	buf.Write([]byte{'M', 'O', 'S', 'S'})
	for _, value := range []uint32{1, uint32(len(docs)), uint32(dimension), uint32(len(metadataBytes))} {
		if err := binary.Write(buf, binary.LittleEndian, value); err != nil {
			return nil, err
		}
	}
	buf.Write(metadataBytes)

	for _, doc := range docs {
		for _, value := range doc.Embedding {
			if err := binary.Write(buf, binary.LittleEndian, value); err != nil {
				return nil, err
			}
		}
	}

	return buf.Bytes(), nil
}

func (c *Client) uploadBulkPayload(ctx context.Context, uploadURL string, payload []byte) error {
	var lastErr error

	for attempt := 0; attempt < maxUploadRetries; attempt++ {
		req, err := http.NewRequestWithContext(ctx, http.MethodPut, uploadURL, bytes.NewReader(payload))
		if err != nil {
			return err
		}
		req.Header.Set("Content-Type", "application/octet-stream")

		resp, err := c.httpClient.Do(req)
		if err != nil {
			lastErr = err
		} else {
			body, _ := io.ReadAll(io.LimitReader(resp.Body, 16*1024))
			resp.Body.Close()

			if resp.StatusCode >= http.StatusOK && resp.StatusCode < http.StatusMultipleChoices {
				return nil
			}

			lastErr = &HTTPError{
				StatusCode: resp.StatusCode,
				Body:       strings.TrimSpace(string(body)),
			}

			if resp.StatusCode < http.StatusInternalServerError {
				return lastErr
			}
		}

		if attempt == maxUploadRetries-1 {
			break
		}

		delay := time.Duration(math.Pow(2, float64(attempt))) * baseUploadRetryDelay
		timer := time.NewTimer(delay)
		select {
		case <-ctx.Done():
			timer.Stop()
			return ctx.Err()
		case <-timer.C:
		}
	}

	return lastErr
}

func (c *Client) pollJobUntilComplete(
	ctx context.Context,
	jobID, indexName string,
	docCount int,
	onProgress func(JobProgress),
) (MutationResult, error) {
	timeoutCtx, cancel := context.WithTimeout(ctx, defaultMutationTimeout)
	defer cancel()

	ticker := time.NewTicker(defaultPollInterval)
	defer ticker.Stop()

	consecutiveErrors := 0

	for {
		status, err := c.GetJobStatus(timeoutCtx, jobID)
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
				return MutationResult{
					JobID:     jobID,
					IndexName: indexName,
					DocCount:  docCount,
				}, nil
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
