package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/usemoss/moss/sdks/go/sdk/moss"
)

func main() {
	projectID := os.Getenv("MOSS_PROJECT_ID")
	projectKey := os.Getenv("MOSS_PROJECT_KEY")
	if projectID == "" || projectKey == "" {
		log.Fatal("set MOSS_PROJECT_ID and MOSS_PROJECT_KEY")
	}

	ctx := context.Background()
	client := moss.NewClient(projectID, projectKey)
	indexName := fmt.Sprintf("go-basic-%d", time.Now().Unix())

	docs := []moss.DocumentInfo{
		{
			ID:   "doc-1",
			Text: "Refunds are processed within five to seven business days.",
			Metadata: map[string]string{
				"topic": "refunds",
			},
		},
		{
			ID:   "doc-2",
			Text: "Orders can be tracked from the account dashboard.",
			Metadata: map[string]string{
				"topic": "shipping",
			},
		},
	}

	result, err := client.CreateIndex(ctx, indexName, docs, nil)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println("create job:", result.JobID)

	search, err := queryWithRetry(ctx, client, indexName, "how long do refunds take?")
	if err != nil {
		log.Fatal(err)
	}

	fmt.Println("query:", search.Query)
	for _, doc := range search.Docs {
		fmt.Printf("%s %.3f %s\n", doc.ID, doc.Score, doc.Text)
	}

	if err := cleanup(ctx, client, indexName); err != nil {
		log.Printf("cleanup warning: %v", err)
	}
}

func cleanup(ctx context.Context, client *moss.Client, indexName string) error {
	_, err := client.DeleteIndex(ctx, indexName)
	return err
}

func queryWithRetry(ctx context.Context, client *moss.Client, indexName, query string) (moss.SearchResult, error) {
	const attempts = 6

	for attempt := 1; attempt <= attempts; attempt++ {
		result, err := client.Query(ctx, indexName, query, &moss.QueryOptions{
			TopK: 3,
		})
		if err == nil {
			return result, nil
		}

		var httpErr *moss.HTTPError
		if !errors.As(err, &httpErr) || httpErr.StatusCode != 503 || attempt == attempts {
			return moss.SearchResult{}, err
		}

		delay := time.Duration(attempt) * 2 * time.Second
		log.Printf("query returned 503, retrying in %s (%d/%d)", delay, attempt, attempts)
		time.Sleep(delay)
	}

	return moss.SearchResult{}, fmt.Errorf("query retries exhausted")
}
