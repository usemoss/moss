import Foundation
import os.log

nonisolated final class AppLogger: @unchecked Sendable {
    static let shared = AppLogger()

    var isDebugEnabled = false
    private let logFileURL: URL
    private let osLog = Logger(subsystem: "dev.moss.pikachu", category: "app")

    private init() {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dir = appSupport.appendingPathComponent("MossPikachu", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        logFileURL = dir.appendingPathComponent("moss-pikachu.log")
    }

    func log(_ message: String) {
        let line = "[\(ISO8601DateFormatter().string(from: Date()))] \(message)\n"
        if isDebugEnabled {
            print(line, terminator: "")
            osLog.debug("\(message)")
            if let data = line.data(using: .utf8) {
                if FileManager.default.fileExists(atPath: logFileURL.path) {
                    if let handle = try? FileHandle(forWritingTo: logFileURL) {
                        handle.seekToEndOfFile()
                        handle.write(data)
                        try? handle.close()
                    }
                } else {
                    try? data.write(to: logFileURL)
                }
            }
        }
    }
}
