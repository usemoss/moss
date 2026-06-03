import Foundation
import MossC

/// On-device session handle for a single index. Returned by
/// `MossClient.session(_:modelId:)`. All embedding runs locally with
/// the bundled litelm model; queries don't hit the network.
///
/// ```swift
/// let session = try await client.session("notes")
/// _ = try await session.addDocs([
///     DocumentInfo(id: "1", text: "first note"),
///     DocumentInfo(id: "2", text: "second note"),
/// ])
/// let result = try await session.query("first")
/// ```
///
/// The class is thread-safe: concurrent calls are serialized only at
/// the native handle level. `close()` (called automatically on deinit)
/// blocks until every in-flight call has returned before freeing the
/// native pointer, mirroring the contract in `MossClient.close()`.
public final class MossSession: @unchecked Sendable {
    private var handle: OpaquePointer?
    private var inFlight: Int = 0
    private var closed: Bool = false
    private let stateCond = NSCondition()

    /// Used by `MossClient.session(...)` only — the C API hands us a
    /// strong, transferable pointer and we take exclusive ownership.
    init(takingOwnershipOf raw: OpaquePointer) {
        self.handle = raw
    }

    deinit { close() }

    /// Free the underlying native handle. Idempotent. Blocks until all
    /// in-flight calls return so they never operate on a freed pointer.
    public func close() {
        stateCond.lock()
        if closed {
            stateCond.unlock()
            return
        }
        closed = true
        while inFlight > 0 {
            stateCond.wait()
        }
        let h = handle
        handle = nil
        stateCond.unlock()
        if let h {
            moss_session_free(h)
        }
    }

    // ── Identity ─────────────────────────────────────────────────────

    /// The index name this session was opened against.
    public var name: String {
        // Synchronously borrow — `moss_session_name` returns a pointer
        // into native-owned memory; we copy into a Swift String before
        // returning the borrow.
        guard let h = try? borrowHandle() else { return "" }
        defer { returnHandle() }
        let ptr = moss_session_name(h)
        guard let ptr else { return "" }
        return String(cString: ptr)
    }

    /// Current document count in the index.
    public var docCount: Int {
        guard let h = try? borrowHandle() else { return 0 }
        defer { returnHandle() }
        return Int(moss_session_doc_count(h))
    }

    // ── Mutations ────────────────────────────────────────────────────

    /// Add or upsert documents. Returns (added, updated) counts —
    /// `added` is rows that didn't exist before, `updated` is rows
    /// whose id collided with an existing row.
    @discardableResult
    public func addDocs(
        _ docs: [DocumentInfo],
        upsert: Bool = true
    ) async throws -> (added: Int, updated: Int) {
        try await Task.detached { [self] () throws -> (Int, Int) in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try Self.withNativeDocs(docs) { docBuf, count in
                var opts = MossAddDocsOptions(upsert: upsert)
                var added: UInt = 0
                var updated: UInt = 0
                let r = moss_session_add_docs(h, docBuf, count, &opts, &added, &updated)
                try MossClient.throwIfErr(r)
                return (Int(added), Int(updated))
            }
        }.value
    }

    /// Delete documents by id. Returns the actual count deleted —
    /// missing ids are silently ignored.
    @discardableResult
    public func deleteDocs(_ docIds: [String]) async throws -> Int {
        try await Task.detached { [self] () throws -> Int in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try withCStringArray(docIds) { ptrs in
                var deleted: UInt = 0
                let r = moss_session_delete_docs(h, ptrs, UInt(docIds.count), &deleted)
                try MossClient.throwIfErr(r)
                return Int(deleted)
            }
        }.value
    }

    /// Return documents by id. Passing nil returns all docs in the
    /// index — convenient for inspection, but expensive on large indexes.
    /// An empty array returns nothing (vs nil's "everything") so callers
    /// can distinguish "no filter" from "asked for no docs".
    public func getDocs(_ docIds: [String]? = nil) async throws -> [DocumentInfo] {
        try await Task.detached { [self] () throws -> [DocumentInfo] in
            let h = try borrowHandle()
            defer { returnHandle() }
            if let docIds {
                return try withCStringArray(docIds) { ptrs in
                    try Self.runGetDocs(h, idsPtr: ptrs, idCount: UInt(docIds.count))
                }
            }
            return try Self.runGetDocs(h, idsPtr: nil, idCount: 0)
        }.value
    }

