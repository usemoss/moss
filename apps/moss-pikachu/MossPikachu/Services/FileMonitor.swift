import CoreServices
import Foundation

final class FileMonitor {
    static let indexableExtensions: Set<String> = ["md", "txt", "pdf", "notes", "rtf", "docx", "html"]

    var onChange: ([String]) -> Void = { _ in }

    private var stream: FSEventStreamRef?
    private var watchedPaths: [String] = []
    private var pendingPaths: Set<String> = []
    private let queue = DispatchQueue(label: "dev.moss.pikachu.filemonitor")
    private var flushTimer: DispatchWorkItem?

    private let allowedExtensions = FileMonitor.indexableExtensions
    private let ignoredNames: Set<String> = [".DS_Store", ".git", "node_modules"]

    func updateWatchedPaths(_ paths: [String]) {
        watchedPaths = paths
        if stream != nil {
            stop()
            _ = start()
        }
    }

    func start() -> Bool {
        guard !watchedPaths.isEmpty else { return false }

        var context = FSEventStreamContext(
            version: 0,
            info: Unmanaged.passUnretained(self).toOpaque(),
            retain: nil,
            release: nil,
            copyDescription: nil
        )

        let callback: FSEventStreamCallback = { _, info, numEvents, eventPaths, _, _ in
            guard let info else { return }
            let monitor = Unmanaged<FileMonitor>.fromOpaque(info).takeUnretainedValue()
            let paths = eventPaths.bindMemory(to: UnsafePointer<CChar>?.self, capacity: numEvents)
            var changed: [String] = []
            for i in 0..<numEvents {
                if let cPath = paths[i] {
                    let path = String(cString: cPath)
                    if monitor.shouldIndex(path: path) {
                        changed.append(path)
                    }
                }
            }
            if !changed.isEmpty {
                monitor.enqueue(changed)
            }
        }

        stream = FSEventStreamCreate(
            nil,
            callback,
            &context,
            watchedPaths as CFArray,
            FSEventStreamEventId(kFSEventStreamEventIdSinceNow),
            0.1,
            UInt32(kFSEventStreamCreateFlagFileEvents)
        )

        guard let stream else { return false }
        FSEventStreamSetDispatchQueue(stream, queue)
        return FSEventStreamStart(stream)
    }

    func stop() {
        if let stream {
            FSEventStreamStop(stream)
            FSEventStreamInvalidate(stream)
            FSEventStreamRelease(stream)
            self.stream = nil
        }
        flushTimer?.cancel()
        pendingPaths.removeAll()
    }

    private func shouldIndex(path: String) -> Bool {
        guard IndexScope.contains(path: path) else { return false }
        let url = URL(fileURLWithPath: path)
        let name = url.lastPathComponent
        if name.hasPrefix(".") { return false }
        if ignoredNames.contains(name) { return false }
        if path.contains("/.git/") || path.contains("/node_modules/") { return false }
        guard FileManager.default.fileExists(atPath: path) else { return true }
        var isDir: ObjCBool = false
        FileManager.default.fileExists(atPath: path, isDirectory: &isDir)
        if isDir.boolValue { return false }
        let ext = url.pathExtension.lowercased()
        return allowedExtensions.contains(ext)
    }

    private func enqueue(_ paths: [String]) {
        queue.async { [weak self] in
            guard let self else { return }
            for path in paths {
                self.pendingPaths.insert(path)
            }
            self.scheduleFlush()
        }
    }

    private func scheduleFlush() {
        flushTimer?.cancel()
        if pendingPaths.count >= 10 {
            flush()
            return
        }
        let work = DispatchWorkItem { [weak self] in self?.flush() }
        flushTimer = work
        queue.asyncAfter(deadline: .now() + 0.1, execute: work)
    }

    private func flush() {
        guard !pendingPaths.isEmpty else { return }
        let batch = Array(pendingPaths)
        pendingPaths.removeAll()
        AppLogger.shared.log("Detected file changes: \(batch.count) files")
        for path in batch {
            AppLogger.shared.log("  → \(path)")
        }
        DispatchQueue.main.async { [weak self] in
            self?.onChange(batch)
        }
    }
}
