package moss

import (
	"context"
	"strings"

	mosscore "github.com/usemoss/moss/sdks/go/bindings"
)

// LoadIndex downloads an index into the local native runtime for fast querying.
func (c *Client) LoadIndex(ctx context.Context, indexName string, options *LoadIndexOptions) (string, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}
	if err := c.validateManageRequest(indexName); err != nil {
		return "", err
	}
	if options != nil && strings.TrimSpace(options.CachePath) != "" {
		return "", ErrUnsupportedCachePath
	}

	manager, err := c.ensureIndexManager()
	if err != nil {
		return "", err
	}

	var bindingOptions *mosscore.LoadIndexOptions
	if options != nil {
		bindingOptions = &mosscore.LoadIndexOptions{
			AutoRefresh:              options.AutoRefresh,
			PollingIntervalInSeconds: options.PollingIntervalInSeconds,
		}
	}

	info, err := manager.LoadIndex(indexName, bindingOptions)
	if err != nil {
		return "", err
	}
	if info.Model.ID != string(ModelCustom) {
		if err := manager.LoadQueryModel(indexName); err != nil {
			return "", err
		}
	}
	if info.Name != "" {
		return info.Name, nil
	}
	return indexName, nil
}

// UnloadIndex removes a previously loaded index from the local runtime.
func (c *Client) UnloadIndex(ctx context.Context, indexName string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if strings.TrimSpace(indexName) == "" {
		return ErrEmptyIndexName
	}

	manager, err := c.ensureIndexManager()
	if err != nil {
		return err
	}
	return manager.UnloadIndex(indexName)
}

// RefreshIndex refreshes a locally loaded index from the cloud when newer data is available.
func (c *Client) RefreshIndex(ctx context.Context, indexName string) (RefreshResult, error) {
	if err := ctx.Err(); err != nil {
		return RefreshResult{}, err
	}
	if err := c.validateManageRequest(indexName); err != nil {
		return RefreshResult{}, err
	}

	manager, err := c.ensureIndexManager()
	if err != nil {
		return RefreshResult{}, err
	}

	result, err := manager.RefreshIndex(indexName)
	if err != nil {
		return RefreshResult{}, err
	}
	return RefreshResult{
		IndexName:         result.IndexName,
		PreviousUpdatedAt: result.PreviousUpdatedAt,
		NewUpdatedAt:      result.NewUpdatedAt,
		WasUpdated:        result.WasUpdated,
	}, nil
}

// GetIndexInfo returns metadata for a locally loaded index.
func (c *Client) GetIndexInfo(ctx context.Context, indexName string) (IndexInfo, error) {
	if err := ctx.Err(); err != nil {
		return IndexInfo{}, err
	}
	if err := c.validateManageRequest(indexName); err != nil {
		return IndexInfo{}, err
	}

	manager, err := c.ensureIndexManager()
	if err != nil {
		return IndexInfo{}, err
	}

	info, err := manager.GetIndexInfo(indexName)
	if err != nil {
		return IndexInfo{}, err
	}
	return fromCoreIndexInfo(info), nil
}