    private static func runGetDocs(
        _ h: OpaquePointer,
        idsPtr: UnsafePointer<UnsafePointer<CChar>?>?,
        idCount: UInt
    ) throws -> [DocumentInfo] {
        var outDocs: UnsafeMutablePointer<MossDocumentInfo>?
        var outCount: UInt = 0
        let r = moss_session_get_docs(h, idsPtr, idCount, &outDocs, &outCount)
        try MossClient.throwIfErr(r)
        guard let outDocs else { return [] }
        defer { moss_free_documents(outDocs, outCount) }
        return parseDocuments(outDocs, count: outCount)
    }

    // ── Query ────────────────────────────────────────────────────────

    /// Run the on-device embedding model on `text` and return the
    /// raw 384-dim FP32 vector. Useful for two patterns:
    /// 1. Latency benches that want to time embedding vs search
    ///    separately (pair with `query(_:embedding:options:)`).
    /// 2. Querying the same input across multiple indexes without
    ///    paying the embedding cost N times.
    public func embed(_ text: String) async throws -> [Float] {
        try await Task.detached { [self] () throws -> [Float] in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try text.withCString { ctext in
                var buf = [Float](repeating: 0, count: 1024)
                var outDim: UInt = 0
                let r = buf.withUnsafeMutableBufferPointer { bp in
                    moss_session_embed_query(h, ctext, bp.baseAddress, UInt(bp.count), &outDim)
                }
                try MossClient.throwIfErr(r)
                buf.removeSubrange(Int(outDim)..<buf.count)
                return buf
            }
        }.value
    }

    public func query(
        _ q: String,
        options: QueryOptions = QueryOptions()
    ) async throws -> SearchResult {
        try await query(q, embedding: nil, options: options)
    }

    /// Search variant that takes a pre-computed embedding (typically
    /// obtained from `embed(_:)`). Bypasses the model forward pass —
    /// pure dot-product scan + top-k. The `text` parameter is still
    /// passed through to telemetry / SearchResult.query so the
    /// caller-visible result stays consistent with `query(_:)`.
    public func query(
        _ q: String,
        embedding: [Float]?,
        options: QueryOptions = QueryOptions()
    ) async throws -> SearchResult {
        let opts = options
        guard opts.topK >= 0 else {
            throw MossError(code: -2, message: "topK must be non-negative; got \(opts.topK)")
        }
        return try await Task.detached { [self] () throws -> SearchResult in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try q.withCString { cq in
                try withOptionalCString(opts.filterJson) { filter in
                    // `embedding` is captured by-ref in the closure
                    // body; need to give it a stable pointer for the
                    // lifetime of the C call. `withUnsafeBufferPointer`
                    // on an Array of Float gives us that without
                    // copying out of Swift-managed storage.
                    let result: UnsafeMutablePointer<MossSearchResult>? = try {
                        var resultLocal: UnsafeMutablePointer<MossSearchResult>?
                        // `MossResult` is emitted by cbindgen as both an
                        // enum and a typedef; Swift sees that as
                        // ambiguous. Treat the wire value as Int32 and
                        // hand it straight to `throwIfErr`.
                        let invoke: (UnsafePointer<Float>?, Int) -> Int32 = { embPtr, embLen in
                            var nativeOpts = MossQueryOptions(
                                top_k: UInt(opts.topK),
                                alpha: opts.alpha,
                                filter_json: filter,
                                embedding: embPtr,
                                embedding_dim: UInt(embLen)
                            )
                            return moss_session_query(h, cq, &nativeOpts, &resultLocal)
                        }
                        let r: Int32 = if let emb = embedding {
                            emb.withUnsafeBufferPointer { bp in invoke(bp.baseAddress, bp.count) }
                        } else {
                            invoke(nil, 0)
                        }
                        try MossClient.throwIfErr(r)
                        return resultLocal
                    }()
                    guard let result else { throw MossClient.lastError(code: -7) }
                    defer { moss_free_search_result(result) }
                    return MossClient.parseSearchResult(result.pointee)
                }
            }
        }.value
    }

