import Foundation
import Combine

@MainActor
final class SearchService: ObservableObject {
    private var mossBridge: MossBridge?
    private let fileMonitor = FileMonitor()
    private let indexManager = IndexManager()
    private var settings = UserSettings.load()
    private var policy = IndexingPolicy()
    private var sessionPushTask: Task<Void, Never>?
    private var hasUnpushedSessionChanges = false

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
    @Published private(set) var sessionDocCount: Int = 0
    @Published private(set) var lastSessionPushDate: Date?
    @Published private(set) var sessionStatusMessage: String = "Session not opened"

    /// True when the app has never completed an initial full index.
    var requiresBootstrapIndex: Bool {
        indexManager.indexedFileCount == 0 && indexManager.lastIndexedDate == nil
    }

    func initialize() async throws {
        statusMessage = "Connecting to Moss..."
        let (projectID, projectKey) = try MossBridge.loadCredentials()
        let bridge = MossBridge(projectID: projectID, projectKey: projectKey)
        try bridge.start()
        let docCount = try await bridge.initSession(indexName: IndexingPolicy.sessionName)
        sessionDocCount = docCount
        sessionStatusMessage = docCount > 0
            ? "Resumed \(docCount) docs from Moss session"
            : "Opened \(IndexingPolicy.sessionName) session"
        mossBridge = bridge

        policy = IndexingPolicy(settings: settings)
        fileMonitor.policy = policy
        fileMonitor.onChange = { [weak self] files in
            Task { @MainActor in
                await self?.handleFilesystemChanges(files)
            }
        }
        refreshWatchedPaths()

        guard !watchedFolderPathsList.isEmpty else {
            statusMessage = missingScopeMessage
            isReady = true
            return
        }

        if indexManager.scopeChanged(from: policy) {
            AppLogger.shared.log("Scope changed — clearing index for rescan")
            try? await mossBridge?.clearIndex()
            indexManager.clear()
            indexedFileCount = 0
            indexedChunkCount = 0
            sessionDocCount = 0
            hasUnpushedSessionChanges = true
        }
        indexManager.updateScopeFingerprint(policy.scopeFingerprint)

        let isFirstLaunch = requiresBootstrapIndex
        if isFirstLaunch && docCount > 0 {
            AppLogger.shared.log("Fresh local manifest with existing Moss session — clearing remote session for current scope")
            try? await mossBridge?.clearIndex()
            sessionDocCount = 0
            sessionStatusMessage = "Reset Moss session for current scope"
            hasUnpushedSessionChanges = true
        }

        _ = fileMonitor.start()

        let needsRehydrate = docCount == 0 && indexManager.indexedFileCount > 0
        await performInitialScan(forceAll: isFirstLaunch || needsRehydrate)
        isReady = true
    }

    func shutdown() {
        fileMonitor.stop()
        if hasUnpushedSessionChanges || indexedFileCount > 0 {
            Task {
                try? await mossBridge?.pushIndex()
            }
        }
        mossBridge?.stop()
    }

    func updateSettings(_ newSettings: UserSettings) {
        let oldFingerprint = policy.scopeFingerprint
        settings = newSettings
        policy = IndexingPolicy(settings: settings)
        fileMonitor.policy = policy
        refreshWatchedPaths()

        if policy.scopeFingerprint != oldFingerprint {
            Task {
                await handleScopeChange()
            }
        }
    }

    func search(_ query: String) async throws -> [SearchResult] {
        guard let mossBridge else {
            throw MossBridgeError.workerCrashed
        }
        await pruneStaleEntries()
        let results = try await mossBridge.query(indexName: IndexingPolicy.sessionName, query: query, topK: 8)
        return results.filter { result in
            FileManager.default.fileExists(atPath: result.path) && policy.shouldIndex(path: result.path)
        }
    }

    func reindexNow() async throws {
        await performInitialScan(forceAll: true)
    }

    func clearIndexAndRescan() async throws {
        try await mossBridge?.clearIndex()
        indexManager.clear()
        indexedFileCount = 0
        indexedChunkCount = 0
        skippedFileCount = 0
        sessionDocCount = 0
        hasUnpushedSessionChanges = true
        indexManager.updateScopeFingerprint(policy.scopeFingerprint)
        await performInitialScan(forceAll: true)
    }

    // MARK: - Private

    private var missingScopeMessage: String {
        "No enabled folders found for indexing."
    }

    private func refreshWatchedPaths() {
        let paths = policy.watchedFolderPaths()
        watchedFolderPathsList = paths
        fileMonitor.updateWatchedPaths(paths)
    }

    private func handleScopeChange() async {
        try? await mossBridge?.clearIndex()
        indexManager.clear()
        indexedFileCount = 0
        indexedChunkCount = 0
        sessionDocCount = 0
        hasUnpushedSessionChanges = true
        indexManager.updateScopeFingerprint(policy.scopeFingerprint)
        await performInitialScan(forceAll: true)
    }

