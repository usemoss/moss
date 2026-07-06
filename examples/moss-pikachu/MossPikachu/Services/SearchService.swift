import Foundation
import Combine

@MainActor
final class SearchService: ObservableObject {
    private var mossBridge: MossBridge?
    private let fileMonitor = FileMonitor()
    private let indexManager = IndexManager()
    private var settings = UserSettings.load()
    private var policy = IndexingPolicy(settings: UserSettings.load())
    private var inaccessibleRootIDs: Set<String> = []
    private var localCacheSaveTask: Task<Void, Never>?
    private var backgroundScanTask: Task<Void, Never>?
    private var hasUnsavedLocalCache = false
    private var filesIndexedSinceLastSave = 0

    private static let memoryThrottleMB: Double = 1500
    private static let memoryThrottlePauseNs: UInt64 = 2_000_000_000

    @Published private(set) var indexedFileCount: Int = 0
    @Published private(set) var indexedChunkCount: Int = 0
    @Published private(set) var skippedFileCount: Int = 0
    @Published private(set) var lastIndexedDate: Date?
    @Published private(set) var statusMessage: String = "Not started"
    @Published private(set) var watchedFolderPathsList: [String] = []
    @Published private(set) var isIndexing: Bool = false
    @Published private(set) var discoveredFileCount: Int = 0
    @Published private(set) var queuedFileCount: Int = 0
    @Published private(set) var isReady: Bool = false
    @Published private(set) var isInitializing: Bool = false
    @Published private(set) var initializationError: String?
    @Published private(set) var sessionDocCount: Int = 0
    @Published private(set) var lastLocalCacheSaveDate: Date?
    @Published private(set) var sessionStatusMessage: String = "Session not opened"
    @Published private(set) var pythonEnvironmentStatus: String = "Not checked"
    @Published private(set) var credentialsConfigured: Bool = MossBridge.hasCredentials()
    @Published private(set) var inaccessibleFolderMessages: [String] = []

    /// True on first launch when both manifest and local cache are empty.
    var requiresBootstrapIndex: Bool {
        indexManager.indexedFileCount == 0
            && indexManager.lastIndexedDate == nil
            && !Self.localCacheExistsOnDisk()
    }

    private static func localCacheExistsOnDisk() -> Bool {
        let cacheDir = URL(fileURLWithPath: IndexingPolicy.localSessionCachePath())
            .appendingPathComponent(IndexingPolicy.sessionName, isDirectory: true)
        return FileManager.default.fileExists(atPath: cacheDir.path)
    }

    func initialize() async throws {
        isInitializing = true
        initializationError = nil
        isReady = false
        credentialsConfigured = MossBridge.hasCredentials()
        statusMessage = "Connecting to Moss..."
        AppLogger.shared.logMemory("before initSession")

        do {
            try PythonEnvironment.preflight()
            pythonEnvironmentStatus = "Python + Moss OK"
        } catch {
            let message = error.localizedDescription
            pythonEnvironmentStatus = message
            throw error
        }

        let (projectID, projectKey) = try MossBridge.loadCredentials()
        let bridge = MossBridge(projectID: projectID, projectKey: projectKey)
        try bridge.start()

        statusMessage = "Loading local search index..."
        let initResult = try await bridge.initSession(
            indexName: IndexingPolicy.sessionName,
            cachePath: IndexingPolicy.localSessionCachePath()
        )
        AppLogger.shared.logMemory("after initSession")

        let docCount = initResult.docCount
        sessionDocCount = docCount
        sessionStatusMessage = initResult.loadedFromDisk
            ? "Restored \(docCount) docs from local cache"
            : "Building local index..."
        mossBridge = bridge

        inaccessibleRootIDs = IndexingPolicy.probeFolderAccess(for: settings)
        inaccessibleFolderMessages = Self.inaccessibleMessages(for: inaccessibleRootIDs)
        policy = IndexingPolicy(settings: settings, inaccessibleRootIDs: inaccessibleRootIDs)
        fileMonitor.policy = policy
        fileMonitor.onChange = { [weak self] files in
            Task { @MainActor in
                await self?.handleFilesystemChanges(files)
            }
        }
        refreshWatchedPaths()

        indexedFileCount = indexManager.indexedFileCount
        lastIndexedDate = indexManager.lastIndexedDate

        if indexManager.scopeChanged(from: policy) {
            AppLogger.shared.log("Scope changed — clearing index for rescan")
            try? await mossBridge?.clearIndex()
            indexManager.clear()
            indexedFileCount = 0
            indexedChunkCount = 0
            sessionDocCount = 0
            hasUnsavedLocalCache = true
        }
        indexManager.updateScopeFingerprint(policy.scopeFingerprint)

        _ = fileMonitor.start()
        isReady = true
        statusMessage = docCount > 0
            ? "Ready — \(docCount) searchable docs"
            : "Indexing in background..."

        let isFirstRun = requiresBootstrapIndex || (docCount == 0 && indexManager.indexedFileCount == 0)
        let needsRehydrate = docCount == 0 && indexManager.indexedFileCount > 0
        let forceAll = isFirstRun || needsRehydrate

        backgroundScanTask?.cancel()
        backgroundScanTask = Task(priority: .utility) { [weak self] in
            await self?.performStreamingScan(forceAll: forceAll)
        }

        isInitializing = false
    }