    // ── Persistence ──────────────────────────────────────────────────

    /// Pull a server-side index into this session. Returns the doc count
    /// loaded (0 if the cloud has no index by that name).
    ///
    /// By default this is a one-time hydration: the session then behaves as a
    /// local one — add/delete/query don't hit the network. Pass
    /// `options.autoRefresh = true` to keep it in sync: a background task
    /// polls the cloud index every `options.pollingIntervalSeconds` and pulls
    /// newer versions in on the next `query`/`getDocs`/`docCount`. Auto-refresh
    /// pauses while the session has un-pushed local edits (`addDocs`/`deleteDocs`
    /// before a `pushIndex`), so it never clobbers local work.
    ///
    /// `options.cachePath` is ignored for sessions — use `save(toCachePath:)`
    /// for on-disk persistence.
    @discardableResult
    public func loadIndex(
        _ indexName: String,
        options: LoadIndexOptions = LoadIndexOptions()
    ) async throws -> Int {
        let opts = options
        return try await Task.detached { [self] () throws -> Int in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try indexName.withCString { cname in
                // `cachePath` is intentionally not forwarded: the native session
                // load ignores it (sessions persist via `save(toCachePath:)`),
                // so passing it would only mislead callers.
                var nativeOpts = MossLoadIndexOptions(
                    auto_refresh: opts.autoRefresh,
                    polling_interval_secs: opts.pollingIntervalSeconds,
                    cache_path: nil
                )
                var docCount: UInt = 0
                let r = moss_session_load_index(h, cname, &nativeOpts, &docCount)
                try MossClient.throwIfErr(r)
                return Int(docCount)
            }
        }.value
    }

    /// Persist this session's index to disk at `cachePath`. Writes
    /// vectors, documents, and metadata atomically so the session can
    /// be re-opened via `loadFromDisk` on the next app launch without
    /// re-embedding. Vector precision matches the `vectorQuantization`
    /// passed to `MossClient.session(_:options:)`.
    public func save(toCachePath cachePath: String) async throws {
        try await Task.detached { [self] () throws -> Void in
            let h = try borrowHandle()
            defer { returnHandle() }
            try cachePath.withCString { cpath in
                let r = moss_session_save_to_disk(h, cpath)
                try MossClient.throwIfErr(r)
            }
        }.value
    }

    /// Restore a session from a previous `save(toCachePath:)` at
    /// `cachePath`. Returns the doc count restored.
    ///
    /// Note: the session's *name* (passed to `client.session(_:)`) must
    /// match the one used at save time — it's part of the on-disk
    /// directory path.
    @discardableResult
    public func loadFromDisk(cachePath: String) async throws -> Int {
        try await Task.detached { [self] () throws -> Int in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try cachePath.withCString { cpath in
                var docCount: UInt = 0
                let r = moss_session_load_from_disk(h, cpath, &docCount)
                try MossClient.throwIfErr(r)
                return Int(docCount)
            }
        }.value
    }

    /// Push the in-memory session to the cloud as a server-side index.
    /// Returns the push job details for status tracking.
    public func pushIndex() async throws -> PushIndexResult {
        try await Task.detached { [self] () throws -> PushIndexResult in
            let h = try borrowHandle()
            defer { returnHandle() }
            var raw: UnsafeMutablePointer<MossPushIndexResult>?
            let r = moss_session_push_index(h, &raw)
            try MossClient.throwIfErr(r)
            guard let raw else { throw MossClient.lastError(code: -7) }
            defer { moss_free_push_index_result(raw) }
            let p = raw.pointee
            return PushIndexResult(
                jobId: cstr(p.job_id),
                indexName: cstr(p.index_name),
                docCount: Int(p.doc_count),
                status: cstr(p.status)
            )
        }.value
    }

    // ── Internals ────────────────────────────────────────────────────

    private func borrowHandle() throws -> OpaquePointer {
        stateCond.lock()
        defer { stateCond.unlock() }
        guard !closed, let h = handle else {
            throw MossError(code: -1, message: "MossSession already closed")
        }
        inFlight += 1
        return h
    }

    private func returnHandle() {
        stateCond.lock()
        defer { stateCond.unlock() }
        inFlight -= 1
        if inFlight == 0 {
            stateCond.broadcast()
        }
    }

