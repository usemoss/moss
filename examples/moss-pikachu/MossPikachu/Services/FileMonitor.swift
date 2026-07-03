import CoreServices
import Foundation

nonisolated final class FileMonitor: @unchecked Sendable {
    var policy = IndexingPolicy()
    var onChange: ([String]) -> Void = { _ in }

    private var stream: FSEventStreamRef?
    private var watchedPaths: [String] = []
    private var pendingPaths: Set<String> = []
    private let queue = DispatchQueue(label: "dev.moss.pikachu.filemonitor")
    private var flushTimer: DispatchWorkItem?

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

        let callback: FSEventStreamCallback = { _, info, numEvents, eventPaths, eventFlags, _ in
            guard let info else { return }
            let monitor = Unmanaged<FileMonitor>.fromOpaque(info).takeUnretainedValue()
            let paths = eventPaths.bindMemory(to: UnsafePointer<CChar>?.self, capacity: numEvents)
            let flags = eventFlags
            var changed: [String] = []
            for i in 0..<numEvents {
                if let cPath = paths[i] {
                    let path = String(cString: cPath)
                    let isRemoved = flags[i] & UInt32(kFSEventStreamEventFlagItemRemoved) != 0
                    if isRemoved || monitor.shouldIndex(path: path) {
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
        policy.shouldIndex(path: path)
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
        DispatchQueue.main.async { [weak self] in
            self?.onChange(batch)
        }
    }
}