    func shutdown() {
        fileMonitor.stop()
        backgroundScanTask?.cancel()
        localCacheSaveTask?.cancel()
        guard let mossBridge else { return }
        if hasUnsavedLocalCache {
            Task {
                _ = try? await mossBridge.saveLocalSession(cachePath: IndexingPolicy.localSessionCachePath())
                mossBridge.stop()
            }
        } else {
            mossBridge.stop()
        }
    }

    func retryInitialize() async {
        mossBridge?.stop()
        mossBridge = nil
        backgroundScanTask?.cancel()
        fileMonitor.stop()
        do {
            try await initialize()
            NotificationManager.shared.showSuccess("Picklight is ready")
        } catch {
            let message = error.localizedDescription
            markInitializationFailed(message)
            NotificationManager.shared.showError(message)
        }
    }

    func markInitializationFailed(_ message: String) {
        isInitializing = false
        isReady = false
        initializationError = message
        statusMessage = "Failed to open Moss session"
        sessionStatusMessage = message
    }

    func updateSettings(_ newSettings: UserSettings) {
        let oldFingerprint = policy.scopeFingerprint
        settings = newSettings
        inaccessibleRootIDs = IndexingPolicy.probeFolderAccess(for: settings)
        inaccessibleFolderMessages = Self.inaccessibleMessages(for: inaccessibleRootIDs)
        policy = IndexingPolicy(settings: settings, inaccessibleRootIDs: inaccessibleRootIDs)
        fileMonitor.policy = policy
        refreshWatchedPaths()

        if policy.scopeFingerprint != oldFingerprint {
            Task {
                await handleScopeChange()
            }
        }
    }

    private func handleScopeChange() async {
        try? await mossBridge?.clearIndex()
        indexManager.clear()
        indexedFileCount = 0
        indexedChunkCount = 0
        sessionDocCount = 0
        hasUnsavedLocalCache = true
        indexManager.updateScopeFingerprint(policy.scopeFingerprint)
        await performStreamingScan(forceAll: true)
    }

    func search(_ query: String) async throws -> [SearchResult] {
        guard let mossBridge else {
            throw MossBridgeError.workerCrashed
        }
        await pruneStaleEntries()
        AppLogger.shared.logMemory("before query")
        let rawResults = try await mossBridge.query(
            indexName: IndexingPolicy.sessionName,
            query: query,
            topK: 12,
            alpha: settings.searchAlpha
        )
        AppLogger.shared.logMemory("after query")

        let deduped = dedupeResultsByPath(rawResults)
        let annotated = deduped.map { annotateMissingOnDisk($0) }

        AppLogger.shared.log(
            "Query \"\(query)\" raw=\(rawResults.count) deduped=\(deduped.count) alpha=\(settings.searchAlpha)"
        )
        for result in deduped.prefix(3) {
            AppLogger.shared.log(String(format: "  [%.3f] %@", result.score, result.path))
        }

        return annotated.filter { result in
            !result.isMissingOnDisk && policy.shouldIndex(path: result.path)
        }
    }

