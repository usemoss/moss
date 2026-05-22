package internal

import "context"

type ManageAPI struct {
	httpClient *JSONHTTPClient
}

func NewManageAPI(httpClient *JSONHTTPClient) *ManageAPI {
	return &ManageAPI{httpClient: httpClient}
}

type manageRequest struct {
	Action    string   `json:"action"`
	ProjectID string   `json:"projectId"`
	IndexName string   `json:"indexName,omitempty"`
	DocIDs    []string `json:"docIds,omitempty"`
}

type ModelRefResponse struct {
	ID      string  `json:"id"`
	Version *string `json:"version,omitempty"`
}

type IndexInfoResponse struct {
	ID        string           `json:"id"`
	Name      string           `json:"name"`
	Version   *string          `json:"version,omitempty"`
	Status    string           `json:"status"`
	DocCount  int              `json:"docCount"`
	CreatedAt *string          `json:"createdAt,omitempty"`
	UpdatedAt *string          `json:"updatedAt,omitempty"`
	Model     ModelRefResponse `json:"model"`
}

type DocumentInfoResponse struct {
	ID        string            `json:"id"`
	Text      string            `json:"text"`
	Metadata  map[string]string `json:"metadata,omitempty"`
	Embedding []float32         `json:"embedding,omitempty"`
}

func (a *ManageAPI) GetIndex(ctx context.Context, manageURL, projectID, projectKey, indexName string) (IndexInfoResponse, error) {
	var response IndexInfoResponse
	if err := a.do(ctx, manageURL, projectID, projectKey, manageRequest{
		Action:    "getIndex",
		ProjectID: projectID,
		IndexName: indexName,
	}, &response); err != nil {
		return IndexInfoResponse{}, err
	}
	return response, nil
}

func (a *ManageAPI) ListIndexes(ctx context.Context, manageURL, projectID, projectKey string) ([]IndexInfoResponse, error) {
	var response []IndexInfoResponse
	if err := a.do(ctx, manageURL, projectID, projectKey, manageRequest{
		Action:    "listIndexes",
		ProjectID: projectID,
	}, &response); err != nil {
		return nil, err
	}
	return response, nil
}

func (a *ManageAPI) DeleteIndex(ctx context.Context, manageURL, projectID, projectKey, indexName string) (bool, error) {
	var response bool
	if err := a.do(ctx, manageURL, projectID, projectKey, manageRequest{
		Action:    "deleteIndex",
		ProjectID: projectID,
		IndexName: indexName,
	}, &response); err != nil {
		return false, err
	}
	return response, nil
}

func (a *ManageAPI) GetDocs(
	ctx context.Context,
	manageURL, projectID, projectKey, indexName string,
	docIDs []string,
) ([]DocumentInfoResponse, error) {
	request := manageRequest{
		Action:    "getDocs",
		ProjectID: projectID,
		IndexName: indexName,
	}
	if len(docIDs) > 0 {
		request.DocIDs = docIDs
	}

	var response []DocumentInfoResponse
	if err := a.do(ctx, manageURL, projectID, projectKey, request, &response); err != nil {
		return nil, err
	}
	return response, nil
}

func (a *ManageAPI) do(ctx context.Context, manageURL, projectID, projectKey string, payload any, dest any) error {
	return a.httpClient.PostJSON(ctx, manageURL, map[string]string{
		"Content-Type":  "application/json",
		"X-Project-Key": projectKey,
	}, payload, dest)
}
