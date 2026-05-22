import Foundation
import MossC

/// Idiomatic Swift wrapper for the native Moss SDK.
///
/// Construct with either a static project key or an [Authenticator].
/// All methods are `async throws` and dispatch native work onto a background
/// thread. The underlying native client is thread-safe.
///
/// ```swift
/// let client = try MossClient(projectId: "p", projectKey: "k")
/// defer { client.close() }
///
/// try await client.loadIndex("docs", options: .init(cachePath: cachePath))
/// let result = try await client.query("docs", "vector search on mobile")
/// ```
public final class MossClient: @unchecked Sendable {
    /// Opaque pointer to the native MossClient. C side uses `MossClient *`,
    /// which Swift imports as `OpaquePointer?` because the struct is opaque.
    /// Mutated only behind `handleLock`; once nil, the handle has been freed
    /// and any subsequent native-side call is rejected at the requireHandle
    /// boundary.
    private var handle: OpaquePointer?
    /// Authenticator-backed clients retain an opaque pointer to an
    /// `AuthenticatorBox` (`Unmanaged.passRetained`) as the native side's
    /// user_data. `close()` releases it once.
    private var authUserData: UnsafeMutableRawPointer?
    /// Serializes mutations to `handle` / `authUserData` so a concurrent
    /// close() can't free state out from under an in-flight operation that
    /// has already captured the handle.
    private let handleLock = NSLock()

    /// Construct a client backed by a static project key.
    public init(projectId: String, projectKey: String) throws {
        Self.ensureModelCacheDir()
        var raw: OpaquePointer?
        let r = projectId.withCString { pid in
            projectKey.withCString { pkey in
                moss_client_new(pid, pkey, &raw)
            }
        }
        try Self.throwIfErr(r)
        guard let raw else { throw Self.lastError(code: -7) }
        self.handle = raw
        self.authUserData = nil
    }

    /// Construct a client whose bearer tokens come from [authenticator].
    public init(projectId: String, authenticator: any Authenticator, baseUrl: String? = nil) throws {
        Self.ensureModelCacheDir()
        let box = AuthenticatorBox(authenticator)
        // Retain the box and pass its raw pointer as user_data. The native
        // side stores it for the client's lifetime. `close()` releases the
        // retained reference exactly once.
        let userData = Unmanaged.passRetained(box).toOpaque()

        var raw: OpaquePointer?
        let r = projectId.withCString { pid in
            withOptionalCString(baseUrl) { base in
                moss_client_new_with_authenticator(
                    pid,
                    mossSwiftAuthNotify,
                    userData,
                    base,
                    &raw
                )
            }
        }
        if r != 0 {
            // Ownership returns to us so the box is freed on the error path.
            Unmanaged<AuthenticatorBox>.fromOpaque(userData).release()
            try Self.throwIfErr(r)
        }
        guard let raw else {
            Unmanaged<AuthenticatorBox>.fromOpaque(userData).release()
            throw Self.lastError(code: -7)
        }
        self.handle = raw
        self.authUserData = userData
    }

    deinit { close() }

    /// Free the underlying native handle and any authenticator box. Idempotent.
    public func close() {
        handleLock.lock(); defer { handleLock.unlock() }
        if let h = handle {
            moss_client_free(h)
            handle = nil
        }
        if let ud = authUserData {
            Unmanaged<AuthenticatorBox>.fromOpaque(ud).release()
            authUserData = nil
        }
    }

    public static var sdkVersion: String {
        String(cString: moss_sdk_version())
    }

    /// Point the embedding-model cache at a custom directory.
    ///
    /// **You normally don't need to call this.** `MossClient` automatically
    /// caches model files under `<Library/Caches>/moss-models/` on first
    /// init, which works for almost every app.
    ///
    /// Call this only if you want a different location (e.g. a shared App
    /// Group container). Call it *before* constructing your first
    /// `MossClient`; later overrides still take effect but the default may
    /// have already been wired.
    ///
    /// Throws `MossError` if `path` is empty or not valid UTF-8.
    public static func setModelCacheDir(_ path: String) throws {
        cacheDirLock.lock(); defer { cacheDirLock.unlock() }
        let r = path.withCString { ptr in moss_set_model_cache_dir(ptr) }
        try throwIfErr(r)
        cacheDirConfigured = true
    }

