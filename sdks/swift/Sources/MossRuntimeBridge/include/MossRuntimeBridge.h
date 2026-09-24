#ifndef MOSS_RUNTIME_BRIDGE_H
#define MOSS_RUNTIME_BRIDGE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

uint64_t moss_runtime_bridge_session_capabilities(void);
typedef void (*MossRuntimeBridgeFunction)(void);
int32_t moss_runtime_bridge_client_session_v2(void *client,
                                              const char *name,
                                              const char *model_id,
                                              uint8_t vector_quantization,
                                              uint8_t skip_auto_load_on_init,
                                              void *out_session);
MossRuntimeBridgeFunction moss_runtime_bridge_session_embed_query_bound(void);
MossRuntimeBridgeFunction moss_runtime_bridge_session_query_bound(void);
MossRuntimeBridgeFunction moss_runtime_bridge_bound_query_embedding_free(void);
MossRuntimeBridgeFunction moss_runtime_bridge_session_query(void);
MossRuntimeBridgeFunction moss_runtime_bridge_session_query_with_model_identity(void);
MossRuntimeBridgeFunction moss_runtime_bridge_session_get_docs(void);

/* Multi-index API (MOSS_MULTI_INDEX_API_VERSION >= 1). These always link;
   against an older runtime the client calls return -7, counts return 0 and
   pointer accessors return NULL. */
uint8_t moss_runtime_bridge_multi_index_available(void);
int32_t moss_runtime_bridge_client_load_indexes(void *client,
                                                const char *const *names,
                                                uintptr_t count,
                                                const void *opts,
                                                void **out_result);
int32_t moss_runtime_bridge_client_unload_indexes(void *client,
                                                  const char *const *names,
                                                  uintptr_t count);
int32_t moss_runtime_bridge_client_query_multi_index(void *client,
                                                     const char *const *names,
                                                     uintptr_t count,
                                                     const char *query,
                                                     const void *opts,
                                                     void **out_result);
uintptr_t moss_runtime_bridge_load_indexes_loaded_count(const void *result);
const char *moss_runtime_bridge_load_indexes_loaded_at(const void *result, uintptr_t i);
uintptr_t moss_runtime_bridge_load_indexes_failed_count(const void *result);
const char *moss_runtime_bridge_load_indexes_failed_name_at(const void *result, uintptr_t i);
const char *moss_runtime_bridge_load_indexes_failed_error_at(const void *result, uintptr_t i);
void moss_runtime_bridge_free_load_indexes_result(void *result);
const char *moss_runtime_bridge_query_result_doc_index_name(const void *doc);

#ifdef __cplusplus
}
#endif

#endif
