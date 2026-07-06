import Foundation

/// Central indexing policy: which roots to watch, what to exclude, and what file types to index.
nonisolated struct IndexingPolicy: Equatable, Sendable {
    nonisolated static let sessionName = "local-files"
    nonisolated static let manifestFilename = "index-manifest.json"
    nonisolated static let localSessionCacheDirectoryName = "moss-session-cache"
    nonisolated static let manifestVersion = 2
    nonisolated static let discoveryBatchSize = 50
    nonisolated static let indexBatchSize = 12
    nonisolated static let saveLocalCacheEveryFiles = 500

    nonisolated static let excludedDirectoryNames: Set<String> = [
        ".git", "node_modules", ".venv", "venv", "DerivedData", "build", "dist", "target",
        "__pycache__", ".Trash", "Caches", "Logs", "Containers"
    ]

    nonisolated static let excludedPathFragments: [String] = [
        "/.git/", "/node_modules/", "/.venv/", "/venv/",
        "/DerivedData/", "/Library/Caches/", "/Library/Logs/",
        "/Library/Containers/", "/__pycache__/"
    ]

    nonisolated static let packageSuffixes: Set<String> = [
        ".app", ".appex", ".bundle", ".framework", ".plugin", ".kext", ".pkg", ".dSYM",
        ".xcarchive", ".xcodeproj", ".playground", ".photoslibrary", ".musiclibrary"
    ]

    nonisolated let settings: UserSettings
    nonisolated let inaccessibleRootIDs: Set<String>

    nonisolated init(settings: UserSettings = .load(), inaccessibleRootIDs: Set<String> = []) {
        self.settings = settings
        self.inaccessibleRootIDs = inaccessibleRootIDs
    }

    nonisolated static func appSupportDirectory() -> URL {
        PicklightPaths.appSupportDirectory()
    }

    nonisolated static func localSessionCachePath() -> String {
        appSupportDirectory()
            .appendingPathComponent(localSessionCacheDirectoryName, isDirectory: true)
            .path
    }

    /// Stable fingerprint of enabled roots; used to detect scope changes.
    nonisolated var scopeFingerprint: String {
        resolvedRoots()
            .map { "\($0.identifier):\($0.url.path)" }
            .sorted()
            .joined(separator: "|")
    }

    nonisolated func resolvedRoots() -> [IndexingRoot] {
        Self.roots(for: settings)
            .filter { !inaccessibleRootIDs.contains($0.identifier) }
    }

    nonisolated static func roots(for settings: UserSettings) -> [IndexingRoot] {
        let home = FileManager.default.homeDirectoryForCurrentUser
        var candidates: [IndexingRoot] = []
        if settings.indexDesktop {
            candidates.append(IndexingRoot(identifier: "desktop", url: home.appendingPathComponent("Desktop", isDirectory: true)))
        }
        if settings.indexDocuments {
            candidates.append(IndexingRoot(identifier: "documents", url: home.appendingPathComponent("Documents", isDirectory: true)))
        }
        if settings.indexDownloads {
            candidates.append(IndexingRoot(identifier: "downloads", url: home.appendingPathComponent("Downloads", isDirectory: true)))
        }
        if settings.indexMovies {
            candidates.append(IndexingRoot(identifier: "movies", url: home.appendingPathComponent("Movies", isDirectory: true)))
        }
        if settings.indexMusic {
            candidates.append(IndexingRoot(identifier: "music", url: home.appendingPathComponent("Music", isDirectory: true)))
        }
        if settings.indexPictures {
            candidates.append(IndexingRoot(identifier: "pictures", url: home.appendingPathComponent("Pictures", isDirectory: true)))
        }
        if settings.indexPublic {
            candidates.append(IndexingRoot(identifier: "public", url: home.appendingPathComponent("Public", isDirectory: true)))
        }
        if settings.indexICloudDrive {
            candidates.append(IndexingRoot(
                identifier: "icloud",
                url: home.appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs", isDirectory: true)
            ))
        }
        return existingRoots(candidates)
    }

    /// All enabled roots before filtering inaccessible ones (for permission probing).
    nonisolated func allEnabledRoots() -> [IndexingRoot] {
        Self.roots(for: settings)
    }

    nonisolated private static func existingRoots(_ roots: [IndexingRoot]) -> [IndexingRoot] {
        roots.filter { root in
            var isDir: ObjCBool = false
            return FileManager.default.fileExists(atPath: root.url.path, isDirectory: &isDir) && isDir.boolValue
        }
    }

    nonisolated func watchedFolderPaths() -> [String] {
        resolvedRoots().map(\.url.path)
    }

    nonisolated func contains(path: String) -> Bool {
        let normalized = (path as NSString).standardizingPath
        return resolvedRoots().contains { root in
            let rootPath = root.url.path
            return normalized == rootPath || normalized.hasPrefix(rootPath + "/")
        }
    }

    nonisolated func rootIdentifier(for path: String) -> String? {
        let normalized = (path as NSString).standardizingPath
        for root in resolvedRoots() {
            let rootPath = root.url.path
            if normalized == rootPath || normalized.hasPrefix(rootPath + "/") {
                return root.identifier
            }
        }
        return nil
    }

    nonisolated func shouldSkipDirectory(at url: URL) -> Bool {
        let name = url.lastPathComponent
        if name.hasPrefix(".") { return true }
        if Self.excludedDirectoryNames.contains(name) { return true }
        if Self.packageSuffixes.contains(url.pathExtension.lowercased()) { return true }
        let path = url.path
        for fragment in Self.excludedPathFragments where path.contains(fragment) {
            return true
        }
        return false
    }

    nonisolated func shouldIndex(path: String) -> Bool {
        guard contains(path: path) else { return false }

        let url = URL(fileURLWithPath: path)
        let name = url.lastPathComponent
        if Self.excludedDirectoryNames.contains(name) { return false }

        for fragment in Self.excludedPathFragments where path.contains(fragment) {
            return false
        }

        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: path, isDirectory: &isDir) else {
            return true // deleted file — handled upstream
        }
        if isDir.boolValue { return false }

        return true
    }

    /// Trigger TCC prompts and detect folders macOS blocks.
    nonisolated static func probeFolderAccess(for settings: UserSettings) -> Set<String> {
        var inaccessible: Set<String> = []
        for root in roots(for: settings) {
            do {
                _ = try FileManager.default.contentsOfDirectory(
                    at: root.url,
                    includingPropertiesForKeys: [.isDirectoryKey],
                    options: [.skipsHiddenFiles]
                )
            } catch {
                inaccessible.insert(root.identifier)
            }
        }
        return inaccessible
    }

    /// Stream file paths in batches without building one giant array. Runs on a background thread.
    nonisolated static func enumerateFileBatches(
        in folders: [String],
        policy: IndexingPolicy,
        batchSize: Int = discoveryBatchSize,
        handler: ([String]) -> Void
    ) {
        var batch: [String] = []
        batch.reserveCapacity(batchSize)

        func flush() {
            guard !batch.isEmpty else { return }
            handler(batch)
            batch.removeAll(keepingCapacity: true)
        }

        for folder in folders {
            guard policy.contains(path: folder) else { continue }
            var stack = [URL(fileURLWithPath: folder)]
            while let current = stack.popLast() {
                guard let entries = try? FileManager.default.contentsOfDirectory(
                    at: current,
                    includingPropertiesForKeys: [.isRegularFileKey, .isDirectoryKey],
                    options: [.skipsHiddenFiles]
                ) else { continue }

                for entry in entries {
                    let isDirectory = (try? entry.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) ?? false
                    if isDirectory {
                        if !policy.shouldSkipDirectory(at: entry) {
                            stack.append(entry)
                        }
                        continue
                    }
                    let path = entry.path
                    guard policy.shouldIndex(path: path) else { continue }
                    batch.append(path)
                    if batch.count >= batchSize {
                        flush()
                    }
                }
            }
        }
        flush()
    }
}

nonisolated struct IndexingRoot: Equatable, Sendable {
    let identifier: String
    let url: URL

    nonisolated var displayName: String {
        switch identifier {
        case "documents": return "Documents"
        case "desktop": return "Desktop"
        case "downloads": return "Downloads"
        case "movies": return "Movies"
        case "music": return "Music"
        case "pictures": return "Pictures"
        case "public": return "Public"
        case "icloud": return "iCloud Drive"
        default: return url.lastPathComponent
        }
    }
}
