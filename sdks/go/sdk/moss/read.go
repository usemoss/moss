package moss

import "context"

// GetIndex fetches metadata for a single index.
func (c *Client) GetIndex(ctx context.Context, indexName string) (IndexInfo, error) {
	if err := c.validateManageRequest(indexName); err != nil {
		return IndexInfo{}, err
	}
	response, err := c.manageAPI.GetIndex(ctx, c.manageURL, c.projectID, c.projectKey, indexName)
	if err != nil {
		return IndexInfo{}, normalizeError(err)
	}
	return toIndexInfo(response), nil
}

// ListIndexes returns all indexes for the configured project.
func (c *Client) ListIndexes(ctx context.Context) ([]IndexInfo, error) {
	if err := validateCredentials(c.projectID, c.projectKey); err != nil {
		return nil, err
	}
	if c.manageURL == "" {
		return nil, ErrMissingManageURL
	}
	response, err := c.manageAPI.ListIndexes(ctx, c.manageURL, c.projectID, c.projectKey)
	if err != nil {
		return nil, normalizeError(err)
	}

	out := make([]IndexInfo, 0, len(response))
	for _, item := range response {
		out = append(out, toIndexInfo(item))
	}
	return out, nil
}

// DeleteIndex removes an index from the configured project.
func (c *Client) DeleteIndex(ctx context.Context, indexName string) (bool, error) {
	if err := c.validateManageRequest(indexName); err != nil {
		return false, err
	}
	ok, err := c.manageAPI.DeleteIndex(ctx, c.manageURL, c.projectID, c.projectKey, indexName)
	if err != nil {
		return false, normalizeError(err)
	}
	return ok, nil
}

// GetDocs retrieves all documents for an index or a selected subset by ID.
func (c *Client) GetDocs(ctx context.Context, indexName string, options *GetDocumentsOptions) ([]DocumentInfo, error) {
	if err := c.validateManageRequest(indexName); err != nil {
		return nil, err
	}
	var docIDs []string
	if options != nil {
		docIDs = options.DocIDs
	}

	response, err := c.manageAPI.GetDocs(ctx, c.manageURL, c.projectID, c.projectKey, indexName, docIDs)
	if err != nil {
		return nil, normalizeError(err)
	}

	out := make([]DocumentInfo, 0, len(response))
	for _, item := range response {
		out = append(out, toDocumentInfo(item))
	}
	return out, nil
}