    private func dedupeResultsByPath(_ results: [SearchResult]) -> [SearchResult] {
        var bestByPath: [String: SearchResult] = [:]
        for result in results {
            if let existing = bestByPath[result.path] {
                if result.score > existing.score {
                    bestByPath[result.path] = result
                }
            } else {
                bestByPath[result.path] = result
            }
        }
        return bestByPath.values.sorted { $0.score > $1.score }
    }

    private func annotateMissingOnDisk(_ result: SearchResult) -> SearchResult {
        let missing = !FileManager.default.fileExists(atPath: result.path)
        guard missing != result.isMissingOnDisk else { return result }
        return SearchResult(
            id: result.id,
            text: result.text,
            score: result.score,
            filename: result.filename,
            path: result.path,
            timingMs: result.timingMs,
            isMissingOnDisk: missing
        )
    }

    func reindexNow() async throws {
        guard !watchedFolderPathsList.isEmpty else {
            statusMessage = missingScopeMessage
            return
        }
        AppLogger.shared.logMemory("before manual reindex")
        await performStreamingScan(forceAll: true)
        AppLogger.shared.logMemory("after manual reindex")
    }

    func clearIndexAndRescan() async throws {
        try await mossBridge?.clearIndex()
        indexManager.clear()
        indexedFileCount = 0
        indexedChunkCount = 0
        skippedFileCount = 0
        sessionDocCount = 0
        hasUnsavedLocalCache = true
        indexManager.updateScopeFingerprint(policy.scopeFingerprint)
        AppLogger.shared.logMemory("before clear and rescan")
        await performStreamingScan(forceAll: true)
        AppLogger.shared.logMemory("after clear and rescan")
    }

    // MARK: - Private

    private var missingScopeMessage: String {
        if !inaccessibleFolderMessages.isEmpty {
            return inaccessibleFolderMessages.joined(separator: " ")
        }
        return "No indexed folders enabled. Turn on folders in Settings."
    }

    private static func inaccessibleMessages(for ids: Set<String>) -> [String] {
        ids.map { id in
            let name: String
            switch id {
            case "documents": name = "Documents"
            case "desktop": name = "Desktop"
            case "downloads": name = "Downloads"
            case "movies": name = "Movies"
            case "music": name = "Music"
            case "pictures": name = "Pictures"
            case "public": name = "Public"
            case "icloud": name = "ICloud Drive"
            default: name = id
            }
            return "Cannot access \(name) — grant access in System Settings → Privacy & Security → Files and Folders."
        }
    }

    private func refreshWatchedPaths() {
        let paths = policy.watchedFolderPaths()
        watchedFolderPathsList = paths
        fileMonitor.updateWatchedPaths(paths)
    }

    private func performStreamingScan(forceAll: Bool) async {
        let folders = policy.watchedFolderPaths()
        guard !folders.isEmpty else {
            statusMessage = missingScopeMessage
            isIndexing = false
            return
        }

        isIndexing = true
        statusMessage = forceAll ? "Scanning folders..." : "Checking for changed files..."
        discoveredFileCount = 0
        queuedFileCount = 0

        await pruneStaleEntries()

        let policySnapshot = policy
        var pendingBatch: [String] = []
        pendingBatch.reserveCapacity(IndexingPolicy.indexBatchSize)

        let stream = AsyncStream<[String]> { continuation in
            DispatchQueue.global(qos: .utility).async {
                IndexingPolicy.enumerateFileBatches(in: folders, policy: policySnapshot) { batch in
                    continuation.yield(batch)
                }
                continuation.finish()
            }
        }

        for await pathBatch in stream {
            discoveredFileCount += pathBatch.count
            let needingIndex = forceAll ? pathBatch : indexManager.filesNeedingIndex(in: pathBatch)
            for path in needingIndex {
                pendingBatch.append(path)
                if pendingBatch.count >= IndexingPolicy.indexBatchSize {
                    await flushIndexBatch(&pendingBatch)
                }
            }
        }

        if !pendingBatch.isEmpty {
            await flushIndexBatch(&pendingBatch)
        }

        indexedFileCount = indexManager.indexedFileCount
        lastIndexedDate = indexManager.lastIndexedDate
        queuedFileCount = 0
        isIndexing = false
        if sessionDocCount > 0 {
            statusMessage = "Up to date (\(indexedFileCount) files, \(sessionDocCount) docs)"
        } else if indexedFileCount > 0 {
            statusMessage = "Indexed \(indexedFileCount) files"
        } else {
            statusMessage = "No files indexed yet"
        }
    }

