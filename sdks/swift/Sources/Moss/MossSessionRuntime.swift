import MossC
import MossRuntimeBridge

typealias MossSessionCapabilitiesFunction = @convention(c) () -> UInt64

typealias MossSessionEmbedBoundFunction = @convention(c) (
    OpaquePointer?,
    UnsafePointer<CChar>?,
    UnsafeMutablePointer<OpaquePointer?>?
) -> Int32

typealias MossSessionQueryBoundFunction = @convention(c) (
    OpaquePointer?,
    UnsafePointer<CChar>?,
    OpaquePointer?,
    UnsafePointer<MossQueryOptions>?,
    UnsafePointer<CChar>?,
    UnsafePointer<CChar>?,
    UnsafeMutablePointer<UnsafeMutablePointer<MossSearchResult>?>?
) -> Int32

typealias MossSessionBoundEmbeddingFreeFunction = @convention(c) (OpaquePointer?) -> Void

typealias MossSessionCurrentQueryFunction = @convention(c) (
    OpaquePointer?,
    UnsafePointer<CChar>?,
    UnsafePointer<MossQueryOptions>?,
    UnsafePointer<CChar>?,
    UnsafePointer<CChar>?,
    UnsafeMutablePointer<UnsafeMutablePointer<MossSearchResult>?>?
) -> Int32

typealias MossSessionQueryWithModelIdentityFunction = @convention(c) (
    OpaquePointer?,
    UnsafePointer<CChar>?,
    UnsafePointer<MossQueryOptions>?,
    UnsafePointer<CChar>?,
    UnsafePointer<CChar>?,
    UnsafePointer<CChar>?,
    UnsafePointer<CChar>?,
    UnsafePointer<CChar>?,
    UnsafeMutablePointer<UnsafeMutablePointer<MossSearchResult>?>?
) -> Int32

typealias MossSessionCurrentGetDocsFunction = @convention(c) (
    OpaquePointer?,
    UnsafePointer<UnsafePointer<CChar>?>?,
    UInt,
    UnsafePointer<CChar>?,
    UnsafePointer<CChar>?,
    Bool,
    UnsafePointer<CChar>?,
    UnsafePointer<CChar>?,
    UnsafeMutablePointer<UnsafeMutablePointer<MossDocumentInfo>?>?,
    UnsafeMutablePointer<UInt>?
) -> Int32

struct MossIdentityBoundSessionAPI: @unchecked Sendable {
    static let requiredCapabilityFlags = UInt64(MOSS_SESSION_CAPABILITY_BOUND_EMBEDDING)
        | UInt64(MOSS_SESSION_CAPABILITY_MODEL_IDENTITY_QUERY)
        | UInt64(MOSS_SESSION_CAPABILITY_CURRENT_SESSION_API)
    static let provenanceSafeCreationFlag =
        UInt64(MOSS_SESSION_CAPABILITY_PROVENANCE_SAFE_CREATION)
    let embed: MossSessionEmbedBoundFunction
    let queryBound: MossSessionQueryBoundFunction
    let freeEmbedding: MossSessionBoundEmbeddingFreeFunction
    let query: MossSessionCurrentQueryFunction
    let queryWithModelIdentity: MossSessionQueryWithModelIdentityFunction
    let getDocs: MossSessionCurrentGetDocsFunction

    static let shared: MossIdentityBoundSessionAPI? = load()

    static var capabilities: UInt64 {
        moss_runtime_bridge_session_capabilities()
    }

    static var supportsProvenanceSafeSessionCreation: Bool {
        capabilities & provenanceSafeCreationFlag
            == provenanceSafeCreationFlag
    }

    static func load() -> MossIdentityBoundSessionAPI? {
        let capabilities = Self.capabilities
        guard capabilities & requiredCapabilityFlags
            == requiredCapabilityFlags,
            let embed = moss_runtime_bridge_session_embed_query_bound(),
            let queryBound = moss_runtime_bridge_session_query_bound(),
            let freeEmbedding = moss_runtime_bridge_bound_query_embedding_free(),
            let query = moss_runtime_bridge_session_query(),
            let queryWithModelIdentity =
                moss_runtime_bridge_session_query_with_model_identity(),
            let getDocs = moss_runtime_bridge_session_get_docs()
        else {
            return nil
        }
        return MossIdentityBoundSessionAPI(
            embed: unsafeBitCast(embed, to: MossSessionEmbedBoundFunction.self),
            queryBound: unsafeBitCast(queryBound, to: MossSessionQueryBoundFunction.self),
            freeEmbedding: unsafeBitCast(
                freeEmbedding,
                to: MossSessionBoundEmbeddingFreeFunction.self
            ),
            query: unsafeBitCast(query, to: MossSessionCurrentQueryFunction.self),
            queryWithModelIdentity: unsafeBitCast(
                queryWithModelIdentity,
                to: MossSessionQueryWithModelIdentityFunction.self
            ),
            getDocs: unsafeBitCast(getDocs, to: MossSessionCurrentGetDocsFunction.self)
        )
    }
}
