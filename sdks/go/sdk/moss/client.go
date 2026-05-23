package moss

import (
	"strings"
	"sync"

	mosscore "github.com/usemoss/moss/sdks/go/bindings"
)

type clientConfig struct {
	manageURL string
	queryURL  string
}

type manageRuntime interface {
	Close() error
	CreateIndex(name string, docs []mosscore.DocumentInfo, modelID string) (mosscore.MutationResult, error)
	AddDocs(name string, docs []mosscore.DocumentInfo, options *mosscore.MutationOptions) (mosscore.MutationResult, error)
	DeleteDocs(name string, docIDs []string) (mosscore.MutationResult, error)
	GetJobStatus(jobID string) (mosscore.JobStatusResponse, error)
	GetIndex(name string) (mosscore.IndexInfo, error)
	ListIndexes() ([]mosscore.IndexInfo, error)
	DeleteIndex(name string) (bool, error)
	GetDocs(name string, docIDs []string) ([]mosscore.DocumentInfo, error)
}

type indexRuntime interface {
	Close() error
	LoadIndex(indexName string, options *mosscore.LoadIndexOptions) (mosscore.IndexInfo, error)
	UnloadIndex(indexName string) error
	HasIndex(indexName string) bool
	Query(indexName, query string, queryEmbedding []float32, topK int, alpha float32, filterJSON *string) (mosscore.SearchResult, error)
	QueryText(indexName, query string, topK int, alpha float32, filterJSON *string) (mosscore.SearchResult, error)
	LoadQueryModel(indexName string) error
	RefreshIndex(indexName string) (mosscore.RefreshResult, error)
	GetIndexInfo(indexName string) (mosscore.IndexInfo, error)
}

// Client is the bindings-backed Moss Go SDK client.
type Client struct {
	projectID     string
	projectKey    string
	manageURL     string
	queryURL      string
	manageMu      sync.Mutex
	manageClient  manageRuntime
	indexMu       sync.Mutex
	indexMgr      indexRuntime
	manageFactory func(projectID, projectKey string) (manageRuntime, error)
	indexFactory  func(projectID, projectKey string) (indexRuntime, error)
}

// NewClient constructs a new Moss client with optional overrides.
func NewClient(projectID, projectKey string, opts ...Option) *Client {
	cfg := clientConfig{}

	for _, opt := range opts {
		if opt != nil {
			opt(&cfg)
		}
	}

	return &Client{
		projectID:  strings.TrimSpace(projectID),
		projectKey: strings.TrimSpace(projectKey),
		manageURL:  strings.TrimSpace(cfg.manageURL),
		queryURL:   strings.TrimSpace(cfg.queryURL),
		manageFactory: func(projectID, projectKey string) (manageRuntime, error) {
			return mosscore.NewManageClient(projectID, projectKey)
		},
		indexFactory: func(projectID, projectKey string) (indexRuntime, error) {
			return mosscore.NewIndexManager(projectID, projectKey)
		},
	}
}

func (c *Client) validateManageRequest(indexName string) error {
	if err := validateCredentials(c.projectID, c.projectKey); err != nil {
		return err
	}
	if strings.TrimSpace(indexName) == "" {
		return ErrEmptyIndexName
	}
	return nil
}

func (c *Client) validateQueryRequest(indexName string) error {
	if err := validateCredentials(c.projectID, c.projectKey); err != nil {
		return err
	}
	if strings.TrimSpace(indexName) == "" {
		return ErrEmptyIndexName
	}
	return nil
}

func validateCredentials(projectID, projectKey string) error {
	if strings.TrimSpace(projectID) == "" {
		return ErrMissingProjectID
	}
	if strings.TrimSpace(projectKey) == "" {
		return ErrMissingProjectKey
	}
	return nil
}

func (c *Client) ensureManageClient() (manageRuntime, error) {
	c.manageMu.Lock()
	defer c.manageMu.Unlock()

	if c.manageClient != nil {
		return c.manageClient, nil
	}

	client, err := c.manageFactory(c.projectID, c.projectKey)
	if err != nil {
		return nil, err
	}
	c.manageClient = client
	return client, nil
}

func (c *Client) ensureIndexManager() (indexRuntime, error) {
	c.indexMu.Lock()
	defer c.indexMu.Unlock()

	if c.indexMgr != nil {
		return c.indexMgr, nil
	}

	manager, err := c.indexFactory(c.projectID, c.projectKey)
	if err != nil {
		return nil, err
	}
	c.indexMgr = manager
	return manager, nil
}

// Close releases any lazily initialized native runtime handles owned by the client.
func (c *Client) Close() error {
	c.manageMu.Lock()
	manage := c.manageClient
	c.manageClient = nil
	c.manageMu.Unlock()

	c.indexMu.Lock()
	index := c.indexMgr
	c.indexMgr = nil
	c.indexMu.Unlock()

	var firstErr error
	if manage != nil {
		if err := manage.Close(); err != nil && firstErr == nil {
			firstErr = err
		}
	}
	if index != nil {
		if err := index.Close(); err != nil && firstErr == nil {
			firstErr = err
		}
	}
	return firstErr
}