    /// Auto-wires the model cache to `<Library/Caches>/moss-models/` if no
    /// caller has overridden it via `setModelCacheDir`. The native default
    /// home-directory lookup doesn't resolve inside an iOS app sandbox, so
    /// without this hook the first `loadIndex` / `query` would fail with
    /// `ErrModel`.
    private static func ensureModelCacheDir() {
        cacheDirLock.lock(); defer { cacheDirLock.unlock() }
        if cacheDirConfigured { return }
        let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)
        guard let cacheRoot = caches.first else { return }
        let dir = cacheRoot.appendingPathComponent("moss-models", isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        } catch {
            return
        }
        let r = dir.path.withCString { ptr in moss_set_model_cache_dir(ptr) }
        if r == 0 {
            cacheDirConfigured = true
        }
    }

    /// Guards `cacheDirConfigured` against races between `setModelCacheDir`
    /// (caller thread) and `ensureModelCacheDir` (any init thread).
    private static let cacheDirLock = NSLock()
    private static var cacheDirConfigured = false

    // ── Operations ───────────────────────────────────────────────────

    public func loadIndex(_ name: String, options: LoadIndexOptions = LoadIndexOptions()) async throws {
        let h = try requireHandle()
        let opts = options
        // throwIfErr must run on the same thread as the C call — moss_last_error
        // is thread-local, so reading it after the Task.detached resumption
        // would land on the wrong thread and lose the message.
        try await Task.detached { [self] in
            try name.withCString { cname in
                try withOptionalCString(opts.cachePath) { cachePath in
                    var nativeOpts = MossLoadIndexOptions(
                        auto_refresh: opts.autoRefresh,
                        polling_interval_secs: opts.pollingIntervalSeconds,
                        cache_path: cachePath
                    )
                    var info: UnsafeMutablePointer<MossIndexInfo>?
                    let r = moss_client_load_index(h, cname, &nativeOpts, &info)
                    if let info { moss_free_index_info(info) }
                    try Self.throwIfErr(r)
                }
            }
        }.value
    }

    public func unloadIndex(_ name: String) async throws {
        let h = try requireHandle()
        try await Task.detached { [self] in
            try name.withCString { cname in
                let r = moss_client_unload_index(h, cname)
                try Self.throwIfErr(r)
            }
        }.value
    }

    public func query(
        _ indexName: String,
        _ query: String,
        options: QueryOptions = QueryOptions()
    ) async throws -> SearchResult {
        let h = try requireHandle()
        let opts = options
        // Validate topK here so `UInt(opts.topK)` below doesn't trap on
        // negatives — defensive against caller error since topK is a
        // signed Int in the public API.
        guard opts.topK >= 0 else {
            throw MossError(code: -2, message: "topK must be non-negative; got \(opts.topK)")
        }
        return try await Task.detached { [self] () throws -> SearchResult in
            try indexName.withCString { iname in
                try query.withCString { q in
                    try withOptionalCString(opts.filterJson) { filter in
                        var nativeOpts = MossQueryOptions(
                            top_k: UInt(opts.topK),
                            alpha: opts.alpha,
                            filter_json: filter,
                            embedding: nil,
                            embedding_dim: 0
                        )
                        var result: UnsafeMutablePointer<MossSearchResult>?
                        let r = moss_client_query(h, iname, q, &nativeOpts, &result)
                        try Self.throwIfErr(r)
                        guard let result else { throw Self.lastError(code: -7) }
                        defer { moss_free_search_result(result) }
                        return Self.parseSearchResult(result.pointee)
                    }
                }
            }
        }.value
    }

    public func deleteIndex(_ name: String) async throws -> Bool {
        let h = try requireHandle()
        return try await Task.detached { [self] () throws -> Bool in
            try name.withCString { (cname: UnsafePointer<CChar>) throws -> Bool in
                var deleted: Bool = false
                let r = moss_client_delete_index(h, cname, &deleted)
                try Self.throwIfErr(r)
                return deleted
            }
        }.value
    }

    public func getIndex(_ name: String) async throws -> IndexInfo {
        let h = try requireHandle()
        return try await Task.detached { [self] () throws -> IndexInfo in
            try name.withCString { cname in
                var info: UnsafeMutablePointer<MossIndexInfo>?
                let r = moss_client_get_index(h, cname, &info)
                try Self.throwIfErr(r)
                guard let info else { throw Self.lastError(code: -7) }
                defer { moss_free_index_info(info) }
                return Self.parseIndexInfo(info.pointee)
            }
        }.value
    }

    public func listIndexes() async throws -> [IndexInfo] {
        let h = try requireHandle()
        return try await Task.detached { [self] () throws -> [IndexInfo] in
            var infos: UnsafeMutablePointer<MossIndexInfo>?
            var count: UInt = 0
            let r = moss_client_list_indexes(h, &infos, &count)
            try Self.throwIfErr(r)
            guard let infos else { return [] }
            defer { moss_free_index_info_list(infos, count) }
            let n = Int(count)
            var out: [IndexInfo] = []
            out.reserveCapacity(n)
            for i in 0..<n {
                out.append(Self.parseIndexInfo(infos.advanced(by: i).pointee))
            }
            return out
        }.value
    }

    public func refreshIndex(_ name: String) async throws -> RefreshResult {
        let h = try requireHandle()
        return try await Task.detached { [self] () throws -> RefreshResult in
            try name.withCString { cname in
                var result: UnsafeMutablePointer<MossRefreshResult>?
                let r = moss_client_refresh_index(h, cname, &result)
                try Self.throwIfErr(r)
                guard let result else { throw Self.lastError(code: -7) }
                defer { moss_free_refresh_result(result) }
                let p = result.pointee
                return RefreshResult(
                    indexName: cstr(p.index_name),
                    previousUpdatedAt: cstr(p.previous_updated_at),
                    newUpdatedAt: cstr(p.new_updated_at),
                    wasUpdated: p.was_updated
                )
            }
        }.value
    }

    public func getJobStatus(_ jobId: String) async throws -> JobStatus {
        let h = try requireHandle()
        return try await Task.detached { [self] () throws -> JobStatus in
            try jobId.withCString { cjob in
                var result: UnsafeMutablePointer<MossJobStatusResponse>?
                let r = moss_client_get_job_status(h, cjob, &result)
                try Self.throwIfErr(r)
                guard let result else { throw Self.lastError(code: -7) }
                defer { moss_free_job_status_response(result) }
                let p = result.pointee
                return JobStatus(
                    jobId: cstr(p.job_id),
                    status: cstr(p.status),
                    progress: p.progress,
                    currentPhase: cstrOpt(p.current_phase),
                    error: cstrOpt(p.error),
                    createdAt: cstr(p.created_at),
                    updatedAt: cstr(p.updated_at),
                    completedAt: cstrOpt(p.completed_at)
                )
            }
        }.value
    }

    public func createIndex(
        _ name: String,
        docs: [DocumentInfo],
        modelId: String? = nil
    ) async throws -> MutationResult {
        let h = try requireHandle()
        let docsJson = try Self.encodeJson(docs)
        return try await Task.detached { [self] () throws -> MutationResult in
            try name.withCString { cname in
                try docsJson.withCString { cdocs in
                    try withOptionalCString(modelId) { cmodel in
                        var out: UnsafeMutablePointer<CChar>?
                        let r = moss_client_create_index_from_json(h, cname, cdocs, cmodel, &out)
                        try Self.throwIfErr(r)
                        guard let out else { throw Self.lastError(code: -7) }
                        defer { moss_free_string(out) }
                        return try Self.decodeMutationResult(String(cString: out))
                    }
                }
            }
        }.value
    }

    public func addDocs(
        _ name: String,
        docs: [DocumentInfo],
        upsert: Bool = true
    ) async throws -> MutationResult {
        let h = try requireHandle()
        let docsJson = try Self.encodeJson(docs)
        return try await Task.detached { [self] () throws -> MutationResult in
            try name.withCString { cname in
                try docsJson.withCString { cdocs in
                    var out: UnsafeMutablePointer<CChar>?
                    let r = moss_client_add_docs_from_json(h, cname, cdocs, upsert, &out)
                    try Self.throwIfErr(r)
                    guard let out else { throw Self.lastError(code: -7) }
                    defer { moss_free_string(out) }
                    return try Self.decodeMutationResult(String(cString: out))
                }
            }
        }.value
    }

    public func getDocs(_ name: String, docIds: [String]? = nil) async throws -> [DocumentInfo] {
        let h = try requireHandle()
        let idsJson: String? = try docIds.map { try Self.encodeJson($0) }
        return try await Task.detached { [self] () throws -> [DocumentInfo] in
            try name.withCString { cname in
                try withOptionalCString(idsJson) { cids in
                    var out: UnsafeMutablePointer<CChar>?
                    let r = moss_client_get_docs_json(h, cname, cids, &out)
                    try Self.throwIfErr(r)
                    guard let out else { throw Self.lastError(code: -7) }
                    defer { moss_free_string(out) }
                    let str = String(cString: out)
                    let data = Data(str.utf8)
                    return try JSONDecoder().decode([DocumentInfo].self, from: data)
                }
            }
        }.value
    }

    /// Free reclaimable native memory in response to an OS memory-pressure
    /// signal. Wire this from `applicationDidReceiveMemoryWarning` /
    /// `UIApplication.didReceiveMemoryWarningNotification`. Returns the
    /// number of indexes that were unloaded.
    public func onMemoryPressure(_ level: MemoryPressureLevel = .critical) async throws -> Int {
        let h = try requireHandle()
        let levelRaw = level.rawValue
        return try await Task.detached { [self] () throws -> Int in
            var unloaded: Int = 0
            let r = moss_client_release_memory(h, levelRaw, &unloaded)
            try Self.throwIfErr(r)
            return unloaded
        }.value
    }

    public func deleteDocs(_ name: String, docIds: [String]) async throws -> MutationResult {
        let h = try requireHandle()
        return try await Task.detached { [self] () throws -> MutationResult in
            // Build a const-char-pointer array; the C function takes
            // `const char *const *` plus a count.
            try name.withCString { cname in
                try withCStringArray(docIds) { ptrs in
                    var result: UnsafeMutablePointer<MossMutationResult>?
                    let r = moss_client_delete_docs(h, cname, ptrs, UInt(docIds.count), &result)
                    try Self.throwIfErr(r)
                    guard let result else { throw Self.lastError(code: -7) }
                    defer { moss_free_mutation_result(result) }
                    let p = result.pointee
                    return MutationResult(
                        jobId: cstr(p.job_id),
                        indexName: cstr(p.index_name),
                        docCount: Int(p.doc_count)
                    )
                }
            }
        }.value
    }

    // ── Internals ────────────────────────────────────────────────────

    private func requireHandle() throws -> OpaquePointer {
        guard let h = handle else {
            throw MossError(code: -1, message: "MossClient already closed")
        }
        return h
    }

    /// `MossResult` is emitted as both an `enum` and a separate
    /// `typedef int32_t MossResult`, which Swift sees as ambiguous. We treat
    /// the value as a raw `Int32` and compare against the well-known OK == 0
    /// constant from the C header.
    fileprivate static func throwIfErr(_ r: Int32) throws {
        if r != 0 {
            throw lastError(code: r)
        }
    }

    fileprivate static func lastError(code: Int32) -> MossError {
        let ptr = moss_last_error()
        let msg = ptr != nil ? String(cString: ptr!) : "moss native error code \(code)"
        return MossError(code: code, message: msg)
    }

    fileprivate static func parseIndexInfo(_ i: MossIndexInfo) -> IndexInfo {
        IndexInfo(
            id: cstr(i.id),
            name: cstr(i.name),
            status: cstr(i.status),
            docCount: Int(i.doc_count),
            model: ModelRef(
                id: cstr(i.model.id),
                version: cstrOpt(i.model.version)
            ),
            version: cstrOpt(i.version),
            createdAt: cstrOpt(i.created_at),
            updatedAt: cstrOpt(i.updated_at)
        )
    }

    fileprivate static func encodeJson<T: Encodable>(_ value: T) throws -> String {
        let data = try JSONEncoder().encode(value)
        guard let s = String(data: data, encoding: .utf8) else {
            throw MossError(code: -7, message: "encoded JSON was not valid UTF-8")
        }
        return s
    }

    fileprivate static func decodeMutationResult(_ json: String) throws -> MutationResult {
        struct Wire: Decodable {
            let jobId: String
            let indexName: String
            let docCount: Int
        }
        let w = try JSONDecoder().decode(Wire.self, from: Data(json.utf8))
        return MutationResult(jobId: w.jobId, indexName: w.indexName, docCount: w.docCount)
    }

    private static func parseSearchResult(_ r: MossSearchResult) -> SearchResult {
        let count = Int(r.doc_count)
        var docs: [QueryResult] = []
        docs.reserveCapacity(count)
        if let buf = r.docs {
            for i in 0..<count {
                let d = buf.advanced(by: i).pointee
                docs.append(
                    QueryResult(
                        id: d.id.flatMap { String(cString: $0) } ?? "",
                        score: d.score,
                        text: d.text.flatMap { String(cString: $0) } ?? ""
                    )
                )
            }
        }
        return SearchResult(
            docs: docs,
            query: r.query.flatMap { String(cString: $0) } ?? "",
            timeMs: r.time_taken_ms
        )
    }
}

