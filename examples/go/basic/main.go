package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/usemoss/moss/sdks/go/sdk"
)

func main() {
	projectID := os.Getenv("MOSS_PROJECT_ID")
	projectKey := os.Getenv("MOSS_PROJECT_KEY")
	if projectID == "" || projectKey == "" {
		log.Fatal("set MOSS_PROJECT_ID and MOSS_PROJECT_KEY")
	}

	ctx := context.Background()
	client := moss.NewClient(projectID, projectKey)
	defer func() {
		if err := client.Close(); err != nil {
			log.Printf("close warning: %v", err)
		}
	}()
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

	if _, err := client.LoadIndex(ctx, indexName, &moss.LoadIndexOptions{}); err != nil {
		log.Fatal(err)
	}

	search, err := client.Query(ctx, indexName, "how long do refunds take?", &moss.QueryOptions{
		TopK: 3,
	})
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
