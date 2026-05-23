package moss

import (
	"context"
	"encoding/json"
	"errors"
	"testing"

	mosscore "github.com/usemoss/moss/sdks/go/bindings"
)

type fakeManageRuntime struct {
	closeCalled    bool
	createIndexFn  func(name string, docs []mosscore.DocumentInfo, modelID string) (mosscore.MutationResult, error)
	addDocsFn      func(name string, docs []mosscore.DocumentInfo, options *mosscore.MutationOptions) (mosscore.MutationResult, error)
	deleteDocsFn   func(name string, docIDs []string) (mosscore.MutationResult, error)
	getJobStatusFn func(jobID string) (mosscore.JobStatusResponse, error)
	getIndexFn     func(name string) (mosscore.IndexInfo, error)
	listIndexesFn  func() ([]mosscore.IndexInfo, error)
	deleteIndexFn  func(name string) (bool, error)
	getDocsFn      func(name string, docIDs []string) ([]mosscore.DocumentInfo, error)
}

func (f *fakeManageRuntime) Close() error {
	f.closeCalled = true
	return nil
}

func (f *fakeManageRuntime) CreateIndex(name string, docs []mosscore.DocumentInfo, modelID string) (mosscore.MutationResult, error) {
	if f.createIndexFn == nil {
		return mosscore.MutationResult{}, nil
	}
	return f.createIndexFn(name, docs, modelID)
}

func (f *fakeManageRuntime) AddDocs(name string, docs []mosscore.DocumentInfo, options *mosscore.MutationOptions) (mosscore.MutationResult, error) {
	if f.addDocsFn == nil {
		return mosscore.MutationResult{}, nil
	}
	return f.addDocsFn(name, docs, options)
}

func (f *fakeManageRuntime) DeleteDocs(name string, docIDs []string) (mosscore.MutationResult, error) {
	if f.deleteDocsFn == nil {
		return mosscore.MutationResult{}, nil
	}
	return f.deleteDocsFn(name, docIDs)
}

func (f *fakeManageRuntime) GetJobStatus(jobID string) (mosscore.JobStatusResponse, error) {
	if f.getJobStatusFn == nil {
		return mosscore.JobStatusResponse{}, nil
	}
	return f.getJobStatusFn(jobID)
}

func (f *fakeManageRuntime) GetIndex(name string) (mosscore.IndexInfo, error) {
	if f.getIndexFn == nil {
		return mosscore.IndexInfo{}, nil
	}
	return f.getIndexFn(name)
}

func (f *fakeManageRuntime) ListIndexes() ([]mosscore.IndexInfo, error) {
	if f.listIndexesFn == nil {
		return nil, nil
	}
	return f.listIndexesFn()
}

func (f *fakeManageRuntime) DeleteIndex(name string) (bool, error) {
	if f.deleteIndexFn == nil {
		return false, nil
	}
	return f.deleteIndexFn(name)
}

func (f *fakeManageRuntime) GetDocs(name string, docIDs []string) ([]mosscore.DocumentInfo, error) {
	if f.getDocsFn == nil {
		return nil, nil
	}
	return f.getDocsFn(name, docIDs)
}

type fakeIndexRuntime struct {
	closeCalled      bool
	loaded           map[string]bool
	loadIndexFn      func(indexName string, options *mosscore.LoadIndexOptions) (mosscore.IndexInfo, error)
	unloadIndexFn    func(indexName string) error
	queryFn          func(indexName, query string, queryEmbedding []float32, topK int, alpha float32, filterJSON *string) (mosscore.SearchResult, error)
	queryTextFn      func(indexName, query string, topK int, alpha float32, filterJSON *string) (mosscore.SearchResult, error)
	loadQueryModelFn func(indexName string) error
	refreshIndexFn   func(indexName string) (mosscore.RefreshResult, error)
	getIndexInfoFn   func(indexName string) (mosscore.IndexInfo, error)
}

func (f *fakeIndexRuntime) Close() error {
	f.closeCalled = true
	return nil
}

func (f *fakeIndexRuntime) LoadIndex(indexName string, options *mosscore.LoadIndexOptions) (mosscore.IndexInfo, error) {
	if f.loadIndexFn == nil {
		if f.loaded == nil {
			f.loaded = map[string]bool{}
		}
		f.loaded[indexName] = true
		return mosscore.IndexInfo{Name: indexName, Model: mosscore.ModelRef{ID: string(ModelMossMiniLM)}}, nil
	}
	return f.loadIndexFn(indexName, options)
}

func (f *fakeIndexRuntime) UnloadIndex(indexName string) error {
	if f.unloadIndexFn != nil {
		return f.unloadIndexFn(indexName)
	}
	if f.loaded != nil {
		delete(f.loaded, indexName)
	}
	return nil
}