    /// Wrap a `[DocumentInfo]` as a contiguous `MossDocumentInfo *`
    /// buffer for the native call, then dispose of the temporary
    /// allocations once `body` returns.
    private static func withNativeDocs<R>(
        _ docs: [DocumentInfo],
        _ body: (UnsafePointer<MossDocumentInfo>?, UInt) throws -> R
    ) throws -> R {
        if docs.isEmpty {
            return try body(nil, 0)
        }

        // Allocate one CString per id/text and one Float buffer per
        // optional embedding. Track them so we can free in any order
        // (errors thrown from `body` still hit the deferred cleanup).
        var idHolders: [UnsafeMutablePointer<CChar>] = []
        var textHolders: [UnsafeMutablePointer<CChar>] = []
        var embHolders: [UnsafeMutablePointer<Float>] = []
        var metaHolders: [UnsafeMutablePointer<MossMetadataEntry>] = []
        var metaKVHolders: [UnsafeMutablePointer<CChar>] = []

        defer {
            for p in idHolders { free(p) }
            for p in textHolders { free(p) }
            for p in embHolders { p.deallocate() }
            for p in metaHolders { p.deallocate() }
            for p in metaKVHolders { free(p) }
        }

        var native: [MossDocumentInfo] = []
        native.reserveCapacity(docs.count)

        for d in docs {
            let idPtr = strdup(d.id)!
            let textPtr = strdup(d.text)!
            idHolders.append(idPtr)
            textHolders.append(textPtr)

            var embPtr: UnsafeMutablePointer<Float>? = nil
            var embLen: UInt = 0
            if let e = d.embedding, !e.isEmpty {
                let buf = UnsafeMutablePointer<Float>.allocate(capacity: e.count)
                buf.initialize(from: e, count: e.count)
                embHolders.append(buf)
                embPtr = buf
                embLen = UInt(e.count)
            }

            var metaPtr: UnsafeMutablePointer<MossMetadataEntry>? = nil
            var metaCount: UInt = 0
            if let m = d.metadata, !m.isEmpty {
                let buf = UnsafeMutablePointer<MossMetadataEntry>.allocate(capacity: m.count)
                metaHolders.append(buf)
                var i = 0
                for (k, v) in m {
                    let kPtr = strdup(k)!
                    let vPtr = strdup(v)!
                    metaKVHolders.append(kPtr)
                    metaKVHolders.append(vPtr)
                    buf.advanced(by: i).initialize(to: MossMetadataEntry(
                        key: kPtr,
                        value: vPtr
                    ))
                    i += 1
                }
                metaPtr = buf
                metaCount = UInt(m.count)
            }

            native.append(MossDocumentInfo(
                id: idPtr,
                text: textPtr,
                metadata: metaPtr,
                metadata_count: metaCount,
                embedding: embPtr,
                embedding_dim: embLen
            ))
        }

        return try native.withUnsafeBufferPointer { buf in
            try body(buf.baseAddress, UInt(buf.count))
        }
    }

    private static func parseDocuments(
        _ ptr: UnsafeMutablePointer<MossDocumentInfo>,
        count: UInt
    ) -> [DocumentInfo] {
        let n = Int(count)
        var out: [DocumentInfo] = []
        out.reserveCapacity(n)
        for i in 0..<n {
            let d = ptr.advanced(by: i).pointee
            let metadata = MossClient.parseMetadata(
                d.metadata,
                count: d.metadata_count
            )
            var embedding: [Float]? = nil
            if let e = d.embedding, d.embedding_dim > 0 {
                embedding = Array(UnsafeBufferPointer(start: e, count: Int(d.embedding_dim)))
            }
            out.append(DocumentInfo(
                id: cstr(d.id),
                text: cstr(d.text),
                metadata: metadata,
                embedding: embedding
            ))
        }
        return out
    }
}

/// Result of pushing a local session to the cloud via
/// `MossSession.pushIndex()`. Status starts as `"queued"` and becomes
/// `"ready"` once the server-side processing job completes; poll
/// `MossClient.getJobStatus(jobId)` to track progress.
public struct PushIndexResult: Sendable {
    public let jobId: String
    public let indexName: String
    public let docCount: Int
    public let status: String
}
