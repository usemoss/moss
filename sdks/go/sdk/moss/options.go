package moss

import "net/http"

// Option customizes client construction.
type Option func(*clientConfig)

// WithManageURL is retained for compatibility with earlier SDK scaffolding.
// The bindings-backed client currently ignores explicit endpoint overrides.
func WithManageURL(url string) Option {
	return func(cfg *clientConfig) {
		cfg.manageURL = url
	}
}

// WithQueryURL is retained for compatibility with earlier SDK scaffolding.
// The bindings-backed client currently ignores explicit endpoint overrides.
func WithQueryURL(url string) Option {
	return func(cfg *clientConfig) {
		cfg.queryURL = url
	}
}

// WithHTTPClient is retained for compatibility with earlier SDK scaffolding.
// The bindings-backed client currently ignores custom HTTP transports.
func WithHTTPClient(_ *http.Client) Option {
	return func(cfg *clientConfig) {}
}
