package moss

import (
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/usemoss/moss/sdks/go/sdk/moss/internal"
)

const (
	DefaultManageURL = "https://service.usemoss.dev/v1/manage"
	defaultTimeout   = 60 * time.Second
)

type clientConfig struct {
	manageURL  string
	queryURL   string
	httpClient *http.Client
}

// Client is the cloud-first Moss Go SDK client.
type Client struct {
	projectID  string
	projectKey string
	manageURL  string
	queryURL   string
	httpClient *http.Client
	manageAPI  *internal.ManageAPI
	queryAPI   *internal.QueryAPI
}

// NewClient constructs a new Moss client with optional overrides.
func NewClient(projectID, projectKey string, opts ...Option) *Client {
	cfg := clientConfig{
		manageURL:  defaultManageURL(),
		httpClient: &http.Client{Timeout: defaultTimeout},
	}
	cfg.queryURL = defaultQueryURL(cfg.manageURL)

	for _, opt := range opts {
		if opt != nil {
			opt(&cfg)
		}
	}

	if cfg.queryURL == "" {
		cfg.queryURL = defaultQueryURL(cfg.manageURL)
	}

	jsonClient := internal.NewJSONHTTPClient(cfg.httpClient)

	return &Client{
		projectID:  strings.TrimSpace(projectID),
		projectKey: strings.TrimSpace(projectKey),
		manageURL:  strings.TrimSpace(cfg.manageURL),
		queryURL:   strings.TrimSpace(cfg.queryURL),
		httpClient: cfg.httpClient,
		manageAPI:  internal.NewManageAPI(jsonClient),
		queryAPI:   internal.NewQueryAPI(jsonClient),
	}
}

func defaultManageURL() string {
	if value := strings.TrimSpace(os.Getenv("MOSS_CLOUD_API_MANAGE_URL")); value != "" {
		return value
	}
	return DefaultManageURL
}

func defaultQueryURL(manageURL string) string {
	if value := strings.TrimSpace(os.Getenv("MOSS_CLOUD_QUERY_URL")); value != "" {
		return value
	}
	if manageURL == "" {
		return ""
	}
	return strings.Replace(manageURL, "/v1/manage", "/query", 1)
}

func (c *Client) validateManageRequest(indexName string) error {
	if err := validateCredentials(c.projectID, c.projectKey); err != nil {
		return err
	}
	if strings.TrimSpace(c.manageURL) == "" {
		return ErrMissingManageURL
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
	if strings.TrimSpace(c.queryURL) == "" {
		return ErrMissingQueryURL
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
