package internal

import "context"

type QueryAPI struct {
	httpClient *JSONHTTPClient
}

func NewQueryAPI(httpClient *JSONHTTPClient) *QueryAPI {
	return &QueryAPI{httpClient: httpClient}
}

type queryRequest struct {
	Query          string    `json:"query"`
	IndexName      string    `json:"indexName"`
	ProjectID      string    `json:"projectId"`
	ProjectKey     string    `json:"projectKey"`
	TopK           int       `json:"topK"`
	QueryEmbedding []float32 `json:"queryEmbedding,omitempty"`
}

type SearchResultResponse struct {
	Docs        []QueryResultDocumentInfoResponse `json:"docs"`
	Query       string                            `json:"query"`
	IndexName   *string                           `json:"indexName,omitempty"`
	TimeTakenMs *int                              `json:"timeTakenMs,omitempty"`
}

type QueryResultDocumentInfoResponse struct {
	ID       string            `json:"id"`
	Text     string            `json:"text"`
	Metadata map[string]string `json:"metadata,omitempty"`
	Score    float64           `json:"score"`
}

func (a *QueryAPI) Query(
	ctx context.Context,
	queryURL, projectID, projectKey, indexName, query string,
	topK int,
	queryEmbedding []float32,
) (SearchResultResponse, error) {
	request := queryRequest{
		Query:      query,
		IndexName:  indexName,
		ProjectID:  projectID,
		ProjectKey: projectKey,
		TopK:       topK,
	}
	if len(queryEmbedding) > 0 {
		request.QueryEmbedding = queryEmbedding
	}

	var response SearchResultResponse
	if err := a.httpClient.PostJSON(ctx, queryURL, map[string]string{
		"Content-Type": "application/json",
	}, request, &response); err != nil {
		return SearchResultResponse{}, err
	}
	return response, nil
}
