import Foundation

nonisolated enum MossPikachuPaths {
    static let appSupportFolderName = "MossPikachu"
    static let logFilename = "moss-pikachu.log"
    static let keychainService = "dev.moss.pikachu"
    static let legacyKeychainService = "dev.moss.pikachu"

    nonisolated static func appSupportDirectory() -> URL {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent(appSupportFolderName, isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }
}
