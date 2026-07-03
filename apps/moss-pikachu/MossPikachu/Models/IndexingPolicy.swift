import Foundation

/// Central indexing policy: which roots to watch, what to exclude, and what file types to index.
nonisolated struct IndexingPolicy: Equatable, Sendable {
    nonisolated static let sessionName = "local-files"
    nonisolated static let manifestFilename = "index-manifest-local-files.json"
    nonisolated static let manifestVersion = 2
    nonisolated static let maxFileBytes: Int64 = 50 * 1024 * 1024 // 50 MB

    nonisolated static let indexableExtensions: Set<String> = ["md", "txt", "rtf", "html", "pdf", "docx"]

    nonisolated static let excludedDirectoryNames: Set<String> = [
        ".git", "node_modules", ".venv", "venv", "DerivedData", "build", "dist", "target",
        "__pycache__", ".Trash", "Caches", "Logs", "Containers"
    ]

    nonisolated static let excludedPathFragments: [String] = [
        "/.git/", "/node_modules/", "/.venv/", "/venv/",
        "/DerivedData/", "/Library/Caches/", "/Library/Logs/",
        "/Library/Containers/", "/__pycache__/"
    ]

    nonisolated let settings: UserSettings

    nonisolated init(settings: UserSettings = .load()) {
        self.settings = settings
    }

    /// Stable fingerprint of enabled roots; used to detect scope changes.
    nonisolated var scopeFingerprint: String {
        resolvedRoots()
            .map { "\($0.identifier):\($0.url.path)" }
            .sorted()
            .joined(separator: "|")
    }

    /// Resolved watch roots that exist on disk.
    nonisolated func resolvedRoots() -> [IndexingRoot] {
        var roots: [IndexingRoot] = []
        let home = FileManager.default.homeDirectoryForCurrentUser

        if settings.indexDocuments {
            roots.append(IndexingRoot(identifier: "documents", url: home.appendingPathComponent("Documents", isDirectory: true)))
        }
        if settings.indexDesktop {
            roots.append(IndexingRoot(identifier: "desktop", url: home.appendingPathComponent("Desktop", isDirectory: true)))
        }
        if settings.indexDownloads {
            roots.append(IndexingRoot(identifier: "downloads", url: home.appendingPathComponent("Downloads", isDirectory: true)))
        }
        if settings.indexICloudDrive {
            let icloud = home
                .appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs", isDirectory: true)
            roots.append(IndexingRoot(identifier: "icloud", url: icloud))
        }

        return roots.filter { root in
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

    nonisolated func shouldIndex(path: String) -> Bool {
        guard contains(path: path) else { return false }

        let url = URL(fileURLWithPath: path)
        let name = url.lastPathComponent

        if name.hasPrefix(".") { return false }
        if Self.excludedDirectoryNames.contains(name) { return false }

        for fragment in Self.excludedPathFragments {
            if path.contains(fragment) { return false }
        }

        var isDir: ObjCBool = false
        guard FileManager.default.fileExists(atPath: path, isDirectory: &isDir) else {
            return true // deleted file — handled upstream
        }
        if isDir.boolValue { return false }

        let ext = url.pathExtension.lowercased()
        guard Self.indexableExtensions.contains(ext) else { return false }

        if let attrs = try? FileManager.default.attributesOfItem(atPath: path),
           let size = attrs[.size] as? Int64,
           size > Self.maxFileBytes {
            return false
        }

        return true
    }

    /// Background-safe filesystem walk — must not be called from async contexts directly.
    nonisolated static func discoverFiles(in folders: [String], settings: UserSettings) -> [String] {
        let policy = IndexingPolicy(settings: settings)
        let allowed = indexableExtensions
        var results: [String] = []
        let fm = FileManager.default

        for folder in folders {
            guard policy.contains(path: folder) else { continue }
            guard let enumerator = fm.enumerator(
                at: URL(fileURLWithPath: folder),
                includingPropertiesForKeys: [.isRegularFileKey, .fileSizeKey],
                options: [.skipsHiddenFiles, .skipsPackageDescendants]
            ) else {
                continue
            }

            while let item = enumerator.nextObject() {
                guard let fileURL = item as? URL else { continue }
                let path = fileURL.path
                if !policy.shouldIndex(path: path) { continue }
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

nonisolated struct IndexingRoot: Equatable, Sendable {
    let identifier: String
    let url: URL

    nonisolated var displayName: String {
        switch identifier {
        case "documents": return "Documents"
        case "desktop": return "Desktop"
        case "downloads": return "Downloads"
        case "icloud": return "iCloud Drive"
        default: return url.lastPathComponent
        }
    }
}
