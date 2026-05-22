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

public struct LoadIndexOptions: Sendable {
    public var autoRefresh: Bool
    public var pollingIntervalSeconds: UInt64
    /// Optional sandbox path used to cache the index on disk so subsequent
    /// launches don't re-download. Pass `FileManager.default.urls(for:
    /// .documentDirectory, in: .userDomainMask).first!.path` or similar.
    public var cachePath: String?

    public init(autoRefresh: Bool = false, pollingIntervalSeconds: UInt64 = 0, cachePath: String? = nil) {
        self.autoRefresh = autoRefresh
        self.pollingIntervalSeconds = pollingIntervalSeconds
        self.cachePath = cachePath
    }
}