func (f *fakeIndexRuntime) HasIndex(indexName string) bool {
	return f.loaded != nil && f.loaded[indexName]
}

func (f *fakeIndexRuntime) Query(indexName, query string, queryEmbedding []float32, topK int, alpha float32, filterJSON *string) (mosscore.SearchResult, error) {
	if f.queryFn == nil {
		return mosscore.SearchResult{}, nil
	}
	return f.queryFn(indexName, query, queryEmbedding, topK, alpha, filterJSON)
}

func (f *fakeIndexRuntime) QueryText(indexName, query string, topK int, alpha float32, filterJSON *string) (mosscore.SearchResult, error) {
	if f.queryTextFn == nil {
		return mosscore.SearchResult{}, nil
	}
	return f.queryTextFn(indexName, query, topK, alpha, filterJSON)
}

func (f *fakeIndexRuntime) LoadQueryModel(indexName string) error {
	if f.loadQueryModelFn == nil {
		return nil
	}
	return f.loadQueryModelFn(indexName)
}

func (f *fakeIndexRuntime) RefreshIndex(indexName string) (mosscore.RefreshResult, error) {
	if f.refreshIndexFn == nil {
		return mosscore.RefreshResult{}, nil
	}
	return f.refreshIndexFn(indexName)
}

func (f *fakeIndexRuntime) GetIndexInfo(indexName string) (mosscore.IndexInfo, error) {
	if f.getIndexInfoFn == nil {
		return mosscore.IndexInfo{}, nil
	}
	return f.getIndexInfoFn(indexName)
}

func newTestClient(manage manageRuntime, index indexRuntime) *Client {
	client := NewClient("project-id", "project-key")
	client.manageClient = manage
	client.indexMgr = index
	return client
}

func TestGetIndexUsesBindingsRuntime(t *testing.T) {
	client := newTestClient(&fakeManageRuntime{
		getIndexFn: func(name string) (mosscore.IndexInfo, error) {
			if name != "support-docs" {
				t.Fatalf("unexpected index name: %q", name)
			}
			return mosscore.IndexInfo{
				ID:       "idx-1",
				Name:     "support-docs",
				Status:   "Ready",
				DocCount: 124,
				Model:    mosscore.ModelRef{ID: string(ModelMossMiniLM)},
			}, nil
		},
	}, nil)

	info, err := client.GetIndex(context.Background(), "support-docs")
	if err != nil {
		t.Fatalf("GetIndex returned error: %v", err)
	}
	if info.Name != "support-docs" || info.DocCount != 124 || info.Model.ID != string(ModelMossMiniLM) {
		t.Fatalf("unexpected index info: %#v", info)
	}
}

func TestListIndexesUsesBindingsRuntime(t *testing.T) {
	client := newTestClient(&fakeManageRuntime{
		listIndexesFn: func() ([]mosscore.IndexInfo, error) {
			return []mosscore.IndexInfo{
				{Name: "alpha", Status: "Ready", DocCount: 2, Model: mosscore.ModelRef{ID: string(ModelMossMiniLM)}},
				{Name: "beta", Status: "Building", DocCount: 3, Model: mosscore.ModelRef{ID: string(ModelCustom)}},
			}, nil
		},
	}, nil)

	indexes, err := client.ListIndexes(context.Background())
	if err != nil {
		t.Fatalf("ListIndexes returned error: %v", err)
	}
	if len(indexes) != 2 {
		t.Fatalf("unexpected index count: %d", len(indexes))
	}
	if indexes[0].Name != "alpha" || indexes[1].Model.ID != string(ModelCustom) {
		t.Fatalf("unexpected indexes: %#v", indexes)
	}
}

func TestGetDocsPassesDocIDsToBindings(t *testing.T) {
	client := newTestClient(&fakeManageRuntime{
		getDocsFn: func(name string, docIDs []string) ([]mosscore.DocumentInfo, error) {
			if name != "support-docs" {
				t.Fatalf("unexpected index name: %q", name)
			}
			if len(docIDs) != 1 || docIDs[0] != "doc-1" {
				t.Fatalf("unexpected doc IDs: %#v", docIDs)
			}
			return []mosscore.DocumentInfo{
				{ID: "doc-1", Text: "hello", Metadata: map[string]string{"topic": "refunds"}},
			}, nil
		},
	}, nil)

	docs, err := client.GetDocs(context.Background(), "support-docs", &GetDocumentsOptions{
		DocIDs: []string{"doc-1"},
	})
	if err != nil {
		t.Fatalf("GetDocs returned error: %v", err)
	}
	if len(docs) != 1 || docs[0].Metadata["topic"] != "refunds" {
		t.Fatalf("unexpected docs: %#v", docs)
	}
}

