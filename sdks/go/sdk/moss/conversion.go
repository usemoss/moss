package moss

import (
	"errors"

	"github.com/usemoss/moss/sdks/go/sdk/moss/internal"
)

func toIndexInfo(value internal.IndexInfoResponse) IndexInfo {
	return IndexInfo{
		ID:        value.ID,
		Name:      value.Name,
		Version:   value.Version,
		Status:    IndexStatus(value.Status),
		DocCount:  value.DocCount,
		CreatedAt: value.CreatedAt,
		UpdatedAt: value.UpdatedAt,
		Model: ModelRef{
			ID:      value.Model.ID,
			Version: value.Model.Version,
		},
	}
}

func toDocumentInfo(value internal.DocumentInfoResponse) DocumentInfo {
	return DocumentInfo{
		ID:        value.ID,
		Text:      value.Text,
		Metadata:  value.Metadata,
		Embedding: value.Embedding,
	}
}

func toSearchResult(value internal.SearchResultResponse) SearchResult {
	docs := make([]QueryResultDocumentInfo, 0, len(value.Docs))
	for _, item := range value.Docs {
		docs = append(docs, QueryResultDocumentInfo{
			ID:       item.ID,
			Text:     item.Text,
			Metadata: item.Metadata,
			Score:    item.Score,
		})
	}

	return SearchResult{
		Docs:        docs,
		Query:       value.Query,
		IndexName:   value.IndexName,
		TimeTakenMs: value.TimeTakenMs,
	}
}

func normalizeError(err error) error {
	if err == nil {
		return nil
	}

	var httpErr *internal.HTTPError
	if !errors.As(err, &httpErr) {
		return err
	}

	return &HTTPError{
		StatusCode: httpErr.StatusCode,
		Body:       httpErr.Body,
	}
}
