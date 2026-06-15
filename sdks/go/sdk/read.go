package moss

import "context"

// GetIndex fetches metadata for a single index.
func (c *Client) GetIndex(ctx context.Context, indexName string) (IndexInfo, error) {
	if err := ctx.Err(); err != nil {
		return IndexInfo{}, err
	}
	if err := c.validateManageRequest(indexName); err != nil {
		return IndexInfo{}, err
	}
	manage, err := c.ensureManageClient()
	if err != nil {
		return IndexInfo{}, err
	}
	response, err := manage.GetIndex(indexName)
	if err != nil {
		return IndexInfo{}, err
	}
	return fromCoreIndexInfo(response), nil
}

// ListIndexes returns all indexes for the configured project.
func (c *Client) ListIndexes(ctx context.Context) ([]IndexInfo, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if err := validateCredentials(c.projectID, c.projectKey); err != nil {
		return nil, err
	}
	manage, err := c.ensureManageClient()
	if err != nil {
		return nil, err
	}
	response, err := manage.ListIndexes()
	if err != nil {
		return nil, err
	}

	out := make([]IndexInfo, 0, len(response))
	for _, item := range response {
		out = append(out, fromCoreIndexInfo(item))
	}
	return out, nil
}

// DeleteIndex removes an index from the configured project.
func (c *Client) DeleteIndex(ctx context.Context, indexName string) (bool, error) {
	if err := ctx.Err(); err != nil {
		return false, err
	}
	if err := c.validateManageRequest(indexName); err != nil {
		return false, err
	}
	manage, err := c.ensureManageClient()
	if err != nil {
		return false, err
	}
	ok, err := manage.DeleteIndex(indexName)
	if err != nil {
		return false, err
	}
	return ok, nil
}

// GetDocs retrieves all documents for an index or a selected subset by ID.
func (c *Client) GetDocs(ctx context.Context, indexName string, options *GetDocumentsOptions) ([]DocumentInfo, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if err := c.validateManageRequest(indexName); err != nil {
		return nil, err
	}
	var docIDs []string
	if options != nil {
		docIDs = options.DocIDs
	}

	manage, err := c.ensureManageClient()
	if err != nil {
		return nil, err
	}
	response, err := manage.GetDocs(indexName, docIDs)
	if err != nil {
		return nil, err
	}

	out := make([]DocumentInfo, 0, len(response))
	for _, item := range response {
		out = append(out, fromCoreDocumentInfo(item))
	}
	return out, nil
}