    private func flushIndexBatch(_ batch: inout [String]) async {
        guard !batch.isEmpty else { return }
        let toIndex = batch
        batch.removeAll(keepingCapacity: true)
        queuedFileCount += toIndex.count
        await indexFiles(toIndex)
        queuedFileCount = max(0, queuedFileCount - toIndex.count)
        await throttleIfMemoryHigh()
    }

    private func throttleIfMemoryHigh() async {
        guard let mb = AppLogger.shared.residentMemoryMB(), mb > Self.memoryThrottleMB else { return }
        AppLogger.shared.log(String(format: "Memory high (%.0f MB) — pausing briefly", mb))
        try? await Task.sleep(nanoseconds: Self.memoryThrottlePauseNs)
    }

    private func handleFilesystemChanges(_ paths: [String]) async {
        await pruneStaleEntries()

        let missingPaths = paths.filter { !FileManager.default.fileExists(atPath: $0) }
        if !missingPaths.isEmpty {
            await removeIndexedPaths(missingPaths)
        }

        let existingPaths = paths.filter { path in
            FileManager.default.fileExists(atPath: path) && policy.shouldIndex(path: path)
        }
        guard !existingPaths.isEmpty else { return }

        let needingIndex = indexManager.filesNeedingIndex(in: existingPaths)
        guard !needingIndex.isEmpty else { return }

        await indexFiles(needingIndex)
    }

    private func removeIndexedPaths(_ paths: [String]) async {
        let tracked = paths.filter { indexManager.isTracked($0) }
        guard !tracked.isEmpty else { return }
        await removeChunksForPaths(tracked)
        indexManager.removePaths(tracked)
        indexedFileCount = indexManager.indexedFileCount
        hasUnsavedLocalCache = true
        scheduleLocalCacheSave()
        AppLogger.shared.log("Removed \(tracked.count) deleted files from index")
    }

    private func removeChunksForPaths(_ paths: [String]) async {
        let idsToDelete = paths.flatMap { indexManager.chunkIDs(for: $0) }
        guard !idsToDelete.isEmpty, let mossBridge else { return }
        do {
            let docCount = try await mossBridge.deleteDocs(ids: idsToDelete)
            sessionDocCount = docCount
            hasUnsavedLocalCache = true
            sessionStatusMessage = "Local session updated"
        } catch {
            AppLogger.shared.log("Delete docs error: \(error.localizedDescription)")
        }
    }

    private func pruneStaleEntries() async {
        let stale = indexManager.stalePaths(validatingWith: policy)
        guard !stale.isEmpty else { return }

        let idsToDelete = stale.flatMap { indexManager.chunkIDs(for: $0) }
        if let mossBridge, !idsToDelete.isEmpty {
            do {
                let docCount = try await mossBridge.deleteDocs(ids: idsToDelete)
                sessionDocCount = docCount
                hasUnsavedLocalCache = true
                sessionStatusMessage = "Local session updated"
            } catch {
                AppLogger.shared.log("Prune delete error: \(error.localizedDescription)")
            }
        }
        indexManager.removePaths(stale)
        indexedFileCount = indexManager.indexedFileCount
        AppLogger.shared.log("Pruned \(stale.count) stale manifest entries")
        scheduleLocalCacheSave()
    }

