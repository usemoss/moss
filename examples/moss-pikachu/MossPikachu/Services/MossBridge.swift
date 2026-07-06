import Foundation
import Security

enum MossBridgeError: LocalizedError {
    case workerNotFound
    case workerStartFailed(String)
    case workerCrashed
    case timeout
    case invalidResponse
    case mossError(String)
    case missingCredentials

    var errorDescription: String? {
        switch self {
        case .workerNotFound: return "moss_worker.py not found in app bundle."
        case .workerStartFailed(let msg): return "Failed to start Moss worker: \(msg)"
        case .workerCrashed: return "Moss worker process crashed."
        case .timeout: return "Moss worker request timed out."
        case .invalidResponse: return "Invalid response from Moss worker."
        case .mossError(let msg): return msg
        case .missingCredentials: return "Moss credentials missing. Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY."
        }
    }
}

nonisolated struct MossSessionInitResult: Sendable {
    let docCount: Int
    let loadedFromDisk: Bool
    let cachePath: String?
}

nonisolated final class MossBridge: @unchecked Sendable {
    private struct PendingRequest {
        let id: UUID
        let continuation: CheckedContinuation<[String: Any], Error>
    }

    private var process: Process?
    private var stdinHandle: FileHandle?
    private let ioQueue = DispatchQueue(label: "dev.moss.pikachu.mossbridge")
    private var readBuffer = ""
    private var pendingRequests: [PendingRequest] = []
    private var isReading = false

    private let projectID: String
    private let projectKey: String

    /// Default timeout for Moss worker RPCs. add_docs uses a longer budget.
    private static let defaultTimeout: TimeInterval = 45
    private static let initSessionTimeout: TimeInterval = 120
    private static let addDocsTimeout: TimeInterval = 90
    private static let saveSessionTimeout: TimeInterval = 120

    init(projectID: String, projectKey: String) {
        self.projectID = projectID
        self.projectKey = projectKey
    }

    static func hasCredentials() -> Bool {
        (try? loadCredentials()) != nil
    }

    static func loadCredentials() throws -> (String, String) {
        if let id = ProcessInfo.processInfo.environment["MOSS_PROJECT_ID"],
           let key = ProcessInfo.processInfo.environment["MOSS_PROJECT_KEY"],
           !id.isEmpty, !key.isEmpty {
            return (id, key)
        }

        if let id = KeychainHelper.read(account: "project_id"),
           let key = KeychainHelper.read(account: "project_key"),
           !id.isEmpty, !key.isEmpty {
            return (id, key)
        }

        if let id = KeychainHelper.readLegacy(account: "project_id"),
           let key = KeychainHelper.readLegacy(account: "project_key"),
           !id.isEmpty, !key.isEmpty {
            return (id, key)
        }

        if let creds = DotEnvLoader.mossCredentials() {
            return creds
        }

        throw MossBridgeError.missingCredentials
    }

    func start() throws {
        guard process == nil else { return }
        try PythonEnvironment.preflight()

        guard let workerURL = Bundle.main.url(forResource: "moss_worker", withExtension: "py") else {
            // Dev fallback: source tree
            let devPath = URL(fileURLWithPath: #filePath)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .appendingPathComponent("Resources/moss_worker.py")
            if FileManager.default.fileExists(atPath: devPath.path) {
                try launchWorker(scriptURL: devPath)
                return
            }
            throw MossBridgeError.workerNotFound
        }
        try launchWorker(scriptURL: workerURL)
    }

    private func launchWorker(scriptURL: URL) throws {
        let proc = Process()
        let pythonPath = resolvePythonPath()

        proc.executableURL = URL(fileURLWithPath: pythonPath)
        proc.arguments = [scriptURL.path]
        proc.environment = ProcessInfo.processInfo.environment.merging([
            "MOSS_PROJECT_ID": projectID,
            "MOSS_PROJECT_KEY": projectKey,
            "PYTHONUNBUFFERED": "1"
        ]) { _, new in new }

        let stdinPipe = Pipe()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        proc.standardInput = stdinPipe
        proc.standardOutput = stdoutPipe
        proc.standardError = stderrPipe

        proc.terminationHandler = { [weak self] _ in
            guard let bridge = self else { return }
            bridge.ioQueue.async { [weak bridge] in
                guard let bridge, bridge.process === proc || bridge.process == nil else { return }
                bridge.failPending(MossBridgeError.workerCrashed)
                bridge.process = nil
                bridge.stdinHandle = nil
            }
        }

        do {
            try proc.run()
        } catch {
            throw MossBridgeError.workerStartFailed(error.localizedDescription)
        }

        process = proc
        stdinHandle = stdinPipe.fileHandleForWriting

        let readHandle = stdoutPipe.fileHandleForReading
        readHandle.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            guard let bridge = self else { return }
            bridge.ioQueue.async { [weak bridge] in
                bridge?.appendOutput(data)
            }
        }

        let stderrHandle = stderrPipe.fileHandleForReading
        stderrHandle.readabilityHandler = { handle in
            let data = handle.availableData
            guard !data.isEmpty,
                  let text = String(data: data, encoding: .utf8)?
                    .trimmingCharacters(in: .whitespacesAndNewlines),
                  !text.isEmpty else { return }
            AppLogger.shared.log("worker stderr: \(text)")
        }
        isReading = true
    }

    private func resolvePythonPath() -> String {
        PythonEnvironment.resolvePythonPath() ?? "/usr/bin/python3"
    }

    func stop() {
        ioQueue.sync {
            failPending(MossBridgeError.workerCrashed)
            hardResetWorkerLocked(sendShutdown: true)
        }
    }

    func initSession(indexName: String, cachePath: String) async throws -> MossSessionInitResult {
        let response = try await send(
            action: "init_session",
            payload: [
                "index_name": indexName,
                "cache_path": cachePath,
            ],
            timeout: Self.initSessionTimeout
        )
        return MossSessionInitResult(
            docCount: response["doc_count"] as? Int ?? 0,
            loadedFromDisk: response["loaded_from_disk"] as? Bool ?? false,
            cachePath: response["cache_path"] as? String
        )
    }

    func addDocs(files: [String]) async throws -> (
        added: Int,
        updated: Int,
        chunks: Int,
        filesIndexed: Int,
        skipped: Int,
        docCount: Int,
        fileChunkCounts: [String: Int]
    ) {
        let response = try await send(
            action: "add_docs",
            payload: ["files": files],
            timeout: Self.addDocsTimeout
        )
        let rawCounts = response["file_chunk_counts"] as? [String: Any] ?? [:]
        let fileChunkCounts = rawCounts.reduce(into: [String: Int]()) { result, entry in
            if let count = entry.value as? Int {
                result[entry.key] = count
            }
        }
        return (
            added: response["added"] as? Int ?? 0,
            updated: response["updated"] as? Int ?? 0,
            chunks: response["chunks_indexed"] as? Int ?? 0,
            filesIndexed: response["files_indexed"] as? Int ?? 0,
            skipped: response["files_skipped"] as? Int ?? 0,
            docCount: response["doc_count"] as? Int ?? 0,
            fileChunkCounts: fileChunkCounts
        )
    }

    func query(indexName: String, query: String, topK: Int = 12, alpha: Double = 0.75) async throws -> [SearchResult] {
        let response = try await send(
            action: "query",
            payload: [
                "index": indexName,
                "query": query,
                "top_k": topK,
                "alpha": alpha,
            ]
        )
        if let error = response["error"] as? String {
            throw MossBridgeError.mossError(error)
        }
        let timingMs = response["timing_ms"] as? Double ?? 0
        let rawCount = response["raw_count"] as? Int
        if let rawCount {
            AppLogger.shared.log("Moss query raw chunk hits before slice: \(rawCount)")
        }
        guard let resultsArray = response["results"] as? [[String: Any]] else {
            return []
        }
        return resultsArray.compactMap { dict in
            guard let id = dict["id"] as? String,
                  let text = dict["text"] as? String,
                  let score = dict["score"] as? Double else { return nil }
            let path = dict["path"] as? String ?? id
            let filename = dict["filename"] as? String ?? URL(fileURLWithPath: path).lastPathComponent
            return SearchResult(
                id: id, text: text, score: score,
                filename: filename, path: path, timingMs: timingMs
            )
        }
    }

    func saveLocalSession(cachePath: String) async throws -> Int {
        let response = try await send(
            action: "save_session",
            payload: ["cache_path": cachePath],
            timeout: Self.saveSessionTimeout
        )
        return response["doc_count"] as? Int ?? 0
    }

    func clearIndex() async throws {
        _ = try await send(action: "clear_index", payload: [:])
    }

    func deleteDocs(ids: [String]) async throws -> Int {
        guard !ids.isEmpty else { return 0 }
        let response = try await send(action: "delete_docs", payload: ["ids": ids])
        return response["doc_count"] as? Int ?? 0
    }

    // MARK: - Private

    private func send(
        action: String,
        payload: [String: Any],
        timeout: TimeInterval = MossBridge.defaultTimeout
    ) async throws -> [String: Any] {
        try start()
        var body = payload
        body["action"] = action
        let data = try JSONSerialization.data(withJSONObject: body)
        guard let line = String(data: data, encoding: .utf8) else {
            throw MossBridgeError.invalidResponse
        }
        let requestID = UUID()
        return try await withCheckedThrowingContinuation { continuation in
            ioQueue.async { [weak self] in
                guard let self else { return }
                self.pendingRequests.append(PendingRequest(id: requestID, continuation: continuation))
                self.sendRawLine(line)
                self.ioQueue.asyncAfter(deadline: .now() + timeout) { [weak self] in
                    self?.timeoutRequest(id: requestID)
                }
            }
        }
    }

    private func sendRawLine(_ line: String) {
        guard let data = (line + "\n").data(using: .utf8),
              let stdinHandle else { return }
        try? stdinHandle.write(contentsOf: data)
    }

    private func appendOutput(_ data: Data) {
        guard let chunk = String(data: data, encoding: .utf8) else { return }
        readBuffer += chunk
        while let newlineIndex = readBuffer.firstIndex(of: "\n") {
            let line = String(readBuffer[..<newlineIndex])
            readBuffer = String(readBuffer[readBuffer.index(after: newlineIndex)...])
            guard !line.isEmpty, let lineData = line.data(using: .utf8),
                  let json = try? JSONSerialization.jsonObject(with: lineData) as? [String: Any] else {
                continue
            }
            if let error = json["error"] as? String {
                completeNext(with: .failure(MossBridgeError.mossError(error)))
            } else {
                completeNext(with: .success(json))
            }
        }
    }

    private func completeNext(with result: Result<[String: Any], Error>) {
        guard !pendingRequests.isEmpty else { return }
        let request = pendingRequests.removeFirst()
        switch result {
        case .success(let json):
            request.continuation.resume(returning: json)
        case .failure(let error):
            request.continuation.resume(throwing: error)
        }
    }

    private func failPending(_ error: Error) {
        let pending = pendingRequests
        pendingRequests.removeAll()
        for request in pending {
            request.continuation.resume(throwing: error)
        }
    }

    private func timeoutRequest(id: UUID) {
        guard pendingRequests.contains(where: { $0.id == id }) else { return }
        AppLogger.shared.log("Moss worker request timed out — restarting worker")
        failPending(MossBridgeError.timeout)
        hardResetWorkerLocked(sendShutdown: false)
    }

    /// Kill the worker so a hung add_docs/query cannot block forever.
    private func hardResetWorkerLocked(sendShutdown: Bool) {
        readBuffer = ""
        if let process {
            if sendShutdown, process.isRunning {
                sendRawLine(#"{"action":"shutdown"}"#)
            }
            if process.isRunning {
                process.terminate()
            }
        }
        process = nil
        stdinHandle = nil
    }
}

nonisolated enum KeychainHelper {
  private static let service = MossPikachuPaths.keychainService
  private static let legacyService = MossPikachuPaths.legacyKeychainService

  static func read(account: String) -> String? {
    read(account: account, service: service) ?? readLegacy(account: account)
  }

  static func readLegacy(account: String) -> String? {
    read(account: account, service: legacyService)
  }

  static func save(account: String, value: String) throws {
    delete(account: account, service: service)
    let query: [String: Any] = [
      kSecClass as String: kSecClassGenericPassword,
      kSecAttrService as String: service,
      kSecAttrAccount as String: account,
      kSecValueData as String: Data(value.utf8),
      kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
    ]
    let status = SecItemAdd(query as CFDictionary, nil)
    guard status == errSecSuccess else {
      throw NSError(domain: NSOSStatusErrorDomain, code: Int(status))
    }
  }

  static func delete(account: String) throws {
    delete(account: account, service: service)
    delete(account: account, service: legacyService)
  }

  private static func read(account: String, service: String) -> String? {
    let query: [String: Any] = [
      kSecClass as String: kSecClassGenericPassword,
      kSecAttrService as String: service,
      kSecAttrAccount as String: account,
      kSecReturnData as String: true,
      kSecMatchLimit as String: kSecMatchLimitOne,
    ]
    var item: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &item)
    guard status == errSecSuccess, let data = item as? Data else { return nil }
    return String(data: data, encoding: .utf8)
  }

  private static func delete(account: String, service: String) {
    let query: [String: Any] = [
      kSecClass as String: kSecClassGenericPassword,
      kSecAttrService as String: service,
      kSecAttrAccount as String: account,
    ]
    SecItemDelete(query as CFDictionary)
  }
}
