import Foundation
import Combine

@MainActor
final class SearchService: ObservableObject {
    private var mossBridge: MossBridge?
    private let fileMonitor = FileMonitor()
    private let indexManager = IndexManager(manifestFilename: IndexScope.manifestFilename)
    private var settings = UserSettings.load()
    private var saveTask: Task<Void, Never>?

    @Published private(set) var indexedFileCount: Int = 0
    @Published private(set) var indexedChunkCount: Int = 0
    @Published private(set) var lastIndexedDate: Date?
    @Published private(set) var statusMessage: String = "Not started"
    @Published private(set) var watchedFolderPathsList: [String] = []
    @Published private(set) var isIndexing: Bool = false

    func initialize() async throws {
        statusMessage = "Connecting to Moss..."
        let (projectID, projectKey) = try MossBridge.loadCredentials()
        let bridge = MossBridge(projectID: projectID, projectKey: projectKey)
        try bridge.start()
        try await bridge.initSession(indexName: IndexScope.sessionName)
        mossBridge = bridge

        fileMonitor.onChange = { [weak self] files in
            Task { @MainActor in
                await self?.indexFiles(files)
            }
        }
        refreshWatchedPaths()

        guard !watchedFolderPathsList.isEmpty else {
            statusMessage = missingScopeMessage
            return
        }

        _ = fileMonitor.start()
        await performInitialScan()
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
        settings = newSettings
        refreshWatchedPaths()
    }

    func search(_ query: String) async throws -> [SearchResult] {
        guard let mossBridge else {
            throw MossBridgeError.workerCrashed
        }
        return try await mossBridge.query(indexName: IndexScope.sessionName, query: query, topK: 8)
    }

    func reindexNow() async throws {
        await performInitialScan(forceAll: true)
    }

    func clearIndexAndRescan() async throws {
        try await mossBridge?.clearIndex()
        indexManager.clear()
        indexedFileCount = 0
        indexedChunkCount = 0
        await performInitialScan(forceAll: true)
    }

    // MARK: - Private

    private var missingScopeMessage: String {
        "Folder not found: ~/Downloads/\(IndexScope.folderName)"
    }

    private func refreshWatchedPaths() {
        let paths = watchedFolderPaths()
        watchedFolderPathsList = paths
        fileMonitor.updateWatchedPaths(paths)
    }

    private func performInitialScan(forceAll: Bool = false) async {
        let folders = watchedFolderPaths()
        guard !folders.isEmpty else {
            statusMessage = missingScopeMessage
            isIndexing = false
            return
        }

        isIndexing = true
        statusMessage = "Scanning \(IndexScope.folderName)..."
        let allFiles = discoverFiles(in: folders)
        let needingIndex = forceAll ? allFiles : indexManager.filesNeedingIndex(in: allFiles)
        statusMessage = "Found \(allFiles.count) files, indexing \(needingIndex.count)..."
        guard !needingIndex.isEmpty else {
            indexedFileCount = indexManager.indexedFileCount
            lastIndexedDate = indexManager.lastIndexedDate
            statusMessage = "Up to date (\(indexedFileCount) files)"
            isIndexing = false
            return
        }
        await indexFiles(needingIndex)
        isIndexing = false
    }

    private func indexFiles(_ paths: [String]) async {
        let inScope = paths.filter { path in
            FileManager.default.fileExists(atPath: path) && IndexScope.contains(path: path)
        }
        guard !inScope.isEmpty, let mossBridge else { return }

        isIndexing = true
        statusMessage = "Indexing \(inScope.count) files..."

        let batchSize = 15
        var offset = 0
        while offset < inScope.count {
            let end = min(offset + batchSize, inScope.count)
            let batch = Array(inScope[offset..<end])
            do {
                let result = try await mossBridge.addDocs(files: batch)
                indexManager.markIndexed(paths: batch)
                indexedFileCount = indexManager.indexedFileCount
                indexedChunkCount += result.chunks
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

    private func watchedFolderPaths() -> [String] {
        guard let url = IndexScope.watchedFolderURL else { return [] }
        return [url.path]
    }

    private func discoverFiles(in folders: [String]) -> [String] {
        let allowed = FileMonitor.indexableExtensions
        var results: [String] = []
        let fm = FileManager.default

        for folder in folders {
            guard IndexScope.contains(path: folder) else { continue }
            guard let enumerator = fm.enumerator(
                at: URL(fileURLWithPath: folder),
                includingPropertiesForKeys: [.isRegularFileKey],
                options: [.skipsHiddenFiles, .skipsPackageDescendants]
            ) else {
                NotificationManager.shared.showError("Cannot access folder: \(folder)")
                continue
            }
            for case let fileURL as URL in enumerator {
                let path = fileURL.path
                if path.contains("/node_modules/") || path.contains("/.git/") { continue }
                if path.contains("/Library/Caches/") { continue }
                var isDir: ObjCBool = false
                guard fm.fileExists(atPath: path, isDirectory: &isDir), !isDir.boolValue else { continue }
                let ext = fileURL.pathExtension.lowercased()
                if allowed.contains(ext) {
                    results.append(path)
                }
            }
        }
        return results
    }
}
