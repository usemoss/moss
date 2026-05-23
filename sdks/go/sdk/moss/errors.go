package moss

import (
	"errors"
	"fmt"
)

var (
	ErrMissingProjectID     = errors.New("moss: missing project ID")
	ErrMissingProjectKey    = errors.New("moss: missing project key")
	ErrEmptyIndexName       = errors.New("moss: index name must not be empty")
	ErrEmptyJobID           = errors.New("moss: job ID must not be empty")
	ErrEmptyDocuments       = errors.New("moss: documents must not be empty")
	ErrEmptyDocumentIDs     = errors.New("moss: document IDs must not be empty")
	ErrIndexNotLoaded       = errors.New("moss: index is not loaded locally; call LoadIndex first")
	ErrUnsupportedCachePath = errors.New("moss: LoadIndexOptions.CachePath is not supported by the current libmoss bindings")
)

// HTTPError is retained for compatibility with earlier SDK scaffolding.
type HTTPError struct {
	StatusCode int
	Body       string
}

func (e *HTTPError) Error() string {
	if e == nil {
		return "<nil>"
	}
	if e.Body == "" {
		return fmt.Sprintf("moss: http request failed with status %d", e.StatusCode)
	}
	return fmt.Sprintf("moss: http request failed with status %d: %s", e.StatusCode, e.Body)
}
