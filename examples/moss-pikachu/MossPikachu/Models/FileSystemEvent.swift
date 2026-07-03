import Foundation

struct IndexedFileRecord: Codable, Equatable {
    let path: String
    let modificationDate: TimeInterval
    var fileSize: Int64?
    var fileExtension: String?
    var rootIdentifier: String?
    var chunkCount: Int?

    init(
        path: String,
        modificationDate: TimeInterval,
        fileSize: Int64? = nil,
        fileExtension: String? = nil,
        rootIdentifier: String? = nil,
        chunkCount: Int? = nil
    ) {
        self.path = path
        self.modificationDate = modificationDate
        self.fileSize = fileSize
        self.fileExtension = fileExtension
        self.rootIdentifier = rootIdentifier
        self.chunkCount = chunkCount
    }
}

struct IndexManifest: Codable {
    var version: Int = IndexingPolicy.manifestVersion
    var scopeFingerprint: String?
    var files: [String: IndexedFileRecord] = [:]
    var lastIndexedDate: Date?
}
