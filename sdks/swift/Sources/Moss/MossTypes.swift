import Foundation

public struct QueryResult: Sendable {
    public let id: String
    public let score: Float
    public let text: String
    /// Metadata associated with the document at index time, surfaced for
    /// inspection and filtering. `nil` when the document has no metadata;
    /// values are always strings (matching the native key/value model).
    public let metadata: [String: String]?

    public init(id: String, score: Float, text: String, metadata: [String: String]? = nil) {
        self.id = id
        self.score = score
        self.text = text
        self.metadata = metadata
    }
}

public struct SearchResult: Sendable {
    public let docs: [QueryResult]
    public let query: String
    public let timeMs: UInt64
}

public struct QueryOptions: Sendable {
    public var topK: Int
    /// Hybrid weight between dense (1.0) and sparse (0.0) scores.
    public var alpha: Float
    /// Optional metadata filter as a JSON string.
    public var filterJson: String?

    public init(topK: Int = 5, alpha: Float = 0.8, filterJson: String? = nil) {
        self.topK = topK
        self.alpha = alpha
        self.filterJson = filterJson
    }
}

/// A document stored in or returned from a Moss index.
public struct DocumentInfo: Sendable, Codable {
    public let id: String
    public let text: String
    public let metadata: [String: String]?
    public let embedding: [Float]?

    public init(id: String, text: String, metadata: [String: String]? = nil, embedding: [Float]? = nil) {
        self.id = id
        self.text = text
        self.metadata = metadata
        self.embedding = embedding
    }
}

/// Levels reported by the host OS when memory is constrained.
public enum MemoryPressureLevel: UInt8, Sendable {
    /// Hint: drop hot caches.
    case low = 0
    /// Drop everything reclaimable; persisted on-disk caches are kept.
    case critical = 1
}

public struct ModelRef: Sendable {
    public let id: String
    public let version: String?
}

public struct IndexInfo: Sendable {
    public let id: String
    public let name: String
    public let status: String
    public let docCount: Int
    public let model: ModelRef
    public let version: String?
    public let createdAt: String?
    public let updatedAt: String?
}

public struct RefreshResult: Sendable {
    public let indexName: String
    public let previousUpdatedAt: String
    public let newUpdatedAt: String
    public let wasUpdated: Bool
}

public struct MutationResult: Sendable {
    public let jobId: String
    public let indexName: String
    public let docCount: Int
}

public struct JobStatus: Sendable {
    public let jobId: String
    public let status: String
    public let progress: Double
    public let currentPhase: String?
    public let error: String?
    public let createdAt: String
    public let updatedAt: String
    public let completedAt: String?
}

/// On-disk vector precision picked at session creation; used by
/// `MossSession.save(toCachePath:)`. Orthogonal to the embedding model
/// — pick `int8` for the smallest `.mossvec` files (~4× smaller than
/// FP32, sub-1% recall hit on MiniLM-family vectors), `fp32` to force
/// the historical lossless format, or leave at `.default` to get
/// the platform-appropriate value (INT8 on iOS, FP32 elsewhere).
///
/// Raw wire values match the C ABI: 0 = default, 1 = fp32, 2 = int8.
public enum VectorQuantization: UInt8, Sendable {
    case `default` = 0
    case fp32 = 1
    case int8 = 2
}

/// Options bag for `MossClient.session(_:options:)`.
public struct SessionOptions: Sendable {
    /// Embedding model id. `nil` = platform default (`moss-litelm` on
    /// iOS, `moss-minilm` elsewhere). Pass `"custom"` to skip on-device
    /// embedding and supply embeddings via `DocumentInfo.embedding`.
    public var modelId: String?
    /// On-disk vector precision used by `MossSession.save(toCachePath:)`.
    public var vectorQuantization: VectorQuantization

    public init(modelId: String? = nil, vectorQuantization: VectorQuantization = .default) {
        self.modelId = modelId
        self.vectorQuantization = vectorQuantization
    }
}

public struct LoadIndexOptions: Sendable {
    /// Keep the loaded index in sync by polling the cloud in the background.
    public var autoRefresh: Bool
    /// How often the auto-refresh poll runs, in seconds (only used when
    /// `autoRefresh` is true). Defaults to 600 (10 minutes); the engine clamps
    /// values below 1 to 1, so leave it at the default rather than passing 0.
    public var pollingIntervalSeconds: UInt64
    /// Optional sandbox path used to cache the index on disk so subsequent
    /// launches don't re-download. Applies to `MossClient.loadIndex`; sessions
    /// persist via `MossSession.save(toCachePath:)` instead. Pass
    /// `FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!.path`
    /// or similar.
    public var cachePath: String?

    public init(autoRefresh: Bool = false, pollingIntervalSeconds: UInt64 = 600, cachePath: String? = nil) {
        self.autoRefresh = autoRefresh
        self.pollingIntervalSeconds = pollingIntervalSeconds
        self.cachePath = cachePath
    }
}
