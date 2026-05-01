/**
 * metadata_filtering.c: Metadata filtering example for the Moss C SDK.
 *
 * Demonstrates: $eq, $and, $in, and $near filter operators
 * on a cloud index loaded locally.
 *
 * See README.md for setup. After extracting the libmoss release archive
 * so that include/ and lib/ sit next to this file:
 *
 * Build (macOS):
 *   clang metadata_filtering.c -o metadata_filtering \
 *     -Iinclude -Llib -lmoss \
 *     -framework Security -framework SystemConfiguration
 *
 * Run:
 *   DYLD_LIBRARY_PATH=lib ./metadata_filtering <project_id> <project_key>
 */

#include "libmoss.h"
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static void check(MossResult r, const char *context) {
    if (r != OK) {
        const char *err = moss_last_error();
        fprintf(stderr, "ERROR [%s]: %s\n", context, err ? err : "(no details)");
        exit(1);
    }
}

static void print_results(MossSearchResult *res) {
    for (size_t i = 0; i < res->doc_count; i++) {
        MossQueryResultDoc *doc = &res->docs[i];
        printf("   - %s | score=%.3f", doc->id, doc->score);
        if (doc->metadata_count > 0) {
            printf(" | metadata={");
            for (size_t j = 0; j < doc->metadata_count; j++) {
                if (j > 0) printf(", ");
                printf("%s: %s", doc->metadata[j].key, doc->metadata[j].value);
            }
            printf("}");
        }
        printf("\n");
    }
}

int main(int argc, char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <project_id> <project_key>\n", argv[0]);
        return 1;
    }

    const char *project_id  = argv[1];
    const char *project_key = argv[2];

    printf("Moss Metadata Filtering Sample (C)\n\n");

    MossClient *client = NULL;
    check(moss_client_new(project_id, project_key, &client), "client_new");

    /* ── Build unique index name ──────────────────────────────── */

    char index_name[64];
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    snprintf(index_name, sizeof(index_name),
             "metadata-filter-sample-%04d%02d%02d-%02d%02d%02d",
             t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
             t->tm_hour, t->tm_min, t->tm_sec);

    /* ── Documents ────────────────────────────────────────────── */

    MossMetadataEntry meta1[] = {
        { .key = "category", .value = "shoes" },
        { .key = "brand",    .value = "swiftfit" },
        { .key = "price",    .value = "79" },
        { .key = "city",     .value = "new-york" },
        { .key = "location", .value = "40.7580,-73.9855" },
    };
    MossMetadataEntry meta2[] = {
        { .key = "category", .value = "shoes" },
        { .key = "brand",    .value = "peakstride" },
        { .key = "price",    .value = "149" },
        { .key = "city",     .value = "seattle" },
        { .key = "location", .value = "47.6062,-122.3321" },
    };
    MossMetadataEntry meta3[] = {
        { .key = "category", .value = "bags" },
        { .key = "brand",    .value = "urbanpack" },
        { .key = "price",    .value = "95" },
        { .key = "city",     .value = "new-york" },
        { .key = "location", .value = "40.7505,-73.9934" },
    };

    MossDocumentInfo docs[] = {
        {
            .id = "doc1",
            .text = "Running shoes with breathable mesh for daily training.",
            .metadata = meta1, .metadata_count = 5,
        },
        {
            .id = "doc2",
            .text = "Trail running shoes built for rocky mountain terrain.",
            .metadata = meta2, .metadata_count = 5,
        },
        {
            .id = "doc3",
            .text = "Lightweight city backpack with laptop compartment.",
            .metadata = meta3, .metadata_count = 5,
        },
    };

    /* ── 1. Create index ──────────────────────────────────────── */

    printf("1. Creating index...\n");
    MossMutationResult *cr = NULL;
    check(moss_client_create_index(client, index_name, docs, 3, NULL, &cr), "create_index");
    moss_free_mutation_result(cr);

    /* ── 2. Load index locally (required for filtering) ───────── */

    printf("2. Loading index locally (required for filtering)...\n");
    MossIndexInfo *loaded = NULL;
    check(moss_client_load_index(client, index_name, NULL, &loaded), "load_index");
    moss_free_index_info(loaded);

    /* ── 3. $eq filter: category == shoes ─────────────────────── */

    printf("\n3. $eq filter: category == shoes\n");
    MossQueryOptions eq_opts = {
        .top_k       = 5,
        .alpha       = 0.5f,
        .filter_json = "{\"field\": \"category\", \"condition\": {\"$eq\": \"shoes\"}}",
    };
    MossSearchResult *eq_res = NULL;
    check(moss_client_query(client, index_name, "running gear", &eq_opts, &eq_res), "query_eq");
    print_results(eq_res);
    moss_free_search_result(eq_res);

    /* ── 4. $and filter: shoes AND price < 100 ────────────────── */

    printf("\n4. $and filter: shoes and price < 100\n");
    MossQueryOptions and_opts = {
        .top_k       = 5,
        .alpha       = 0.6f,
        .filter_json = "{\"$and\": ["
                        "{\"field\": \"category\", \"condition\": {\"$eq\": \"shoes\"}},"
                        "{\"field\": \"price\", \"condition\": {\"$lt\": \"100\"}}"
                       "]}",
    };
    MossSearchResult *and_res = NULL;
    check(moss_client_query(client, index_name, "running shoes", &and_opts, &and_res), "query_and");
    print_results(and_res);
    moss_free_search_result(and_res);

    /* ── 5. $in filter: city in [new-york] ────────────────────── */

    printf("\n5. $in filter: city in [new-york]\n");
    MossQueryOptions in_opts = {
        .top_k       = 5,
        .filter_json = "{\"field\": \"city\", \"condition\": {\"$in\": [\"new-york\"]}}",
    };
    MossSearchResult *in_res = NULL;
    check(moss_client_query(client, index_name, "city essentials", &in_opts, &in_res), "query_in");
    print_results(in_res);
    moss_free_search_result(in_res);

    /* ── 6. $near filter: within 5km of Times Square ──────────── */

    printf("\n6. $near filter: within 5km of Times Square\n");
    MossQueryOptions near_opts = {
        .top_k       = 5,
        .filter_json = "{\"field\": \"location\", \"condition\": {\"$near\": \"40.7580,-73.9855,5000\"}}",
    };
    MossSearchResult *near_res = NULL;
    check(moss_client_query(client, index_name, "city products", &near_opts, &near_res), "query_near");
    print_results(near_res);
    moss_free_search_result(near_res);

    printf("\nMetadata filtering sample completed.\n");

    /* ── 7. Cleanup ───────────────────────────────────────────── */

    printf("\n7. Cleaning up index...\n");
    bool deleted = false;
    check(moss_client_delete_index(client, index_name, &deleted), "delete_index");

    moss_client_free(client);
    return 0;
}