    private func performInitialScan(forceAll: Bool = false) async {
        let folders = policy.watchedFolderPaths()
        guard !folders.isEmpty else {
            statusMessage = missingScopeMessage
            isIndexing = false
            return
        }

        isIndexing = true
        statusMessage = "Scanning folders..."
        await pruneStaleEntries()

        let allFiles = await discoverFiles(in: folders)
        discoveredFileCount = allFiles.count
        let needingIndex = forceAll ? allFiles : indexManager.filesNeedingIndex(in: allFiles)
        queuedFileCount = needingIndex.count

        if needingIndex.isEmpty {
            indexedFileCount = indexManager.indexedFileCount
            lastIndexedDate = indexManager.lastIndexedDate
            statusMessage = "Up to date (\(indexedFileCount) files)"
            isIndexing = false
            return
        }

        statusMessage = "Found \(allFiles.count) files, indexing \(needingIndex.count)..."
        await indexFiles(needingIndex)
        isIndexing = false
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
        hasUnpushedSessionChanges = true
        scheduleSessionPush()
        AppLogger.shared.log("Removed \(tracked.count) deleted files from index")
    }

    private func removeChunksForPaths(_ paths: [String]) async {
        let idsToDelete = paths.flatMap { indexManager.chunkIDs(for: $0) }
        guard !idsToDelete.isEmpty, let mossBridge else { return }
        do {
            let docCount = try await mossBridge.deleteDocs(ids: idsToDelete)
            sessionDocCount = docCount
            hasUnpushedSessionChanges = true
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
                hasUnpushedSessionChanges = true
                sessionStatusMessage = "Local session updated"
            } catch {
                AppLogger.shared.log("Prune delete error: \(error.localizedDescription)")
            }
        }
        indexManager.removePaths(stale)
        indexedFileCount = indexManager.indexedFileCount
        AppLogger.shared.log("Pruned \(stale.count) stale manifest entries")
        scheduleSessionPush()
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
        queuedFileCount = inScope.count

        let batchSize = 15
        var offset = 0

        while offset < inScope.count {
            let end = min(offset + batchSize, inScope.count)
            let batch = Array(inScope[offset..<end])
            let succeeded = await indexBatch(batch, using: mossBridge)
            if !succeeded {
                // Batch hung or failed — retry files one at a time and skip poison files.
                for path in batch {
                    let ok = await indexBatch([path], using: mossBridge)
                    if !ok {
                        AppLogger.shared.log("Skipping file after timeout/error: \(path)")
                        indexManager.markIndexed(paths: [path], chunkCounts: [path: 0], policy: policy)
                        skippedFileCount += 1
                        indexedFileCount = indexManager.indexedFileCount
                        lastIndexedDate = indexManager.lastIndexedDate
                    }
                }
            }
            queuedFileCount = max(0, inScope.count - end)
            statusMessage = "Indexed \(indexedFileCount) files (\(indexedChunkCount) chunks)"
            offset = end
        }

        isIndexing = false
        queuedFileCount = 0
        scheduleSessionPush()
    }

    /// Returns false when the worker times out or errors so the caller can skip poison files.
    private func indexBatch(_ batch: [String], using mossBridge: MossBridge) async -> Bool {
        var batchChunkCounts: [String: Int] = [:]
        do {
            let result = try await mossBridge.addDocs(files: batch)
            let perFileChunks = batch.isEmpty ? 0 : max(1, result.chunks / batch.count)
            for path in batch {
                batchChunkCounts[path] = perFileChunks
            }
            indexManager.markIndexed(paths: batch, chunkCounts: batchChunkCounts, policy: policy)
            indexedFileCount = indexManager.indexedFileCount
            indexedChunkCount += result.chunks
            skippedFileCount += result.skipped
            sessionDocCount = result.docCount
            hasUnpushedSessionChanges = true
            sessionStatusMessage = "Local session updated"
            lastIndexedDate = indexManager.lastIndexedDate
            AppLogger.shared.log(
                "Indexed batch: \(result.filesIndexed) files, \(result.chunks) chunks, skipped \(result.skipped)"
            )
            return true
        } catch {
            AppLogger.shared.log("Index error: \(error.localizedDescription)")
            return false
        }
    }

    private func scheduleSessionPush() {
        sessionPushTask?.cancel()
        sessionPushTask = Task {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            guard !Task.isCancelled else { return }
            await pushSessionIfNeeded()
        }
    }

    private func pushSessionIfNeeded() async {
        guard hasUnpushedSessionChanges, let mossBridge else { return }
        sessionStatusMessage = "Storing Moss session..."
        do {
            let result = try await mossBridge.pushIndex()
            hasUnpushedSessionChanges = false
            sessionDocCount = result.docCount
            lastSessionPushDate = Date()
            sessionStatusMessage = "Stored \(result.docCount) docs in Moss session"
            if let jobID = result.jobID {
                AppLogger.shared.log("Pushed Moss session job: \(jobID)")
            }
        } catch {
            sessionStatusMessage = "Session storage failed: \(error.localizedDescription)"
            AppLogger.shared.log(sessionStatusMessage)
        }
    }

    private func discoverFiles(in folders: [String]) async -> [String] {
        let settingsSnapshot = settings
        let inaccessible = folders.filter { folder in
            !FileManager.default.fileExists(atPath: folder)
        }
        for folder in inaccessible {
            NotificationManager.shared.showError("Cannot access folder: \(folder)")
        }

        return await Task.detached(priority: .utility) {
            IndexingPolicy.discoverFiles(in: folders, settings: settingsSnapshot)
        }.value
    }
}
