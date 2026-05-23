package moss

import (
	"context"
	"encoding/json"
)

const defaultTopK = 5

// Query executes a local query against a previously loaded index.
func (c *Client) Query(ctx context.Context, indexName, query string, options *QueryOptions) (SearchResult, error) {
	if err := ctx.Err(); err != nil {
		return SearchResult{}, err
	}
	if err := c.validateQueryRequest(indexName); err != nil {
		return SearchResult{}, err
	}

	manager, err := c.ensureIndexManager()
	if err != nil {
		return SearchResult{}, err
	}
	if !manager.HasIndex(indexName) {
		return SearchResult{}, ErrIndexNotLoaded
	}
	return c.queryLocal(manager, indexName, query, options)
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
			bytes, err := json.Marshal(options.Filter)
			if err != nil {
				return SearchResult{}, err
			}
			value := string(bytes)
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
