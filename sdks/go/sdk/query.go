package moss

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"

	mosscore "github.com/usemoss/moss/sdks/go/bindings"
)

const defaultTopK = 5

// Query executes a local query when the index is loaded, otherwise falls back to cloud query.
func (c *Client) Query(ctx context.Context, indexName, query string, options *QueryOptions) (SearchResult, error) {
	if err := ctx.Err(); err != nil {
		return SearchResult{}, err
	}
	if err := c.validateQueryRequest(indexName); err != nil {
		return SearchResult{}, err
	}

	manager, err := c.ensureIndexManager()
	if err != nil {
		if errors.Is(err, mosscore.ErrBindingsUnavailable) {
			return c.queryCloud(ctx, indexName, query, options)
		}
		return SearchResult{}, err
	}
	if manager.HasIndex(indexName) {
		return c.queryLocal(manager, indexName, query, options)
	}
	return c.queryCloud(ctx, indexName, query, options)
}

func (c *Client) queryLocal(manager indexRuntime, indexName, query string, options *QueryOptions) (SearchResult, error) {
	topK := defaultTopK
	alpha := 0.8
	var embedding []float32
	var filterJSON *string

	if options != nil {
		if options.TopK > 0 {
			topK = options.TopK
		}
		if options.Alpha != nil {
			alpha = *options.Alpha
		}
		if len(options.Embedding) > 0 {
			embedding = options.Embedding
		}
		if options.Filter != nil {
			filterBytes, err := json.Marshal(options.Filter)
			if err != nil {
				return SearchResult{}, err
			}
			value := string(filterBytes)
			filterJSON = &value
		}
	}

	if len(embedding) > 0 {
		result, err := manager.Query(indexName, query, embedding, topK, float32(alpha), filterJSON)
		if err != nil {
			return SearchResult{}, err
		}
		return fromCoreSearchResult(result), nil
	}

	result, err := manager.QueryText(indexName, query, topK, float32(alpha), filterJSON)
	if err != nil {
		return SearchResult{}, err
	}
	return fromCoreSearchResult(result), nil
}

type cloudQueryRequest struct {
	Query          string    `json:"query"`
	IndexName      string    `json:"indexName"`
	ProjectID      string    `json:"projectId"`
	ProjectKey     string    `json:"projectKey"`
	TopK           int       `json:"topK"`
	QueryEmbedding []float32 `json:"queryEmbedding,omitempty"`
}

func (c *Client) queryCloud(ctx context.Context, indexName, query string, options *QueryOptions) (SearchResult, error) {
	if strings.TrimSpace(c.queryURL) == "" {
		return SearchResult{}, ErrMissingQueryURL
	}

	topK := defaultTopK
	var embedding []float32
	if options != nil {
		if options.Alpha != nil || options.Filter != nil {
			return SearchResult{}, ErrCloudQueryOptions
		}
		if options.TopK > 0 {
			topK = options.TopK
		}
		if len(options.Embedding) > 0 {
			embedding = options.Embedding
		}
	}

	payload := cloudQueryRequest{
		Query:      query,
		IndexName:  indexName,
		ProjectID:  c.projectID,
		ProjectKey: c.projectKey,
		TopK:       topK,
	}
	if len(embedding) > 0 {
		payload.QueryEmbedding = embedding
	}

	var body bytes.Buffer
	if err := json.NewEncoder(&body).Encode(payload); err != nil {
		return SearchResult{}, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.queryURL, &body)
	if err != nil {
		return SearchResult{}, err
	}
	req.Header.Set("Content-Type", "application/json")

	client := c.httpClient
	if client == nil {
		client = http.DefaultClient
	}
	resp, err := client.Do(req)
	if err != nil {
		return SearchResult{}, err
	}
	defer resp.Body.Close()

	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 16*1024))
		return SearchResult{}, &HTTPError{
			StatusCode: resp.StatusCode,
			Body:       strings.TrimSpace(string(body)),
		}
	}

	var result SearchResult
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return SearchResult{}, err
	}
	return result, nil
}
