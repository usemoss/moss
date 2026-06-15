package moss

import mosscore "github.com/usemoss/moss/sdks/go/bindings"

func toCoreDocumentInfo(value DocumentInfo) mosscore.DocumentInfo {
	return mosscore.DocumentInfo{
		ID:        value.ID,
		Text:      value.Text,
		Metadata:  value.Metadata,
		Embedding: value.Embedding,
	}
}

func toCoreDocumentInfos(values []DocumentInfo) []mosscore.DocumentInfo {
	out := make([]mosscore.DocumentInfo, 0, len(values))
	for _, value := range values {
		out = append(out, toCoreDocumentInfo(value))
	}
	return out
}

func fromCoreIndexInfo(value mosscore.IndexInfo) IndexInfo {
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

func fromCoreDocumentInfo(value mosscore.DocumentInfo) DocumentInfo {
	return DocumentInfo{
		ID:        value.ID,
		Text:      value.Text,
		Metadata:  value.Metadata,
		Embedding: value.Embedding,
	}
}

func fromCoreMutationResult(value mosscore.MutationResult) MutationResult {
	return MutationResult{
		JobID:     value.JobID,
		IndexName: value.IndexName,
		DocCount:  value.DocCount,
	}
}

func fromCoreSearchResult(value mosscore.SearchResult) SearchResult {
	docs := make([]QueryResultDocumentInfo, 0, len(value.Docs))
	for _, item := range value.Docs {
		docs = append(docs, QueryResultDocumentInfo{
			ID:       item.ID,
			Text:     item.Text,
			Metadata: item.Metadata,
			Score:    item.Score,
		})
	}

	var timeTaken *int
	if value.TimeTakenMs != 0 {
		value := value.TimeTakenMs
		timeTaken = &value
	}
	return SearchResult{
		Docs:        docs,
		Query:       value.Query,
		IndexName:   value.IndexName,
		TimeTakenMs: timeTaken,
	}
}

func fromCoreJobStatusResponse(value mosscore.JobStatusResponse) JobStatusResponse {
	var currentPhase *JobPhase
	if value.CurrentPhase != nil {
		phase := JobPhase(*value.CurrentPhase)
		currentPhase = &phase
	}

	return JobStatusResponse{
		JobID:        value.JobID,
		Status:       JobStatus(value.Status),
		Progress:     value.Progress,
		CurrentPhase: currentPhase,
		Error:        value.Error,
		CreatedAt:    value.CreatedAt,
		UpdatedAt:    value.UpdatedAt,
		CompletedAt:  value.CompletedAt,
	}
}
