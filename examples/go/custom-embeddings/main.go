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
	indexName := fmt.Sprintf("go-custom-%d", time.Now().Unix())

	docs := []moss.DocumentInfo{
		{
			ID:        "refunds",
			Text:      "Refunds are processed within five business days.",
			Embedding: []float32{1, 0, 0, 0},
		},
		{
			ID:        "shipping",
			Text:      "Track your order from the shipping dashboard.",
			Embedding: []float32{0, 1, 0, 0},
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

	query := []float32{1, 0, 0, 0}
	search, err := client.Query(ctx, indexName, "", &moss.QueryOptions{
		Embedding: query,
		TopK:      2,
	})
	if err != nil {
		log.Fatal(err)
	}

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
