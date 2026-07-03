import Foundation

final class IndexManager {
    private let manifestURL: URL
    private var manifest = IndexManifest()
    private let queue = DispatchQueue(label: "dev.moss.pikachu.indexmanager")

    init(manifestFilename: String = IndexingPolicy.manifestFilename) {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent("MossPikachu", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        manifestURL = dir.appendingPathComponent(manifestFilename)
        load()
    }

    var indexedFileCount: Int { manifest.files.count }
    var lastIndexedDate: Date? { manifest.lastIndexedDate }
    var scopeFingerprint: String? { manifest.scopeFingerprint }

    func load() {
        guard let data = try? Data(contentsOf: manifestURL),
              let loaded = try? JSONDecoder().decode(IndexManifest.self, from: data) else { return }
        manifest = loaded
    }

    func save() {
        manifest.lastIndexedDate = Date()
        queue.sync {
            if let data = try? JSONEncoder().encode(manifest) {
                try? data.write(to: manifestURL, options: .atomic)
            }
        }
    }

    func clear() {
        manifest = IndexManifest()
        save()
    }

    func updateScopeFingerprint(_ fingerprint: String) {
        manifest.scopeFingerprint = fingerprint
        save()
    }

    func scopeChanged(from policy: IndexingPolicy) -> Bool {
        guard let stored = manifest.scopeFingerprint, !stored.isEmpty else {
            return manifest.files.isEmpty ? false : true
        }
        return stored != policy.scopeFingerprint
    }

    func filesNeedingIndex(in paths: [String]) -> [String] {
        paths.filter { path in
            guard let attrs = try? FileManager.default.attributesOfItem(atPath: path),
                  let modDate = attrs[.modificationDate] as? Date else { return false }
            let mtime = modDate.timeIntervalSince1970
            if let existing = manifest.files[path] {
                return existing.modificationDate < mtime
            }
            return true
        }
    }

    func markIndexed(paths: [String], chunkCounts: [String: Int] = [:], policy: IndexingPolicy? = nil) {
        for path in paths {
            guard let attrs = try? FileManager.default.attributesOfItem(atPath: path),
                  let modDate = attrs[.modificationDate] as? Date else { continue }
            let size = attrs[.size] as? Int64
            let ext = URL(fileURLWithPath: path).pathExtension.lowercased()
            manifest.files[path] = IndexedFileRecord(
                path: path,
                modificationDate: modDate.timeIntervalSince1970,
                fileSize: size,
                fileExtension: ext.isEmpty ? nil : ext,
                rootIdentifier: policy?.rootIdentifier(for: path),
                chunkCount: chunkCounts[path]
            )
        }
        save()
    }

    func allIndexedPaths() -> [String] {
        Array(manifest.files.keys)
    }

    /// Paths in manifest that no longer exist on disk or are outside current policy.
    func stalePaths(validatingWith policy: IndexingPolicy) -> [String] {
        manifest.files.keys.filter { path in
            !FileManager.default.fileExists(atPath: path) || !policy.shouldIndex(path: path)
        }
    }

    func removePaths(_ paths: [String]) {
        for path in paths {
            manifest.files.removeValue(forKey: path)
        }
        if !paths.isEmpty { save() }
    }

    func chunkIDs(for path: String, maxChunks: Int = 32) -> [String] {
        let count = manifest.files[path]?.chunkCount ?? maxChunks
        let limit = max(1, min(count + 2, maxChunks))
        return (0..<limit).map { "\(path)#chunk-\(String(format: "%04d", $0))" }
    }
}
