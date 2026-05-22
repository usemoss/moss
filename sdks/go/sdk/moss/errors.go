package moss

import (
	"errors"
	"fmt"
)

var (
	ErrMissingProjectID       = errors.New("moss: missing project ID")
	ErrMissingProjectKey      = errors.New("moss: missing project key")
	ErrMissingManageURL       = errors.New("moss: manage URL is not configured")
	ErrMissingQueryURL        = errors.New("moss: query URL is not configured")
	ErrEmptyIndexName         = errors.New("moss: index name must not be empty")
	ErrUnsupportedQueryFilter = errors.New("moss: query filters are not supported in the cloud-only Go SDK yet")
)

// HTTPError wraps non-2xx responses from Moss services.
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
