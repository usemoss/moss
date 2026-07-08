import Foundation

/// Moss SessionIndex scope for the current product build (test corpus: Downloads/cwp-stuff).
enum IndexScope {
    static let folderName = "cwp-stuff"
    static let sessionName = "cwp-stuff"
    static let manifestFilename = "index-manifest-cwp-stuff.json"

    /// Resolved `~/Downloads/cwp-stuff` for the current user.
    static var watchedFolderURL: URL? {
        let downloads = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Downloads", isDirectory: true)
        let folder = downloads.appendingPathComponent(folderName, isDirectory: true)
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: folder.path, isDirectory: &isDirectory),
              isDirectory.boolValue else {
            return nil
        }
        return folder
    }

    static func contains(path: String) -> Bool {
        guard let root = watchedFolderURL?.path else { return false }
        return path == root || path.hasPrefix(root + "/")
    }
}