func TestQueryRequiresLoadedIndex(t *testing.T) {
	client := newTestClient(nil, &fakeIndexRuntime{loaded: map[string]bool{}})

	_, err := client.Query(context.Background(), "support-docs", "refund policy", nil)
	if !errors.Is(err, ErrIndexNotLoaded) {
		t.Fatalf("expected ErrIndexNotLoaded, got %v", err)
	}
}

func TestQueryUsesLocalBindingsAndSupportsFilters(t *testing.T) {
	client := newTestClient(nil, &fakeIndexRuntime{
		loaded: map[string]bool{"support-docs": true},
		queryTextFn: func(indexName, query string, topK int, alpha float32, filterJSON *string) (mosscore.SearchResult, error) {
			if indexName != "support-docs" {
				t.Fatalf("unexpected index name: %q", indexName)
			}
			if query != "refund policy" {
				t.Fatalf("unexpected query: %q", query)
			}
			if topK != 7 {
				t.Fatalf("unexpected topK: %d", topK)
			}
			if alpha != 0.6 {
				t.Fatalf("unexpected alpha: %f", alpha)
			}
			if filterJSON == nil {
				t.Fatal("expected filter JSON to be passed")
			}

			var decoded map[string]any
			if err := json.Unmarshal([]byte(*filterJSON), &decoded); err != nil {
				t.Fatalf("decode filter: %v", err)
			}
			if decoded["field"] != "topic" {
				t.Fatalf("unexpected filter payload: %#v", decoded)
			}

			timeTaken := 17
			return mosscore.SearchResult{
				Docs:        []mosscore.QueryResultDocumentInfo{{ID: "doc-1", Text: "Refunds take 5-7 days", Score: 0.91, Metadata: map[string]string{"topic": "refunds"}}},
				Query:       query,
				IndexName:   &indexName,
				TimeTakenMs: timeTaken,
			}, nil
		},
	})

	alpha := 0.6
	result, err := client.Query(context.Background(), "support-docs", "refund policy", &QueryOptions{
		TopK:   7,
		Alpha:  &alpha,
		Filter: map[string]any{"field": "topic"},
	})
	if err != nil {
		t.Fatalf("Query returned error: %v", err)
	}
	if len(result.Docs) != 1 || result.Docs[0].Score != 0.91 {
		t.Fatalf("unexpected query result: %#v", result)
	}
	if result.TimeTakenMs == nil || *result.TimeTakenMs != 17 {
		t.Fatalf("unexpected timeTakenMs: %#v", result.TimeTakenMs)
	}
}

func TestLoadIndexSkipsQueryModelForCustomEmbeddings(t *testing.T) {
	loadQueryModelCalled := false
	client := newTestClient(nil, &fakeIndexRuntime{
		loadIndexFn: func(indexName string, options *mosscore.LoadIndexOptions) (mosscore.IndexInfo, error) {
			return mosscore.IndexInfo{
				Name:  indexName,
				Model: mosscore.ModelRef{ID: string(ModelCustom)},
			}, nil
		},
		loadQueryModelFn: func(indexName string) error {
			loadQueryModelCalled = true
			return nil
		},
	})

	name, err := client.LoadIndex(context.Background(), "custom-index", &LoadIndexOptions{})
	if err != nil {
		t.Fatalf("LoadIndex returned error: %v", err)
	}
	if name != "custom-index" {
		t.Fatalf("unexpected loaded index name: %q", name)
	}
	if loadQueryModelCalled {
		t.Fatal("expected custom embedding index to skip query model loading")
	}
}

func TestLoadIndexRejectsUnsupportedCachePath(t *testing.T) {
	client := newTestClient(nil, &fakeIndexRuntime{})

	_, err := client.LoadIndex(context.Background(), "support-docs", &LoadIndexOptions{CachePath: "/tmp/cache"})
	if !errors.Is(err, ErrUnsupportedCachePath) {
		t.Fatalf("expected ErrUnsupportedCachePath, got %v", err)
	}
}

func TestCloseReleasesInitializedBindings(t *testing.T) {
	manage := &fakeManageRuntime{}
	index := &fakeIndexRuntime{}
	client := newTestClient(manage, index)

	if err := client.Close(); err != nil {
		t.Fatalf("Close returned error: %v", err)
	}
	if !manage.closeCalled || !index.closeCalled {
		t.Fatalf("expected runtimes to be closed: manage=%v index=%v", manage.closeCalled, index.closeCalled)
	}
}
