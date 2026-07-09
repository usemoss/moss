import Foundation
import os.log
import Darwin

nonisolated final class AppLogger: @unchecked Sendable {
    static let shared = AppLogger()

    var isDebugEnabled = false
    private let logFileURL: URL
    private let osLog = Logger(subsystem: "dev.picklight", category: "app")

    private init() {
        let dir = PicklightPaths.appSupportDirectory()
        logFileURL = dir.appendingPathComponent(PicklightPaths.logFilename)
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

    /// Returns resident memory in MB, or nil if unavailable.
    func residentMemoryMB() -> Double? {
        var info = mach_task_basic_info()
        var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size) / 4
        let result = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &count)
            }
        }
        guard result == KERN_SUCCESS else { return nil }
        return Double(info.resident_size) / 1024 / 1024
    }

    /// Logs resident memory for the current process (MB).
    func logMemory(_ label: String) {
        guard let mb = residentMemoryMB() else { return }
        log(String(format: "[memory] %@: %.1f MB resident", label, mb))
    }
}
