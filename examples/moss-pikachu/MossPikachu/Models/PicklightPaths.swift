import Foundation

/// User-facing Picklight paths and identifiers (internal target remains MossPikachu).
nonisolated enum PicklightPaths {
    static let appSupportFolderName = "Picklight"
    static let legacyAppSupportFolderName = "MossPikachu"
    static let logFilename = "picklight.log"
    static let legacyLogFilename = "moss-pikachu.log"

    static let keychainService = "dev.picklight"
    static let legacyKeychainService = "dev.moss.pikachu"

    nonisolated static func appSupportDirectory() -> URL {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent(appSupportFolderName, isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }
}