// ── Helpers ──────────────────────────────────────────────────────────

/// Trampoline matching `MossAuthNotifyFn` in the C header:
///   typedef void (*MossAuthNotifyFn)(uint32_t request_id, void *user_data);
///
/// Lives here (not in Authenticator.swift) because Swift's eager linker
/// emits a duplicate `@_cdecl` symbol when the function is referenced from
/// a different translation unit. Co-locating with the only caller fixes it.
@_cdecl("_moss_swift_auth_notify")
func mossSwiftAuthNotify(requestId: UInt32, userData: UnsafeMutableRawPointer?) {
    guard let userData else { return }
    let box = Unmanaged<AuthenticatorBox>.fromOpaque(userData).takeUnretainedValue()
    Task.detached {
        do {
            let token = try await box.inner.getAuthHeader()
            token.withCString { ptr in _ = moss_resolve_auth_request(requestId, ptr) }
        } catch {
            let msg = "\(error)"
            msg.withCString { ptr in _ = moss_reject_auth_request(requestId, ptr) }
        }
    }
}

/// `withCString` for an optional string. Calls `body(nil)` when the input is nil.
@inline(__always)
func withOptionalCString<R>(_ s: String?, _ body: (UnsafePointer<CChar>?) throws -> R) rethrows -> R {
    if let s {
        return try s.withCString { try body($0) }
    } else {
        return try body(nil)
    }
}

