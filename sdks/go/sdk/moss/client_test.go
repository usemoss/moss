package moss

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestNewClientUsesDocumentedDefaults(t *testing.T) {
	t.Setenv("MOSS_CLOUD_API_MANAGE_URL", "")
	t.Setenv("MOSS_CLOUD_QUERY_URL", "")

	client := NewClient("project-id", "project-key")

	if client.manageURL != "https://service.usemoss.dev/v1/manage" {
		t.Fatalf("unexpected manage URL: %s", client.manageURL)
	}
	if client.queryURL != "https://service.usemoss.dev/query" {
		t.Fatalf("unexpected query URL: %s", client.queryURL)
	}
}

func TestNewClientHonorsExplicitURLs(t *testing.T) {
	client := NewClient(
		"project-id",
		"project-key",
		WithManageURL("https://custom.example.com/v1/manage"),
		WithQueryURL("https://query.example.com/search"),
	)

	if client.manageURL != "https://custom.example.com/v1/manage" {
		t.Fatalf("unexpected manage URL: %s", client.manageURL)
	}
	if client.queryURL != "https://query.example.com/search" {
		t.Fatalf("unexpected query URL: %s", client.queryURL)
	}
}

func TestGetIndexSendsManageRequestShape(t *testing.T) {
	var gotHeader string
	var gotBody map[string]any

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotHeader = r.Header.Get("X-Project-Key")
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&gotBody); err != nil {
			t.Fatalf("decode request body: %v", err)
		}

		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{
			"id":"idx-1",
			"name":"support-docs",
			"version":"1.0.0",
			"status":"Ready",
			"docCount":124,
			"createdAt":"2026-05-21T00:00:00Z",
			"updatedAt":"2026-05-21T01:00:00Z",
			"model":{"id":"moss-minilm","version":"1.0.0"}
		}`))
	}))
	defer server.Close()

	client := NewClient(
		"project-123",
		"project-key-123",
		WithManageURL(server.URL),
	)

	info, err := client.GetIndex(context.Background(), "support-docs")
	if err != nil {
		t.Fatalf("GetIndex returned error: %v", err)
	}

	if gotHeader != "project-key-123" {
		t.Fatalf("unexpected project key header: %q", gotHeader)
	}
	if gotBody["action"] != "getIndex" {
		t.Fatalf("unexpected action: %#v", gotBody["action"])
	}
	if gotBody["projectId"] != "project-123" {
		t.Fatalf("unexpected projectId: %#v", gotBody["projectId"])
	}
	if gotBody["indexName"] != "support-docs" {
		t.Fatalf("unexpected indexName: %#v", gotBody["indexName"])
	}
	if info.Name != "support-docs" || info.DocCount != 124 || info.Model.ID != "moss-minilm" {
		t.Fatalf("unexpected index info: %#v", info)
	}
}

func TestListIndexesDecodesResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`[
			{"id":"1","name":"alpha","status":"Ready","docCount":2,"model":{"id":"moss-minilm"}},
			{"id":"2","name":"beta","status":"Building","docCount":3,"model":{"id":"custom"}}
		]`))
	}))
	defer server.Close()

	client := NewClient("project-id", "project-key", WithManageURL(server.URL))

	indexes, err := client.ListIndexes(context.Background())
	if err != nil {
		t.Fatalf("ListIndexes returned error: %v", err)
	}
	if len(indexes) != 2 {
		t.Fatalf("unexpected index count: %d", len(indexes))
	}
	if indexes[0].Name != "alpha" || indexes[1].Model.ID != "custom" {
		t.Fatalf("unexpected indexes: %#v", indexes)
	}
}

func TestDeleteIndexSendsExpectedAction(t *testing.T) {
	var gotBody map[string]any

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&gotBody); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`true`))
	}))
	defer server.Close()

	client := NewClient("project-id", "project-key", WithManageURL(server.URL))

	ok, err := client.DeleteIndex(context.Background(), "old-index")
	if err != nil {
		t.Fatalf("DeleteIndex returned error: %v", err)
	}
	if !ok {
		t.Fatal("expected delete result to be true")
	}
	if gotBody["action"] != "deleteIndex" {
		t.Fatalf("unexpected action: %#v", gotBody["action"])
	}
}

func TestGetDocsPassesDocIDs(t *testing.T) {
	var gotBody map[string]any

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&gotBody); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`[
			{"id":"doc-1","text":"hello","metadata":{"topic":"refunds"}}
		]`))
	}))
	defer server.Close()

	client := NewClient("project-id", "project-key", WithManageURL(server.URL))

	docs, err := client.GetDocs(context.Background(), "support-docs", &GetDocumentsOptions{
		DocIDs: []string{"doc-1"},
	})
	if err != nil {
		t.Fatalf("GetDocs returned error: %v", err)
	}
	if len(docs) != 1 || docs[0].Metadata["topic"] != "refunds" {
		t.Fatalf("unexpected docs: %#v", docs)
	}

	docIDs, ok := gotBody["docIds"].([]any)
	if !ok || len(docIDs) != 1 || docIDs[0] != "doc-1" {
		t.Fatalf("unexpected docIds payload: %#v", gotBody["docIds"])
	}
}

func TestQuerySendsExpectedCloudPayload(t *testing.T) {
	var gotBody map[string]any

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&gotBody); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{
			"docs":[{"id":"doc-1","text":"Refunds take 5-7 days","score":0.91,"metadata":{"topic":"refunds"}}],
			"query":"refund policy",
			"indexName":"support-docs",
			"timeTakenMs":17
		}`))
	}))
	defer server.Close()

	client := NewClient(
		"project-id",
		"project-key",
		WithQueryURL(server.URL),
	)

	result, err := client.Query(context.Background(), "support-docs", "refund policy", &QueryOptions{
		TopK:      7,
		Embedding: []float32{0.1, 0.2, 0.3},
	})
	if err != nil {
		t.Fatalf("Query returned error: %v", err)
	}

	if gotBody["projectKey"] != "project-key" {
		t.Fatalf("unexpected projectKey: %#v", gotBody["projectKey"])
	}
	if gotBody["topK"] != float64(7) {
		t.Fatalf("unexpected topK: %#v", gotBody["topK"])
	}
	if _, ok := gotBody["queryEmbedding"]; !ok {
		t.Fatalf("queryEmbedding missing from payload: %#v", gotBody)
	}
	if len(result.Docs) != 1 || result.Docs[0].Score != 0.91 {
		t.Fatalf("unexpected query result: %#v", result)
	}
	if result.TimeTakenMs == nil || *result.TimeTakenMs != 17 {
		t.Fatalf("unexpected timeTakenMs: %#v", result.TimeTakenMs)
	}
}

func TestQueryRejectsUnsupportedFilter(t *testing.T) {
	client := NewClient("project-id", "project-key")

	_, err := client.Query(context.Background(), "support-docs", "refund policy", &QueryOptions{
		Filter: map[string]any{"field": "topic"},
	})
	if !errors.Is(err, ErrUnsupportedQueryFilter) {
		t.Fatalf("expected ErrUnsupportedQueryFilter, got %v", err)
	}
}

func TestManageHTTPErrorIsWrapped(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	defer server.Close()

	client := NewClient("project-id", "project-key", WithManageURL(server.URL))

	_, err := client.GetIndex(context.Background(), "support-docs")
	if err == nil {
		t.Fatal("expected GetIndex to fail")
	}

	var httpErr *HTTPError
	if !errors.As(err, &httpErr) {
		t.Fatalf("expected HTTPError, got %T", err)
	}
	if httpErr.StatusCode != http.StatusInternalServerError {
		t.Fatalf("unexpected status code: %d", httpErr.StatusCode)
	}
}
