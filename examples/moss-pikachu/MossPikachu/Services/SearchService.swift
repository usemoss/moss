import Foundation
import Combine

@MainActor
final class SearchService: ObservableObject {
    private var mossBridge: MossBridge?
    private let fileMonitor = FileMonitor()
    private let indexManager = IndexManager()
    private var settings = UserSettings.load()
    private var policy = IndexingPolicy()
    private var saveTask: Task<Void, Never>?

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
        mossBridge = bridge

        policy = IndexingPolicy(settings: settings)
        fileMonitor.policy = policy
        fileMonitor.onChange = { [weak self] files in
            Task { @MainActor in
                await self?.indexFiles(files)
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
        }
        indexManager.updateScopeFingerprint(policy.scopeFingerprint)

        _ = fileMonitor.start()

        let isFirstLaunch = requiresBootstrapIndex
        let needsRehydrate = docCount == 0 && indexManager.indexedFileCount > 0
        await performInitialScan(forceAll: isFirstLaunch || needsRehydrate)
        isReady = true
    }

    func shutdown() {
        fileMonitor.stop()
        if settings.mossCloudSync {
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
        return try await mossBridge.query(indexName: IndexingPolicy.sessionName, query: query, topK: 8)
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
        indexManager.updateScopeFingerprint(policy.scopeFingerprint)
        await performInitialScan(forceAll: true)
    }

    // MARK: - Private

    private var missingScopeMessage: String {
        "No indexed folders found. Enable Documents, Desktop, Downloads, or iCloud Drive in Settings."
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

    private func pruneStaleEntries() async {
        let stale = indexManager.stalePaths(validatingWith: policy)
        guard !stale.isEmpty else { return }

        let idsToDelete = stale.flatMap { indexManager.chunkIDs(for: $0) }
        if let mossBridge, !idsToDelete.isEmpty {
            try? await mossBridge.deleteDocs(ids: idsToDelete)
        }
        indexManager.removePaths(stale)
        indexedFileCount = indexManager.indexedFileCount
        AppLogger.shared.log("Pruned \(stale.count) stale manifest entries")
    }

    private func indexFiles(_ paths: [String]) async {
        let inScope = paths.filter { path in
            FileManager.default.fileExists(atPath: path) && policy.shouldIndex(path: path)
        }
        guard !inScope.isEmpty, let mossBridge else { return }

        isIndexing = true
        statusMessage = "Indexing \(inScope.count) files..."
        queuedFileCount = inScope.count

        let batchSize = 15
        var offset = 0
        var batchChunkCounts: [String: Int] = [:]

        while offset < inScope.count {
            let end = min(offset + batchSize, inScope.count)
            let batch = Array(inScope[offset..<end])
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
                lastIndexedDate = indexManager.lastIndexedDate
                statusMessage = "Indexed \(indexedFileCount) files (\(indexedChunkCount) chunks)"
                AppLogger.shared.log(
                    "Indexed batch: \(result.filesIndexed) files, \(result.chunks) chunks, skipped \(result.skipped)"
                )
            } catch {
                AppLogger.shared.log("Index error: \(error.localizedDescription)")
                NotificationManager.shared.showError(error.localizedDescription)
            }
            offset = end
        }

        isIndexing = false
        queuedFileCount = 0
        scheduleSave()
    }

    private func scheduleSave() {
        saveTask?.cancel()
        saveTask = Task {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            guard !Task.isCancelled, settings.mossCloudSync else { return }
            try? await mossBridge?.pushIndex()
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
