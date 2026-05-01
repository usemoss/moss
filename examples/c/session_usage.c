/**
 * session_usage.c — Session workflow example for the Moss C SDK.
 *
 * Demonstrates: create client, open session, add docs with metadata,
 * query, query with filter, get docs, push to cloud.
 *
 * Build (macOS):
 *   cargo build --release
 *   clang examples/session_usage.c -o examples/session_usage \
 *     -I. -Ltarget/release -lmoss \
 *     -framework Security -framework SystemConfiguration
 *
 * Run:
 *   export DYLD_LIBRARY_PATH=target/release
 *   ./examples/session_usage <project_id> <project_key>
 */

#include "libmoss.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

    printf("Moss SDK version: %s\n\n", moss_sdk_version());

    /* ── 1. Create client ─────────────────────────────────────── */

    MossClient *client = NULL;
    check(moss_client_new(project_id, project_key, &client), "client_new");
    printf("Client created.\n");

    /* ── 2. Create session ────────────────────────────────────── */

    MossSession *session = NULL;
    check(moss_client_session(client, "c-sdk-demo", NULL, &session), "session");
    printf("Session created: name=%s, doc_count=%zu\n",
           moss_session_name(session), moss_session_doc_count(session));

    /* ── 3. Add documents ─────────────────────────────────────── */

    MossMetadataEntry meta1[] = {
        { .key = "type",     .value = "billing" },
        { .key = "priority", .value = "high"    },
    };
    MossMetadataEntry meta2[] = {
        { .key = "type", .value = "gardening" },
    };

    MossDocumentInfo docs[] = {
        {
            .id             = "doc-1",
            .text           = "Customer requested a billing refund and invoice review.",
            .metadata       = meta1,
            .metadata_count = 2,
            .embedding      = NULL,
            .embedding_dim  = 0,
        },
        {
            .id             = "doc-2",
            .text           = "How to prune tomato plants in a home garden.",
            .metadata       = meta2,
            .metadata_count = 1,
            .embedding      = NULL,
            .embedding_dim  = 0,
        },
    };

    size_t added = 0, updated = 0;
    check(moss_session_add_docs(session, docs, 2, NULL, &added, &updated), "add_docs");
    printf("Added %zu, updated %zu. Total docs: %zu\n\n",
           added, updated, moss_session_doc_count(session));

    /* ── 4. Query ─────────────────────────────────────────────── */

    MossSearchResult *result = NULL;
    check(moss_session_query(session, "billing refund", NULL, &result), "query");

    printf("Query: \"%s\" — %zu results in %llu ms\n",
           result->query, result->doc_count, (unsigned long long)result->time_taken_ms);
    for (size_t i = 0; i < result->doc_count; i++) {
        MossQueryResultDoc *doc = &result->docs[i];
        printf("  [%zu] id=%s  score=%.4f  text=\"%.60s...\"\n",
               i, doc->id, doc->score, doc->text);
    }
    moss_free_search_result(result);
    printf("\n");

    /* ── 5. Query with filter ─────────────────────────────────── */

    MossQueryOptions opts = {
        .top_k       = 5,
        .alpha       = 0.8f,
        .filter_json = "{\"field\": \"type\", \"condition\": {\"$eq\": \"billing\"}}",
        .embedding     = NULL,
        .embedding_dim = 0,
    };
    MossSearchResult *filtered = NULL;
    check(moss_session_query(session, "refund", &opts, &filtered), "query_filtered");

    printf("Filtered query: \"%s\" — %zu results\n", filtered->query, filtered->doc_count);
    for (size_t i = 0; i < filtered->doc_count; i++) {
        printf("  [%zu] id=%s  score=%.4f\n",
               i, filtered->docs[i].id, filtered->docs[i].score);
    }
    moss_free_search_result(filtered);
    printf("\n");

    /* ── 6. Get documents ─────────────────────────────────────── */

    MossDocumentInfo *fetched = NULL;
    size_t fetched_count = 0;
    check(moss_session_get_docs(session, NULL, 0, &fetched, &fetched_count), "get_docs");

    printf("All docs (%zu):\n", fetched_count);
    for (size_t i = 0; i < fetched_count; i++) {
        printf("  id=%s  text=\"%.50s...\"\n", fetched[i].id, fetched[i].text);
    }
    moss_free_documents(fetched, fetched_count);
    printf("\n");

    /* ── 7. Push to cloud ─────────────────────────────────────── */

    MossPushIndexResult *push = NULL;
    check(moss_session_push_index(session, &push), "push_index");
    printf("Pushed! job_id=%s  status=%s  doc_count=%zu\n",
           push->job_id, push->status, push->doc_count);
    moss_free_push_index_result(push);

    /* ── 8. Cleanup ───────────────────────────────────────────── */

    moss_session_free(session);
    moss_client_free(client);
    printf("\nDone.\n");

    return 0;
}
