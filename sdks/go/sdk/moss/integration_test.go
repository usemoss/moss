package moss

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"
)

func TestCloudLifecycleIntegration(t *testing.T) {
	projectID := os.Getenv("MOSS_TEST_PROJECT_ID")
	projectKey := os.Getenv("MOSS_TEST_PROJECT_KEY")
	if projectID == "" || projectKey == "" {
		t.Skip("Skipping cloud integration test: set MOSS_TEST_PROJECT_ID and MOSS_TEST_PROJECT_KEY")
	}

	client := NewClient(projectID, projectKey)
	ctx := context.Background()
	indexName := fmt.Sprintf("go-sdk-int-%d", time.Now().UnixNano())

	docs := []DocumentInfo{
		{
			ID:        "doc-1",
			Text:      "Refunds are processed within five business days.",
			Embedding: []float32{1, 0, 0, 0},
		},
		{
			ID:        "doc-2",
			Text:      "Orders can be tracked from the dashboard.",
			Embedding: []float32{0, 1, 0, 0},
		},
	}

	t.Cleanup(func() {
		_, _ = client.DeleteIndex(context.Background(), indexName)
	})

	createResult, err := client.CreateIndex(ctx, indexName, docs, nil)
	if err != nil {
		t.Fatalf("CreateIndex failed: %v", err)
	}
	if createResult.JobID == "" || createResult.IndexName != indexName || createResult.DocCount != 2 {
		t.Fatalf("unexpected create result: %#v", createResult)
	}

	status, err := client.GetJobStatus(ctx, createResult.JobID)
	if err != nil {
		t.Fatalf("GetJobStatus failed: %v", err)
	}
	if status.JobID != createResult.JobID || status.Status != JobStatusCompleted {
		t.Fatalf("unexpected job status: %#v", status)
	}

	info, err := client.GetIndex(ctx, indexName)
	if err != nil {
		t.Fatalf("GetIndex failed: %v", err)
	}
	if info.Name != indexName || info.DocCount != 2 || info.Model.ID != string(ModelCustom) {
		t.Fatalf("unexpected index info: %#v", info)
	}

	gotDocs, err := client.GetDocs(ctx, indexName, nil)
	if err != nil {
		t.Fatalf("GetDocs failed: %v", err)
	}
	if len(gotDocs) != 2 {
		t.Fatalf("unexpected doc count: %d", len(gotDocs))
	}

	search, err := client.Query(ctx, indexName, "", &QueryOptions{
		Embedding: []float32{1, 0, 0, 0},
		TopK:      2,
	})
	if err != nil {
		t.Fatalf("Query failed: %v", err)
	}
	if len(search.Docs) == 0 || search.Docs[0].ID != "doc-1" {
		t.Fatalf("unexpected query result: %#v", search)
	}

	upsert := true
	addResult, err := client.AddDocs(ctx, indexName, []DocumentInfo{
		{
			ID:        "doc-3",
			Text:      "Customers can update shipping addresses before fulfillment.",
			Embedding: []float32{0, 0, 1, 0},
		},
	}, &MutationOptions{Upsert: &upsert})
	if err != nil {
		t.Fatalf("AddDocs failed: %v", err)
	}
	if addResult.DocCount != 1 {
		t.Fatalf("unexpected add result: %#v", addResult)
	}

	info, err = client.GetIndex(ctx, indexName)
	if err != nil {
		t.Fatalf("GetIndex after AddDocs failed: %v", err)
	}
	if info.DocCount != 3 {
		t.Fatalf("unexpected doc count after add: %d", info.DocCount)
	}

	deleteResult, err := client.DeleteDocs(ctx, indexName, []string{"doc-2"}, nil)
	if err != nil {
		t.Fatalf("DeleteDocs failed: %v", err)
	}
	if deleteResult.DocCount != 1 {
		t.Fatalf("unexpected delete result: %#v", deleteResult)
	}

	info, err = client.GetIndex(ctx, indexName)
	if err != nil {
		t.Fatalf("GetIndex after DeleteDocs failed: %v", err)
	}
	if info.DocCount != 2 {
		t.Fatalf("unexpected doc count after delete: %d", info.DocCount)
	}
}
