package moss

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
)

func TestCreateIndexRunsInitUploadUploadStartBuildAndPoll(t *testing.T) {
	var initSeen, startSeen bool
	var uploaded []byte
	var pollCount atomic.Int32

	mux := http.NewServeMux()
	server := httptest.NewServer(mux)
	defer server.Close()

	mux.HandleFunc("/manage", func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode request body: %v", err)
		}

		switch body["action"] {
		case "initUpload":
			initSeen = true
			if body["modelId"] != "moss-minilm" {
				t.Fatalf("unexpected modelId: %#v", body["modelId"])
			}
			if body["dimension"] != float64(0) {
				t.Fatalf("unexpected dimension: %#v", body["dimension"])
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"jobId":"job-create","uploadUrl":"` + server.URL + `/upload","expiresIn":3600}`))
		case "startBuild":
			startSeen = true
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"jobId":"job-create","status":"building"}`))
		case "getJobStatus":
			w.Header().Set("Content-Type", "application/json")
			if pollCount.Add(1) == 1 {
				_, _ = w.Write([]byte(`{"jobId":"job-create","status":"building","progress":42,"currentPhase":"building_index","error":null,"createdAt":"2026-05-22T00:00:00Z","updatedAt":"2026-05-22T00:00:01Z","completedAt":null}`))
				return
			}
			_, _ = w.Write([]byte(`{"jobId":"job-create","status":"completed","progress":100,"currentPhase":null,"error":null,"createdAt":"2026-05-22T00:00:00Z","updatedAt":"2026-05-22T00:00:02Z","completedAt":"2026-05-22T00:00:02Z"}`))
		default:
			t.Fatalf("unexpected action: %#v", body["action"])
		}
	})

	mux.HandleFunc("/upload", func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		data, err := io.ReadAll(r.Body)
		if err != nil {
			t.Fatalf("read upload body: %v", err)
		}
		uploaded = data
		w.WriteHeader(http.StatusOK)
	})

	client := NewClient("project-id", "project-key", WithManageURL(server.URL+"/manage"))
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

	if !initSeen || !startSeen {
		t.Fatalf("expected initUpload and startBuild to both run")
	}
	if len(uploaded) == 0 {
		t.Fatal("expected upload payload to be sent")
	}
	if string(uploaded[:4]) != "MOSS" {
		t.Fatalf("unexpected upload header: %q", string(uploaded[:4]))
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

func TestAddDocsSendsJSONMutationAndPolls(t *testing.T) {
	var gotBody map[string]any

	mux := http.NewServeMux()
	server := httptest.NewServer(mux)
	defer server.Close()

	mux.HandleFunc("/manage", func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		if err := json.NewDecoder(r.Body).Decode(&gotBody); err != nil {
			t.Fatalf("decode request body: %v", err)
		}

		w.Header().Set("Content-Type", "application/json")
		switch gotBody["action"] {
		case "addDocs":
			_, _ = w.Write([]byte(`{"jobId":"job-add","status":"building"}`))
		case "getJobStatus":
			_, _ = w.Write([]byte(`{"jobId":"job-add","status":"completed","progress":100,"currentPhase":null,"error":null,"createdAt":"2026-05-22T00:00:00Z","updatedAt":"2026-05-22T00:00:01Z","completedAt":"2026-05-22T00:00:01Z"}`))
		default:
			t.Fatalf("unexpected action: %#v", gotBody["action"])
		}
	})

	upsert := true
	client := NewClient("project-id", "project-key", WithManageURL(server.URL+"/manage"))
	result, err := client.AddDocs(context.Background(), "support-docs", []DocumentInfo{
		{ID: "doc-3", Text: "new"},
	}, &MutationOptions{Upsert: &upsert})
	if err != nil {
		t.Fatalf("AddDocs returned error: %v", err)
	}

	if result.JobID != "job-add" || result.DocCount != 1 {
		t.Fatalf("unexpected add result: %#v", result)
	}
	if gotBody["action"] != "getJobStatus" {
		t.Fatalf("expected final request to be getJobStatus, got %#v", gotBody["action"])
	}
}

func TestDeleteDocsSendsExpectedAction(t *testing.T) {
	var firstAction string
	var seenDelete bool

	mux := http.NewServeMux()
	server := httptest.NewServer(mux)
	defer server.Close()

	mux.HandleFunc("/manage", func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		action := body["action"].(string)
		if firstAction == "" {
			firstAction = action
		}
		if action == "deleteDocs" {
			seenDelete = true
		}

		w.Header().Set("Content-Type", "application/json")
		if action == "deleteDocs" {
			_, _ = w.Write([]byte(`{"jobId":"job-del","status":"building"}`))
			return
		}
		_, _ = w.Write([]byte(`{"jobId":"job-del","status":"completed","progress":100,"currentPhase":null,"error":null,"createdAt":"2026-05-22T00:00:00Z","updatedAt":"2026-05-22T00:00:01Z","completedAt":"2026-05-22T00:00:01Z"}`))
	})

	client := NewClient("project-id", "project-key", WithManageURL(server.URL+"/manage"))
	result, err := client.DeleteDocs(context.Background(), "support-docs", []string{"doc-1", "doc-2"}, nil)
	if err != nil {
		t.Fatalf("DeleteDocs returned error: %v", err)
	}

	if !seenDelete || firstAction != "deleteDocs" {
		t.Fatalf("expected first action to be deleteDocs, got %q", firstAction)
	}
	if result.DocCount != 2 {
		t.Fatalf("unexpected delete result: %#v", result)
	}
}

func TestGetJobStatusDecodesResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"jobId":"job-123","status":"building","progress":55,"currentPhase":"uploading","error":null,"createdAt":"2026-05-22T00:00:00Z","updatedAt":"2026-05-22T00:00:01Z","completedAt":null}`))
	}))
	defer server.Close()

	client := NewClient("project-id", "project-key", WithManageURL(server.URL))
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
