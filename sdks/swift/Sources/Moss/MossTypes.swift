import Foundation

public struct QueryResult: Sendable {
    public let id: String
    public let score: Float
    public let text: String
    /// Metadata associated with the document at index time, surfaced for
    /// inspection and filtering. `nil` when the document has no metadata;
    /// values are always strings (matching the native key/value model).
    public let metadata: [String: String]?
    /// Verbatim structured payload stored at index time (e.g. JSON), returned
    /// unchanged. `nil` when the document has none. Not embedded or searched.
    public let payload: String?

    public init(
        id: String, score: Float, text: String,
        metadata: [String: String]? = nil, payload: String? = nil
    ) {
        self.id = id
        self.score = score
        self.text = text
        self.metadata = metadata
        self.payload = payload
    }

    /// Decode `payload` as a `Decodable` type. Returns `nil` when there is no payload.
    public func decodedPayload<P: Decodable>(_ type: P.Type) throws -> P? {
        guard let payload, let data = payload.data(using: .utf8) else { return nil }
        return try JSONDecoder().decode(P.self, from: data)
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
    /// Typed metadata filter (preferred). Serialized internally; when set it
    /// takes precedence over `filterJson`.
    public var filter: Filter?
    /// Optional metadata filter as a JSON string (escape hatch / legacy).
    public var filterJson: String?
    /// Collapse sibling hits sharing a parent identifier into one result per
    /// unit (assembled in `orderField` order). Session queries only.
    public var groupByParent: ParentGrouping?

    public init(
        topK: Int = 5, alpha: Float = 0.8, filter: Filter? = nil,
        filterJson: String? = nil, groupByParent: ParentGrouping? = nil
    ) {
        self.topK = topK
        self.alpha = alpha
        self.filter = filter
        self.filterJson = filterJson
        self.groupByParent = groupByParent
    }
}

/// A document stored in or returned from a Moss index.
public struct DocumentInfo: Sendable, Codable {
    public let id: String
    public let text: String
    public let metadata: [String: String]?
    public let embedding: [Float]?
    /// Verbatim structured payload (e.g. JSON), stored and returned unchanged.
    /// Not embedded or searched. Use `decodedPayload(_:)` to read it typed, or
    /// the `structured:` initializer to write a `Encodable` value.
    public let payload: String?

    public init(
        id: String, text: String, metadata: [String: String]? = nil,
        embedding: [Float]? = nil, payload: String? = nil
    ) {
        self.id = id
        self.text = text
        self.metadata = metadata
        self.embedding = embedding
        self.payload = payload
    }

    /// Store an `Encodable` value as the payload (JSON-encoded).
    public init<P: Encodable>(
        id: String, text: String, metadata: [String: String]? = nil,
        embedding: [Float]? = nil, structured: P
    ) throws {
        let data = try JSONEncoder().encode(structured)
        self.init(
            id: id, text: text, metadata: metadata, embedding: embedding,
            payload: String(data: data, encoding: .utf8)
        )
    }

    /// Decode `payload` as a `Decodable` type. Returns `nil` when there is no payload.
    public func decodedPayload<P: Decodable>(_ type: P.Type) throws -> P? {
        guard let payload, let data = payload.data(using: .utf8) else { return nil }
        return try JSONDecoder().decode(P.self, from: data)
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

// ── Deterministic (exact / "graph") retrieval ────────────────────────────────

/// A typed metadata value used in a `Filter`. Literal-expressible, so you can
/// pass `"emotion"`, `27`, `0.7`, or `false` directly.
public enum FilterValue: Sendable, Hashable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)

