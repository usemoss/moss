import Foundation

struct IndexedFileRecord: Codable, Equatable {
    let path: String
    let modificationDate: TimeInterval
}

struct IndexManifest: Codable {
    var files: [String: IndexedFileRecord] = [:]
    var lastIndexedDate: Date?
}
