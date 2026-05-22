package moss

import "context"

const defaultTopK = 5

// Query executes a cloud query against the configured index.
func (c *Client) Query(ctx context.Context, indexName, query string, options *QueryOptions) (SearchResult, error) {
	if err := c.validateQueryRequest(indexName); err != nil {
		return SearchResult{}, err
	}
	if options != nil && options.Filter != nil {
		return SearchResult{}, ErrUnsupportedQueryFilter
	}

	topK := defaultTopK
	if options != nil && options.TopK > 0 {
		topK = options.TopK
	}

	var embedding []float32
	if options != nil && len(options.Embedding) > 0 {
		embedding = options.Embedding
	}

	response, err := c.queryAPI.Query(ctx, c.queryURL, c.projectID, c.projectKey, indexName, query, topK, embedding)
	if err != nil {
		return SearchResult{}, normalizeError(err)
	}
	return toSearchResult(response), nil
}
