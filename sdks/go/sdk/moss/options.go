package moss

import "net/http"

// Option customizes client construction.
type Option func(*clientConfig)

// WithManageURL overrides the default manage endpoint.
func WithManageURL(url string) Option {
	return func(cfg *clientConfig) {
		cfg.manageURL = url
		if cfg.queryURL == "" {
			cfg.queryURL = defaultQueryURL(url)
		}
	}
}

// WithQueryURL overrides the default query endpoint.
func WithQueryURL(url string) Option {
	return func(cfg *clientConfig) {
		cfg.queryURL = url
	}
}

// WithHTTPClient injects a custom HTTP client.
func WithHTTPClient(httpClient *http.Client) Option {
	return func(cfg *clientConfig) {
		if httpClient != nil {
			cfg.httpClient = httpClient
		}
	}
}