/// Build a `const char *const *` array of NUL-terminated copies of `strings`,
/// hand it to `body`, then free everything. Used for C functions that take
/// arrays of strings (e.g. `moss_client_delete_docs`).
@inline(__always)
func withCStringArray<R>(
    _ strings: [String],
    _ body: (UnsafePointer<UnsafePointer<CChar>?>) throws -> R
) rethrows -> R {
    let copies = strings.map { strdup($0) }
    defer { copies.forEach { free($0) } }
    let ptrs = UnsafeMutablePointer<UnsafePointer<CChar>?>.allocate(capacity: copies.count)
    defer { ptrs.deallocate() }
    for (i, c) in copies.enumerated() {
        ptrs[i] = UnsafePointer(c)
    }
    return try body(ptrs)
}

/// Read a (possibly NULL) `*mut c_char` into a Swift String, defaulting to empty.
@inline(__always)
func cstr(_ p: UnsafeMutablePointer<CChar>?) -> String {
    p.flatMap { String(cString: $0) } ?? ""
}

/// Read a (possibly NULL) `*mut c_char` into a Swift String?, returning nil
/// for null pointers.
@inline(__always)
func cstrOpt(_ p: UnsafeMutablePointer<CChar>?) -> String? {
    p.flatMap { String(cString: $0) }
}
