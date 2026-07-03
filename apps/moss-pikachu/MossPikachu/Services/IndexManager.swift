import Foundation

final class IndexManager {
    private let manifestURL: URL
    private var manifest = IndexManifest()
    private let queue = DispatchQueue(label: "dev.moss.pikachu.indexmanager")

    init(manifestFilename: String = "index-manifest.json") {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent("MossPikachu", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        manifestURL = dir.appendingPathComponent(manifestFilename)
        load()
    }

    var indexedFileCount: Int { manifest.files.count }
    var lastIndexedDate: Date? { manifest.lastIndexedDate }

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

    func markIndexed(paths: [String]) {
        for path in paths {
            guard let attrs = try? FileManager.default.attributesOfItem(atPath: path),
                  let modDate = attrs[.modificationDate] as? Date else { continue }
            manifest.files[path] = IndexedFileRecord(path: path, modificationDate: modDate.timeIntervalSince1970)
        }
        save()
    }

    func allIndexedPaths() -> [String] {
        Array(manifest.files.keys)
    }
}
