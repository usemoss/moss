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

type initUploadRequest struct {
	Action    string `json:"action"`
	ProjectID string `json:"projectId"`
	IndexName string `json:"indexName"`
	ModelID   string `json:"modelId"`
	DocCount  int    `json:"docCount"`
	Dimension int    `json:"dimension"`
}

type addDocsRequest struct {
	Action    string                 `json:"action"`
	ProjectID string                 `json:"projectId"`
	IndexName string                 `json:"indexName"`
	Docs      []DocumentInfoResponse `json:"docs"`
	Options   *addDocsOptions        `json:"options,omitempty"`
}

type addDocsOptions struct {
	Upsert *bool `json:"upsert,omitempty"`
}

type jobRequest struct {
	Action    string `json:"action"`
	ProjectID string `json:"projectId"`
	JobID     string `json:"jobId"`
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

type InitUploadResponse struct {
	JobID     string `json:"jobId"`
	UploadURL string `json:"uploadUrl"`
	ExpiresIn int    `json:"expiresIn"`
}

type MutationResponse struct {
	JobID  string `json:"jobId"`
	Status string `json:"status"`
}

type JobStatusResponse struct {
	JobID        string  `json:"jobId"`
	Status       string  `json:"status"`
	Progress     float64 `json:"progress"`
	CurrentPhase *string `json:"currentPhase"`
	Error        *string `json:"error"`
	CreatedAt    string  `json:"createdAt"`
	UpdatedAt    string  `json:"updatedAt"`
	CompletedAt  *string `json:"completedAt"`
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

func (a *ManageAPI) InitUpload(
	ctx context.Context,
	manageURL, projectID, projectKey, indexName, modelID string,
	docCount, dimension int,
) (InitUploadResponse, error) {
	var response InitUploadResponse
	if err := a.do(ctx, manageURL, projectID, projectKey, initUploadRequest{
		Action:    "initUpload",
		ProjectID: projectID,
		IndexName: indexName,
		ModelID:   modelID,
		DocCount:  docCount,
		Dimension: dimension,
	}, &response); err != nil {
		return InitUploadResponse{}, err
	}
	return response, nil
}

func (a *ManageAPI) StartBuild(ctx context.Context, manageURL, projectID, projectKey, jobID string) (MutationResponse, error) {
	var response MutationResponse
	if err := a.do(ctx, manageURL, projectID, projectKey, jobRequest{
		Action:    "startBuild",
		ProjectID: projectID,
		JobID:     jobID,
	}, &response); err != nil {
		return MutationResponse{}, err
	}
	return response, nil
}

func (a *ManageAPI) AddDocs(
	ctx context.Context,
	manageURL, projectID, projectKey, indexName string,
	docs []DocumentInfoResponse,
	upsert *bool,
) (MutationResponse, error) {
	request := addDocsRequest{
		Action:    "addDocs",
		ProjectID: projectID,
		IndexName: indexName,
		Docs:      docs,
	}
	if upsert != nil {
		request.Options = &addDocsOptions{Upsert: upsert}
	}

	var response MutationResponse
	if err := a.do(ctx, manageURL, projectID, projectKey, request, &response); err != nil {
		return MutationResponse{}, err
	}
	return response, nil
}

func (a *ManageAPI) DeleteDocs(
	ctx context.Context,
	manageURL, projectID, projectKey, indexName string,
	docIDs []string,
) (MutationResponse, error) {
	var response MutationResponse
	if err := a.do(ctx, manageURL, projectID, projectKey, manageRequest{
		Action:    "deleteDocs",
		ProjectID: projectID,
		IndexName: indexName,
		DocIDs:    docIDs,
	}, &response); err != nil {
		return MutationResponse{}, err
	}
	return response, nil
}

func (a *ManageAPI) GetJobStatus(ctx context.Context, manageURL, projectID, projectKey, jobID string) (JobStatusResponse, error) {
	var response JobStatusResponse
	if err := a.do(ctx, manageURL, projectID, projectKey, jobRequest{
		Action:    "getJobStatus",
		ProjectID: projectID,
		JobID:     jobID,
	}, &response); err != nil {
		return JobStatusResponse{}, err
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
		"Content-Type":      "application/json",
		"X-Project-Key":     projectKey,
		"X-Service-Version": "v1",
	}, payload, dest)
}
