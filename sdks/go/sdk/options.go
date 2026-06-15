package moss

import "net/http"

// Option customizes client construction.
type Option func(*clientConfig)

// WithManageURL overrides the manage endpoint used to derive the default query endpoint.
func WithManageURL(url string) Option {
	return func(cfg *clientConfig) {
		cfg.manageURL = url
		if !cfg.querySet {
			cfg.queryURL = defaultQueryURL(url)
		}
	}
}

// WithQueryURL overrides the cloud query endpoint used when an index is not loaded locally.
func WithQueryURL(url string) Option {
	return func(cfg *clientConfig) {
		cfg.queryURL = url
		cfg.querySet = true
	}
}

// WithHTTPClient injects a custom HTTP client for cloud query fallback.
func WithHTTPClient(httpClient *http.Client) Option {
	return func(cfg *clientConfig) {
		if httpClient != nil {
			cfg.httpClient = httpClient
		}
	}
}
