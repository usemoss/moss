import Foundation
import MossC
#if canImport(UIKit)
import UIKit
#endif

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
    /// Opaque pointer to the native MossClient. Mutated only behind
    /// `stateCond`; access from outside the lock is unsafe because a
    /// concurrent `close()` could free it. Operations borrow it via
    /// `borrowHandle()` which both reads it and increments `inFlight` in
    /// a single critical section.
    private var handle: OpaquePointer?
    /// Authenticator-backed clients retain an opaque pointer to an
    /// `AuthenticatorBox` (`Unmanaged.passRetained`) as the native side's
    /// user_data. `close()` releases it once, after the in-flight count
    /// has drained.
    private var authUserData: UnsafeMutableRawPointer?
    /// Number of operations that have called `borrowHandle()` but not yet
    /// `returnHandle()`. `close()` waits on `stateCond` until this drops
    /// to zero before freeing the native handle, so an in-flight call
    /// never operates on a freed pointer.
    private var inFlight: Int = 0
    /// Once true, no new `borrowHandle()` succeeds. Set by `close()`
    /// before it begins waiting for `inFlight` to drain.
    private var closed: Bool = false
    /// Mutex + condition variable guarding `handle`, `authUserData`,
    /// `inFlight`, and `closed`. `close()` signals here when ops finish.
    private let stateCond = NSCondition()

    /// Construct a client backed by a static project key.
    ///
    /// The client automatically attaches a stable per-device telemetry
    /// identifier sourced from `UIDevice.current.identifierForVendor`,
    /// with a Keychain-persisted UUID fallback if IDFV is unavailable.
    /// The consumer doesn't supply this — it's an SDK concern, not an
    /// app concern, and keeping it inside the SDK ensures every
    /// consumer reports telemetry the same way.
    public init(projectId: String, projectKey: String) throws {
        try Self.ensureModelCacheDir()
        let did = Self.stableDeviceId()
        var raw: OpaquePointer?
        let r = projectId.withCString { pid in
            projectKey.withCString { pkey in
                did.withCString { d in
                    moss_client_new_with_device_id(pid, pkey, d, &raw)
                }
            }
        }
        try Self.throwIfErr(r)
        guard let raw else { throw Self.lastError(code: -7) }
        self.handle = raw
        self.authUserData = nil
    }

    /// Construct a client whose bearer tokens come from [authenticator].
    /// See the static-key initializer for the device-id behavior.
    public init(
        projectId: String,
        authenticator: any Authenticator,
        baseUrl: String? = nil
    ) throws {
        try Self.ensureModelCacheDir()
        let box = AuthenticatorBox(authenticator)
        // Retain the box and pass its raw pointer as user_data. The native
        // side stores it for the client's lifetime. `close()` releases the
        // retained reference exactly once.
        let userData = Unmanaged.passRetained(box).toOpaque()
        let did = Self.stableDeviceId()

        var raw: OpaquePointer?
        let r = projectId.withCString { pid in
            withOptionalCString(baseUrl) { base in
                did.withCString { d in
                    moss_client_new_with_authenticator_and_device_id(
                        pid,
                        mossSwiftAuthNotify,
                        userData,
                        base,
                        d,
                        &raw
                    )
                }
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

    /// Free the underlying native handle and any authenticator box.
    ///
    /// Idempotent. Safe to call concurrently with in-flight operations:
    /// the call blocks until every borrowed handle is returned, then
    /// frees. After `close()` returns, every further operation throws
    /// `MossError(-1, "MossClient already closed")`.
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
        let ud = authUserData
        authUserData = nil
        stateCond.unlock()

        if let h { moss_client_free(h) }
        if let ud { Unmanaged<AuthenticatorBox>.fromOpaque(ud).release() }
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
    /// a much less actionable `ErrModel`.
    private static func ensureModelCacheDir() throws {
        cacheDirLock.lock(); defer { cacheDirLock.unlock() }
        if cacheDirConfigured { return }
        guard let cacheRoot = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first else {
            throw MossError(code: -7, message: "could not locate <Library/Caches> for model cache")
        }
        let dir = cacheRoot.appendingPathComponent("moss-models", isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        } catch {
            throw MossError(code: -7, message: "could not create model cache directory at \(dir.path): \(error.localizedDescription)")
        }
        let r = dir.path.withCString { ptr in moss_set_model_cache_dir(ptr) }
        try throwIfErr(r)
        cacheDirConfigured = true
    }

    /// Guards `cacheDirConfigured` against races between `setModelCacheDir`
    /// (caller thread) and `ensureModelCacheDir` (any init thread).
    private static let cacheDirLock = NSLock()
    private static var cacheDirConfigured = false

    // ── Device-identifier helpers ────────────────────────────────────

    /// Returns a stable per-device identifier suitable for telemetry
    /// attribution. Tries `UIDevice.identifierForVendor` first (the
    /// recommended Apple-blessed mechanism; no permission prompt, no
    /// App Tracking Transparency consent required). Falls back to a
    /// UUID persisted in the Keychain if IDFV is unavailable — which
    /// is rare in practice but can happen very early in the launch
    /// sequence or in unusual restored-from-backup states.
    ///
    /// IDFV is stable for the lifetime of any app from your team on
    /// this device; the Keychain fallback is stable across reinstalls
    /// of this specific app.
    static func stableDeviceId() -> String {
        #if canImport(UIKit)
        if let idfv = UIDevice.current.identifierForVendor?.uuidString {
            return idfv
        }
        #endif
        return keychainOrCreateDeviceId()
    }

    /// Reads (or creates) a UUID stored in the Keychain under a moss-
    /// specific service+account. Used as a fallback when IDFV is nil
    /// or absent.
    private static func keychainOrCreateDeviceId() -> String {
        let service = "dev.moss.sdk"
        let account = "device_id"

        let readQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
        ]
        var item: CFTypeRef?
        if SecItemCopyMatching(readQuery as CFDictionary, &item) == errSecSuccess,
           let data = item as? Data,
           let existing = String(data: data, encoding: .utf8),
           !existing.isEmpty {
            return existing
        }

        let new = UUID().uuidString
        let writeAttrs: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: Data(new.utf8),
            // ThisDeviceOnly: the entry doesn't migrate to a new device
            // via iCloud Keychain backup. Telemetry IDs should stay
            // device-scoped — restoring to a new device should look
            // like a fresh install for attribution purposes.
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
        _ = SecItemAdd(writeAttrs as CFDictionary, nil)
        return new
    }

    // ── Operations ───────────────────────────────────────────────────

    public func loadIndex(_ name: String, options: LoadIndexOptions = LoadIndexOptions()) async throws {
        let opts = options
        try await Task.detached { [self] in
            let h = try borrowHandle()
            defer { returnHandle() }
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
        try await Task.detached { [self] in
            let h = try borrowHandle()
            defer { returnHandle() }
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
        let opts = options
        // Validate topK eagerly so the caller gets a descriptive error
        // instead of `UInt(opts.topK)` trapping on negatives.
        guard opts.topK >= 0 else {
            throw MossError(code: -2, message: "topK must be non-negative; got \(opts.topK)")
        }
        return try await Task.detached { [self] () throws -> SearchResult in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try indexName.withCString { iname in
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
        try await Task.detached { [self] () throws -> Bool in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try name.withCString { (cname: UnsafePointer<CChar>) throws -> Bool in
                var deleted: Bool = false
                let r = moss_client_delete_index(h, cname, &deleted)
                try Self.throwIfErr(r)
                return deleted
            }
        }.value
    }

    public func getIndex(_ name: String) async throws -> IndexInfo {
        try await Task.detached { [self] () throws -> IndexInfo in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try name.withCString { cname in
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
        try await Task.detached { [self] () throws -> [IndexInfo] in
            let h = try borrowHandle()
            defer { returnHandle() }
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
        try await Task.detached { [self] () throws -> RefreshResult in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try name.withCString { cname in
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
        try await Task.detached { [self] () throws -> JobStatus in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try jobId.withCString { cjob in
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
        let docsJson = try Self.encodeJson(docs)
        return try await Task.detached { [self] () throws -> MutationResult in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try name.withCString { cname in
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
        let docsJson = try Self.encodeJson(docs)
        return try await Task.detached { [self] () throws -> MutationResult in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try name.withCString { cname in
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
        let idsJson: String? = try docIds.map { try Self.encodeJson($0) }
        return try await Task.detached { [self] () throws -> [DocumentInfo] in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try name.withCString { cname in
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
        let levelRaw = level.rawValue
        return try await Task.detached { [self] () throws -> Int in
            let h = try borrowHandle()
            defer { returnHandle() }
            var unloaded: Int = 0
            // `MossMemoryPressure` is the same cbindgen-generated enum/typedef
            // pair as `MossResult` — pass the raw UInt8 value to avoid the
            // ambiguous-type lookup error.
            let r = moss_client_release_memory(h, levelRaw, &unloaded)
            try Self.throwIfErr(r)
            return unloaded
        }.value
    }

    public func deleteDocs(_ name: String, docIds: [String]) async throws -> MutationResult {
        try await Task.detached { [self] () throws -> MutationResult in
            let h = try borrowHandle()
            defer { returnHandle() }
            // Build a const-char-pointer array; the C function takes
            // `const char *const *` plus a count.
            return try name.withCString { cname in
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

    /// Open an on-device session for `name` with the given options.
    ///
    /// Sessions back the local-only flow: documents are embedded on-
    /// device with the bundled litelm model (no network round-trip),
    /// stored in an mmap'd vector store, and queried locally. Pass the
    /// returned [MossSession] to `addDocs`/`query`/etc. Call `close()`
    /// (or let it deinit) to release the native handle.
    ///
    /// `options.modelId == nil` selects the platform default
    /// (`moss-litelm` on iOS). `options.vectorQuantization` picks the
    /// on-disk vector precision used by `MossSession.save(toCachePath:)`
    /// — defaults to platform-appropriate (INT8 on iOS).
    public func session(
        _ name: String,
        options: SessionOptions = SessionOptions()
    ) async throws -> MossSession {
        let opts = options
        return try await Task.detached { [self] () throws -> MossSession in
            let h = try borrowHandle()
            defer { returnHandle() }
            return try name.withCString { cname in
                try withOptionalCString(opts.modelId) { cmodel in
                    var nativeOpts = MossSessionOptions(
                        model_id: cmodel,
                        vector_quantization: opts.vectorQuantization.rawValue,
                        // C ABI field is uint8_t: 1 = skip auto-load, 0 = keep it.
                        skip_auto_load_on_init: opts.autoLoadOnInit ? 0 : 1
                    )
                    var raw: OpaquePointer?
                    let r = moss_client_session(h, cname, &nativeOpts, &raw)
                    try Self.throwIfErr(r)
                    guard let raw else { throw Self.lastError(code: -7) }
                    return MossSession(takingOwnershipOf: raw)
                }
            }
        }.value
    }

    /// Convenience overload: open a session with just a model id.
    /// Equivalent to `session(name, options: SessionOptions(modelId: modelId))`.
    public func session(_ name: String, modelId: String?) async throws -> MossSession {
        try await session(name, options: SessionOptions(modelId: modelId))
    }

    // ── Internals ────────────────────────────────────────────────────

    /// Reserve the native handle for the duration of a single operation.
    /// Increments `inFlight` so a concurrent `close()` blocks until the
    /// matching `returnHandle()` runs. Must be paired with exactly one
    /// `returnHandle()` (use `defer`).
    private func borrowHandle() throws -> OpaquePointer {
        stateCond.lock()
        defer { stateCond.unlock() }
        guard !closed, let h = handle else {
            throw MossError(code: -1, message: "MossClient already closed")
        }
        inFlight += 1
        return h
    }

    /// Release a handle reservation taken with `borrowHandle()`. Wakes a
    /// waiting `close()` when `inFlight` drops to zero.
    private func returnHandle() {
        stateCond.lock()
        defer { stateCond.unlock() }
        inFlight -= 1
        if inFlight == 0 {
            stateCond.broadcast()
        }
    }

    /// `MossResult` is emitted by cbindgen as both an `enum` and a separate
    /// `typedef int32_t MossResult`, which Swift sees as ambiguous. We treat
    /// the value as a raw `Int32` and compare against the well-known OK == 0
    /// constant from the C header.
    static func throwIfErr(_ r: Int32) throws {
        if r != 0 {
            throw lastError(code: r)
        }
    }

    static func lastError(code: Int32) -> MossError {
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

    static func encodeJson<T: Encodable>(_ value: T) throws -> String {
        let data = try JSONEncoder().encode(value)
        guard let s = String(data: data, encoding: .utf8) else {
            throw MossError(code: -7, message: "encoded JSON was not valid UTF-8")
        }
        return s
    }

    static func decodeMutationResult(_ json: String) throws -> MutationResult {
        // The JSON-returning C entry points (moss_client_create_index_from_json,
        // moss_client_add_docs_from_json) emit MutationResult with camelCase
        // keys: { "jobId", "indexName", "docCount" }. If the native layer's
        // serialization format ever changes, the JSONDecoder call below will
        // throw with a clear "keyNotFound" error.
        struct Wire: Decodable {
            let jobId: String
            let indexName: String
            let docCount: Int
        }
        let w = try JSONDecoder().decode(Wire.self, from: Data(json.utf8))
        return MutationResult(jobId: w.jobId, indexName: w.indexName, docCount: w.docCount)
    }

    static func parseSearchResult(_ r: MossSearchResult) -> SearchResult {
        let count = Int(r.doc_count)
        var docs: [QueryResult] = []
        docs.reserveCapacity(count)
        if let buf = r.docs {
            for i in 0..<count {
                let d = buf.advanced(by: i).pointee
                docs.append(
                    QueryResult(
                        id: cstr(d.id),
                        score: d.score,
                        text: cstr(d.text),
                        metadata: parseMetadata(d.metadata, count: d.metadata_count)
                    )
                )
            }
        }
        return SearchResult(
            docs: docs,
            query: cstr(r.query),
            timeMs: r.time_taken_ms
        )
    }

    /// Decode a `MossMetadataEntry *` array into a `[String: String]`.
    /// Drops entries with NULL keys (which the native side shouldn't emit
    /// but we defend against). NULL `entries` or `count == 0` returns nil
    /// so the optional `QueryResult.metadata` is empty rather than `[:]`.
    static func parseMetadata(
        _ entries: UnsafeMutablePointer<MossMetadataEntry>?,
        count: UInt
    ) -> [String: String]? {
        guard let entries, count > 0 else { return nil }
        var out: [String: String] = [:]
        let n = Int(count)
        out.reserveCapacity(n)
        for i in 0..<n {
            let e = entries.advanced(by: i).pointee
            guard let keyPtr = e.key else { continue }
            out[String(cString: keyPtr)] = cstr(e.value)
        }
        return out.isEmpty ? nil : out
    }
}

// ── Helpers ──────────────────────────────────────────────────────────

/// Trampoline matching `MossAuthNotifyFn` in libmoss.h:
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

/// Build a `const char *const *` array of NUL-terminated UTF-8 copies of
/// `strings`, hand it to `body`, then free everything. Used for C
/// functions that take arrays of strings (e.g. `moss_client_delete_docs`).
///
/// Allocates with Swift's `UnsafeMutablePointer.allocate`, which traps on
/// failure rather than returning nil — so the produced pointer array is
/// always fully populated by the time `body` runs.
@inline(__always)
func withCStringArray<R>(
    _ strings: [String],
    _ body: (UnsafePointer<UnsafePointer<CChar>?>) throws -> R
) rethrows -> R {
    let buffers: [UnsafeMutablePointer<CChar>] = strings.map { s in
        let utf8 = Array(s.utf8)
        let buf = UnsafeMutablePointer<CChar>.allocate(capacity: utf8.count + 1)
        for (i, b) in utf8.enumerated() {
            buf[i] = CChar(bitPattern: b)
        }
        buf[utf8.count] = 0
        return buf
    }
    defer { buffers.forEach { $0.deallocate() } }
    let ptrs = UnsafeMutablePointer<UnsafePointer<CChar>?>.allocate(capacity: buffers.count)
    defer { ptrs.deallocate() }
    for (i, b) in buffers.enumerated() {
        ptrs[i] = UnsafePointer(b)
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
