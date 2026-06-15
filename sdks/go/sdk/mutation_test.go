package moss

import (
	"context"
	"strings"
	"testing"

	mosscore "github.com/usemoss/moss/sdks/go/bindings"
)

func TestCreateIndexUsesBindingsAndPollsJobStatus(t *testing.T) {
	polls := 0
	client := newTestClient(&fakeManageRuntime{
		createIndexFn: func(name string, docs []mosscore.DocumentInfo, modelID string) (mosscore.MutationResult, error) {
			if name != "support-docs" {
				t.Fatalf("unexpected index name: %q", name)
			}
			if len(docs) != 2 {
				t.Fatalf("unexpected doc count: %d", len(docs))
			}
			if modelID != string(ModelMossMiniLM) {
				t.Fatalf("unexpected model ID: %q", modelID)
			}
			return mosscore.MutationResult{JobID: "job-create", IndexName: name, DocCount: len(docs)}, nil
		},
		getJobStatusFn: func(jobID string) (mosscore.JobStatusResponse, error) {
			polls++
			if polls == 1 {
				phase := "building_index"
				return mosscore.JobStatusResponse{
					JobID:        jobID,
					Status:       string(JobStatusBuilding),
					Progress:     42,
					CurrentPhase: &phase,
					CreatedAt:    "2026-05-22T00:00:00Z",
					UpdatedAt:    "2026-05-22T00:00:01Z",
				}, nil
			}
			return mosscore.JobStatusResponse{
				JobID:       jobID,
				Status:      string(JobStatusCompleted),
				Progress:    100,
				CreatedAt:   "2026-05-22T00:00:00Z",
				UpdatedAt:   "2026-05-22T00:00:02Z",
				CompletedAt: ptr("2026-05-22T00:00:02Z"),
			}, nil
		},
	}, nil)

	progresses := []JobProgress{}
	result, err := client.CreateIndex(context.Background(), "support-docs", []DocumentInfo{
		{ID: "doc-1", Text: "hello"},
		{ID: "doc-2", Text: "world"},
	}, &CreateIndexOptions{
		OnProgress: func(progress JobProgress) {
			progresses = append(progresses, progress)
		},
	})
	if err != nil {
		t.Fatalf("CreateIndex returned error: %v", err)
	}
	if result.JobID != "job-create" || result.IndexName != "support-docs" || result.DocCount != 2 {
		t.Fatalf("unexpected mutation result: %#v", result)
	}
	if len(progresses) != 2 || progresses[len(progresses)-1].Status != JobStatusCompleted {
		t.Fatalf("unexpected progress updates: %#v", progresses)
	}
}

func TestCreateIndexRejectsMixedEmbeddings(t *testing.T) {
	client := NewClient("project-id", "project-key")

	_, err := client.CreateIndex(context.Background(), "support-docs", []DocumentInfo{
		{ID: "doc-1", Text: "a", Embedding: []float32{1, 2}},
		{ID: "doc-2", Text: "b"},
	}, nil)
	if err == nil || !strings.Contains(err.Error(), "all have embeddings or none") {
		t.Fatalf("expected mixed embeddings error, got %v", err)
	}
}

func TestAddDocsUsesBindingsAndConvertsOptions(t *testing.T) {
	upsert := true
	client := newTestClient(&fakeManageRuntime{
		addDocsFn: func(name string, docs []mosscore.DocumentInfo, options *mosscore.MutationOptions) (mosscore.MutationResult, error) {
			if name != "support-docs" {
				t.Fatalf("unexpected index name: %q", name)
			}
			if len(docs) != 1 || docs[0].ID != "doc-3" {
				t.Fatalf("unexpected docs: %#v", docs)
			}
			if options == nil || options.Upsert == nil || !*options.Upsert {
				t.Fatalf("expected upsert option to be forwarded, got %#v", options)
			}
			return mosscore.MutationResult{JobID: "job-add", IndexName: name, DocCount: len(docs)}, nil
		},
		getJobStatusFn: func(jobID string) (mosscore.JobStatusResponse, error) {
			return mosscore.JobStatusResponse{
				JobID:       jobID,
				Status:      string(JobStatusCompleted),
				Progress:    100,
				CreatedAt:   "2026-05-22T00:00:00Z",
				UpdatedAt:   "2026-05-22T00:00:01Z",
				CompletedAt: ptr("2026-05-22T00:00:01Z"),
			}, nil
		},
	}, nil)

	result, err := client.AddDocs(context.Background(), "support-docs", []DocumentInfo{
		{ID: "doc-3", Text: "new"},
	}, &MutationOptions{Upsert: &upsert})
	if err != nil {
		t.Fatalf("AddDocs returned error: %v", err)
	}
	if result.JobID != "job-add" || result.DocCount != 1 {
		t.Fatalf("unexpected add result: %#v", result)
	}
}

func TestDeleteDocsUsesBindings(t *testing.T) {
	client := newTestClient(&fakeManageRuntime{
		deleteDocsFn: func(name string, docIDs []string) (mosscore.MutationResult, error) {
			if name != "support-docs" {
				t.Fatalf("unexpected index name: %q", name)
			}
			if len(docIDs) != 2 || docIDs[0] != "doc-1" || docIDs[1] != "doc-2" {
				t.Fatalf("unexpected doc IDs: %#v", docIDs)
			}
			return mosscore.MutationResult{JobID: "job-del", IndexName: name, DocCount: len(docIDs)}, nil
		},
		getJobStatusFn: func(jobID string) (mosscore.JobStatusResponse, error) {
			return mosscore.JobStatusResponse{
				JobID:       jobID,
				Status:      string(JobStatusCompleted),
				Progress:    100,
				CreatedAt:   "2026-05-22T00:00:00Z",
				UpdatedAt:   "2026-05-22T00:00:01Z",
				CompletedAt: ptr("2026-05-22T00:00:01Z"),
			}, nil
		},
	}, nil)

	result, err := client.DeleteDocs(context.Background(), "support-docs", []string{"doc-1", "doc-2"}, nil)
	if err != nil {
		t.Fatalf("DeleteDocs returned error: %v", err)
	}
	if result.DocCount != 2 {
		t.Fatalf("unexpected delete result: %#v", result)
	}
}

func TestGetJobStatusUsesBindingsRuntime(t *testing.T) {
	client := newTestClient(&fakeManageRuntime{
		getJobStatusFn: func(jobID string) (mosscore.JobStatusResponse, error) {
			if jobID != "job-123" {
				t.Fatalf("unexpected job ID: %q", jobID)
			}
			phase := "uploading"
			return mosscore.JobStatusResponse{
				JobID:        jobID,
				Status:       string(JobStatusBuilding),
				Progress:     55,
				CurrentPhase: &phase,
				CreatedAt:    "2026-05-22T00:00:00Z",
				UpdatedAt:    "2026-05-22T00:00:01Z",
			}, nil
		},
	}, nil)

	status, err := client.GetJobStatus(context.Background(), "job-123")
	if err != nil {
		t.Fatalf("GetJobStatus returned error: %v", err)
	}
	if status.JobID != "job-123" || status.Status != JobStatusBuilding || status.Progress != 55 {
		t.Fatalf("unexpected job status: %#v", status)
	}
	if status.CurrentPhase == nil || *status.CurrentPhase != JobPhaseUploading {
		t.Fatalf("unexpected current phase: %#v", status.CurrentPhase)
	}
}

func ptr(value string) *string {
	return &value
}