    /// JSON-native representation handed to the engine's filter parser.
    fileprivate var jsonValue: Any {
        switch self {
        case .string(let s): return s
        case .int(let i): return i
        case .double(let d): return d
        case .bool(let b): return b
        }
    }
}

extension FilterValue: ExpressibleByStringLiteral {
    public init(stringLiteral value: String) { self = .string(value) }
}
extension FilterValue: ExpressibleByIntegerLiteral {
    public init(integerLiteral value: Int) { self = .int(value) }
}
extension FilterValue: ExpressibleByFloatLiteral {
    public init(floatLiteral value: Double) { self = .double(value) }
}
extension FilterValue: ExpressibleByBooleanLiteral {
    public init(booleanLiteral value: Bool) { self = .bool(value) }
}

/// A composable metadata predicate. Used to filter both deterministic fetches
/// (`getDocs(where:)`) and semantic queries. Serialized internally to the
/// engine's filter format — no JSON to hand-write.
public indirect enum Filter: Sendable {
    case equals(String, FilterValue)
    case notEquals(String, FilterValue)
    case greaterThan(String, FilterValue)
    case greaterThanOrEqual(String, FilterValue)
    case lessThan(String, FilterValue)
    case lessThanOrEqual(String, FilterValue)
    case isIn(String, [FilterValue])
    case notIn(String, [FilterValue])
    case near(field: String, lat: Double, lng: Double, withinMeters: Double)
    case and([Filter])
    case or([Filter])
    /// Escape hatch: a raw engine-format filter JSON string.
    case raw(String)

    private func jsonObject() -> Any {
        func field(_ f: String, _ op: String, _ v: Any) -> [String: Any] {
            ["field": f, "condition": [op: v]]
        }
        switch self {
        case .equals(let f, let v): return field(f, "$eq", v.jsonValue)
        case .notEquals(let f, let v): return field(f, "$ne", v.jsonValue)
        case .greaterThan(let f, let v): return field(f, "$gt", v.jsonValue)
        case .greaterThanOrEqual(let f, let v): return field(f, "$gte", v.jsonValue)
        case .lessThan(let f, let v): return field(f, "$lt", v.jsonValue)
        case .lessThanOrEqual(let f, let v): return field(f, "$lte", v.jsonValue)
        case .isIn(let f, let vs): return field(f, "$in", vs.map(\.jsonValue))
        case .notIn(let f, let vs): return field(f, "$nin", vs.map(\.jsonValue))
        case .near(let f, let lat, let lng, let m):
            return field(f, "$near", "\(lat),\(lng),\(m)")
        case .and(let fs): return ["$and": fs.map { $0.jsonObject() }]
        case .or(let fs): return ["$or": fs.map { $0.jsonObject() }]
        case .raw(let s):
            return (try? JSONSerialization.jsonObject(with: Data(s.utf8))) ?? [String: Any]()
        }
    }

    /// Serialize to the engine's filter JSON. `nil` only if serialization fails.
    public func encoded() -> String? {
        guard let data = try? JSONSerialization.data(withJSONObject: jsonObject()) else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }
}

/// Collapse sibling documents that share a parent identifier into one logical
/// result. Siblings are assembled in `orderField` order (numeric-aware).
public struct ParentGrouping: Sendable {
    public var parentField: String   // e.g. "unit_id"
    public var orderField: String    // e.g. "chunk_index"

    public init(parentField: String, orderField: String) {
        self.parentField = parentField
        self.orderField = orderField
    }
}

/// Options for `MossSession.getDocs(_:)` — the deterministic, non-semantic
/// fetch path (no query vector, no similarity ranking).
public struct GetDocsOptions: Sendable {
    /// Fetch these exact ids, returned in this order. Missing ids are skipped.
    public var ids: [String]?
    /// Metadata predicate; documents matching it are returned.
    public var filter: Filter?
    /// Metadata field to order results by (numeric-aware). Ignored when `ids`
    /// already fixes the order.
    public var sortBy: String?
    /// Sort direction for `sortBy`.
    public var ascending: Bool
    /// Collapse siblings into one result per parent unit.
    public var groupByParent: ParentGrouping?

    public init(
        ids: [String]? = nil, filter: Filter? = nil, sortBy: String? = nil,
        ascending: Bool = true, groupByParent: ParentGrouping? = nil
    ) {
        self.ids = ids
        self.filter = filter
        self.sortBy = sortBy
        self.ascending = ascending
        self.groupByParent = groupByParent
    }
}