    private func indexFiles(_ paths: [String]) async {
        let inScope = paths.filter { path in
            FileManager.default.fileExists(atPath: path) && policy.shouldIndex(path: path)
        }
        guard !inScope.isEmpty, let mossBridge else { return }

        let reindexing = inScope.filter { indexManager.isTracked($0) }
        if !reindexing.isEmpty {
            await removeChunksForPaths(reindexing)
        }

        isIndexing = true
        statusMessage = "Indexing \(inScope.count) files..."

        let batchSize = IndexingPolicy.indexBatchSize
        var offset = 0
        let chunksBeforeRun = indexedChunkCount
        let skippedBeforeRun = skippedFileCount

        while offset < inScope.count {
            let end = min(offset + batchSize, inScope.count)
            let batch = Array(inScope[offset..<end])
            let succeeded = await indexBatch(batch, using: mossBridge)
            if !succeeded {
                for path in batch {
                    let ok = await indexBatch([path], using: mossBridge)
                    if !ok {
                        AppLogger.shared.log("Skipping file after timeout/error: \(path)")
                        skippedFileCount += 1
                        indexedFileCount = indexManager.indexedFileCount
                        lastIndexedDate = indexManager.lastIndexedDate
                        if isQuotaOrAuthError() {
                            statusMessage = sessionStatusMessage
                            isIndexing = false
                            return
                        }
                    }
                }
            }
            statusMessage = "Indexed \(indexedFileCount) files (\(indexedChunkCount) chunks)"
            AppLogger.shared.logMemory("after index batch")
            offset = end

            filesIndexedSinceLastSave += batch.count
            if filesIndexedSinceLastSave >= IndexingPolicy.saveLocalCacheEveryFiles {
                await saveLocalCacheNow()
                filesIndexedSinceLastSave = 0
            }
            await throttleIfMemoryHigh()
        }

        let chunksAddedThisRun = indexedChunkCount - chunksBeforeRun
        let skippedThisRun = skippedFileCount - skippedBeforeRun
        if skippedThisRun > 0 && chunksAddedThisRun == 0 {
            statusMessage = "Index failed: \(skippedThisRun) files skipped, no searchable chunks"
        }
        isIndexing = false
        if chunksAddedThisRun > 0 {
            scheduleLocalCacheSave()
        }
    }

    private func isQuotaOrAuthError() -> Bool {
        guard let error = initializationError ?? Optional(sessionStatusMessage) else { return false }
        let lower = error.lowercased()
        return lower.contains("usage_limit") || lower.contains("429")
            || lower.contains("unauthorized") || lower.contains("credentials")
    }

    private func indexBatch(_ batch: [String], using mossBridge: MossBridge) async -> Bool {
        guard !batch.isEmpty else { return true }

        do {
            let result = try await mossBridge.addDocs(files: batch)
            guard !result.fileChunkCounts.isEmpty || result.chunks > 0 else {
                return result.skipped == batch.count
            }

            indexManager.markIndexed(
                paths: Array(result.fileChunkCounts.keys),
                chunkCounts: result.fileChunkCounts,
                policy: policy
            )
            indexedFileCount = indexManager.indexedFileCount
            indexedChunkCount += result.chunks
            skippedFileCount += result.skipped
            sessionDocCount = result.docCount
            hasUnsavedLocalCache = true
            sessionStatusMessage = "Local session updated"
            lastIndexedDate = indexManager.lastIndexedDate
            AppLogger.shared.log(
                "Indexed batch: \(result.filesIndexed) files, \(result.chunks) chunks, skipped \(result.skipped)"
            )
            return true
        } catch {
            let message = error.localizedDescription
            AppLogger.shared.log("Index error: \(message)")
            if message.lowercased().contains("usage_limit") || message.contains("429") {
                sessionStatusMessage = "Moss quota exceeded — search still works on cached index"
                statusMessage = sessionStatusMessage
            } else if message.lowercased().contains("credential") || message.lowercased().contains("unauthorized") {
                sessionStatusMessage = "Moss credentials invalid"
                initializationError = message
            }
            return false
        }
    }

    private func scheduleLocalCacheSave() {
        localCacheSaveTask?.cancel()
        localCacheSaveTask = Task {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            guard !Task.isCancelled else { return }
            await saveLocalCacheNow()
        }
    }

    private func saveLocalCacheNow() async {
        guard hasUnsavedLocalCache, let mossBridge else { return }
        sessionStatusMessage = "Saving local index..."
        AppLogger.shared.logMemory("before saveLocalSession")
        do {
            let localDocCount = try await mossBridge.saveLocalSession(cachePath: IndexingPolicy.localSessionCachePath())
            hasUnsavedLocalCache = false
            sessionDocCount = localDocCount
            lastLocalCacheSaveDate = Date()
            sessionStatusMessage = "Saved \(localDocCount) docs to local cache"
            AppLogger.shared.logMemory("after saveLocalSession")
        } catch {
            sessionStatusMessage = "Local save failed: \(error.localizedDescription)"
            AppLogger.shared.log(sessionStatusMessage)
        }
    }
}
