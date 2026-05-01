/**
 * example_usage.c — Complete cloud workflow example for the Moss C SDK.
 *
 * Demonstrates: create index, get index, list indexes, add docs,
 * get docs, load index, query, delete docs, delete index.
 *
 * Build (macOS):
 *   cargo build --release
 *   clang examples/example_usage.c -o examples/example_usage \
 *     -I. -Ltarget/release -lmoss \
 *     -framework Security -framework SystemConfiguration
 *
 * Run:
 *   export DYLD_LIBRARY_PATH=target/release
 *   ./examples/example_usage <project_id> <project_key>
 */

#include "libmoss.h"
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void check(MossResult r, const char *context) {
    if (r != OK) {
        const char *err = moss_last_error();
        fprintf(stderr, "ERROR [%s]: %s\n", context, err ? err : "(no details)");
        exit(1);
    }
}

int main(int argc, char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <project_id> <project_key>\n", argv[0]);
        return 1;
    }

    const char *project_id  = argv[1];
    const char *project_key = argv[2];

    printf("Moss C SDK Complete Example\n");
    printf("SDK version: %s\n\n", moss_sdk_version());

    /* ── Create client ────────────────────────────────────────── */

    MossClient *client = NULL;
    check(moss_client_new(project_id, project_key, &client), "client_new");

    /* ── Build unique index name ──────────────────────────────── */

    char index_name[64];
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    snprintf(index_name, sizeof(index_name),
             "example-cloud-index-%04d%02d%02d-%02d%02d%02d",
             t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
             t->tm_hour, t->tm_min, t->tm_sec);

    /* ── 1. Create index with documents ───────────────────────── */

    printf("1. Creating index with documents...\n");

    MossMetadataEntry meta_ml[]  = {
        { .key = "category",   .value = "ai" },
        { .key = "topic",      .value = "machine_learning" },
        { .key = "difficulty", .value = "intermediate" },
    };
    MossMetadataEntry meta_dl[]  = {
        { .key = "category",   .value = "ai" },
        { .key = "topic",      .value = "deep_learning" },
        { .key = "difficulty", .value = "advanced" },
    };
    MossMetadataEntry meta_nlp[] = {
        { .key = "category",   .value = "ai" },
        { .key = "topic",      .value = "nlp" },
        { .key = "difficulty", .value = "intermediate" },
    };
    MossMetadataEntry meta_cv[]  = {
        { .key = "category",   .value = "ai" },
        { .key = "topic",      .value = "computer_vision" },
        { .key = "difficulty", .value = "intermediate" },
    };
    MossMetadataEntry meta_rl[]  = {
        { .key = "category",   .value = "ai" },
        { .key = "topic",      .value = "reinforcement_learning" },
        { .key = "difficulty", .value = "advanced" },
    };

    MossDocumentInfo docs[] = {
        {
            .id = "doc1",
            .text = "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed.",
            .metadata = meta_ml, .metadata_count = 3,
        },
        {
            .id = "doc2",
            .text = "Deep learning uses neural networks with multiple layers to model and understand complex patterns in data.",
            .metadata = meta_dl, .metadata_count = 3,
        },
        {
            .id = "doc3",
            .text = "Natural language processing enables computers to interpret and manipulate human language for various applications.",
            .metadata = meta_nlp, .metadata_count = 3,
        },
        {
            .id = "doc4",
            .text = "Computer vision enables machines to interpret and understand visual information from the world around them.",
            .metadata = meta_cv, .metadata_count = 3,
        },
        {
            .id = "doc5",
            .text = "Reinforcement learning is a type of machine learning where an agent learns to make decisions by performing actions and receiving rewards.",
            .metadata = meta_rl, .metadata_count = 3,
        },
    };

    MossMutationResult *created = NULL;
    check(moss_client_create_index(client, index_name, docs, 5, NULL, &created), "create_index");
    printf("   Index created: job_id=%s  doc_count=%zu\n", created->job_id, created->doc_count);
    moss_free_mutation_result(created);

    /* ── 2. Get index information ─────────────────────────────── */

    printf("\n2. Getting index information...\n");
    MossIndexInfo *info = NULL;
    check(moss_client_get_index(client, index_name, &info), "get_index");
    printf("   Name: %s\n", info->name);
    printf("   Doc count: %zu\n", info->doc_count);
    printf("   Model: %s\n", info->model.id);
    printf("   Status: %s\n", info->status);
    moss_free_index_info(info);

    /* ── 3. List all indexes ──────────────────────────────────── */

    printf("\n3. Listing all indexes...\n");
    MossIndexInfo *indexes = NULL;
    size_t index_count = 0;
    check(moss_client_list_indexes(client, &indexes, &index_count), "list_indexes");
    for (size_t i = 0; i < index_count; i++) {
        printf("   - %s: %zu docs, status: %s\n",
               indexes[i].name, indexes[i].doc_count, indexes[i].status);
    }
    moss_free_index_info_list(indexes, index_count);

    /* ── 4. Add more documents ────────────────────────────────── */

    printf("\n4. Adding more documents...\n");

    MossMetadataEntry meta_ds[] = {
        { .key = "category",   .value = "data_science" },
        { .key = "topic",      .value = "analytics" },
        { .key = "difficulty", .value = "intermediate" },
    };
    MossMetadataEntry meta_cloud[] = {
        { .key = "category",   .value = "infrastructure" },
        { .key = "topic",      .value = "cloud" },
        { .key = "difficulty", .value = "beginner" },
    };

    MossDocumentInfo new_docs[] = {
        {
            .id = "doc6",
            .text = "Data science combines statistics, programming, and domain expertise to extract insights from data.",
            .metadata = meta_ds, .metadata_count = 3,
        },
        {
            .id = "doc7",
            .text = "Cloud computing provides on-demand access to computing resources over the internet.",
            .metadata = meta_cloud, .metadata_count = 3,
        },
    };

    MossMutationOptions mut_opts = { .upsert = true };
    MossMutationResult *add_result = NULL;
    check(moss_client_add_docs(client, index_name, new_docs, 2, &mut_opts, &add_result), "add_docs");
    printf("   Documents added: job_id=%s  doc_count=%zu\n", add_result->job_id, add_result->doc_count);
    moss_free_mutation_result(add_result);

    /* ── 5. Get all documents ─────────────────────────────────── */

    printf("\n5. Getting all documents...\n");
    MossDocumentInfo *all_docs = NULL;
    size_t all_count = 0;
    check(moss_client_get_docs(client, index_name, NULL, 0, &all_docs, &all_count), "get_docs_all");
    printf("   Total documents: %zu\n", all_count);
    moss_free_documents(all_docs, all_count);

    /* ── 6. Get specific documents ────────────────────────────── */

    printf("\n6. Getting specific documents...\n");
    const char *specific_ids[] = { "doc1", "doc2", "doc6" };
    MossDocumentInfo *specific_docs = NULL;
    size_t specific_count = 0;
    check(moss_client_get_docs(client, index_name, specific_ids, 3, &specific_docs, &specific_count), "get_docs_specific");
    for (size_t i = 0; i < specific_count; i++) {
        printf("   - %s: %.50s...\n", specific_docs[i].id, specific_docs[i].text);
    }
    moss_free_documents(specific_docs, specific_count);

    /* ── 7. Load index for querying ───────────────────────────── */

    printf("\n7. Loading index for querying...\n");
    MossIndexInfo *loaded = NULL;
    check(moss_client_load_index(client, index_name, NULL, &loaded), "load_index");
    printf("   Loaded: %s (%zu docs)\n", loaded->name, loaded->doc_count);
    moss_free_index_info(loaded);

    /* ── 8. Semantic search ───────────────────────────────────── */

    printf("\n8. Performing semantic search...\n");
    MossQueryOptions qopts = {
        .top_k = 3,
        .alpha = 0.6f,
    };
    MossSearchResult *search = NULL;
    check(moss_client_query(client, index_name, "artificial intelligence and neural networks", &qopts, &search), "query");

    printf("   Query: \"%s\"\n", search->query);
    printf("   Found %zu results:\n", search->doc_count);
    for (size_t i = 0; i < search->doc_count; i++) {
        MossQueryResultDoc *doc = &search->docs[i];
        printf("   %zu. [%s] score=%.3f\n", i + 1, doc->id, doc->score);
        printf("      %.80s...\n", doc->text);
    }
    moss_free_search_result(search);

    /* ── 9. Delete some documents ─────────────────────────────── */

    printf("\n9. Deleting some documents...\n");
    const char *del_ids[] = { "doc6", "doc7" };
    MossMutationResult *del_result = NULL;
    check(moss_client_delete_docs(client, index_name, del_ids, 2, &del_result), "delete_docs");
    printf("   Deleted: doc_count=%zu\n", del_result->doc_count);
    moss_free_mutation_result(del_result);

    /* ── 10. Verify remaining documents ───────────────────────── */

    printf("\n10. Verifying document count after deletion...\n");
    MossDocumentInfo *remaining = NULL;
    size_t remaining_count = 0;
    check(moss_client_get_docs(client, index_name, NULL, 0, &remaining, &remaining_count), "get_docs_remaining");
    printf("   Remaining documents: %zu\n", remaining_count);
    moss_free_documents(remaining, remaining_count);

    /* ── 11. Final search ─────────────────────────────────────── */

    printf("\n11. Final search to verify everything works...\n");
    MossQueryOptions final_opts = { .top_k = 2 };
    MossSearchResult *final_search = NULL;
    check(moss_client_query(client, index_name, "machine learning algorithms", &final_opts, &final_search), "query_final");
    for (size_t i = 0; i < final_search->doc_count; i++) {
        printf("   %zu. [%s] score=%.3f\n", i + 1, final_search->docs[i].id, final_search->docs[i].score);
    }
    moss_free_search_result(final_search);

    /* ── 12. Cleanup ──────────────────────────────────────────── */

    printf("\n12. Cleaning up — deleting the test index...\n");
    bool deleted = false;
    check(moss_client_delete_index(client, index_name, &deleted), "delete_index");
    printf("   Index deleted: %s\n", deleted ? "true" : "false");

    moss_client_free(client);
    printf("\nAll operations completed successfully.\n");

    return 0;
}
