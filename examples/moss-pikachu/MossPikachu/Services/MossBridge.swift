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

nonisolated final class MossBridge: @unchecked Sendable {
    private var process: Process?
    private var stdinHandle: FileHandle?
    private let ioQueue = DispatchQueue(label: "dev.moss.pikachu.mossbridge")
    private var readBuffer = ""
    private var pendingContinuations: [CheckedContinuation<[String: Any], Error>] = []
    private var isReading = false

    private let projectID: String
    private let projectKey: String

    init(projectID: String, projectKey: String) {
        self.projectID = projectID
        self.projectKey = projectKey
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

        if let creds = DotEnvLoader.mossCredentials() {
            return creds
        }

        throw MossBridgeError.missingCredentials
    }

    func start() throws {
        guard process == nil else { return }

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
        proc.standardInput = stdinPipe
        proc.standardOutput = stdoutPipe
        proc.standardError = Pipe()

        proc.terminationHandler = { [weak self] _ in
            guard let bridge = self else { return }
            bridge.ioQueue.async { [weak bridge] in
                bridge?.failPending(MossBridgeError.workerCrashed)
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
        isReading = true
    }

    private func resolvePythonPath() -> String {
        let repoRoot = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let venvPython = repoRoot.appendingPathComponent(".venv/bin/python3").path
        if FileManager.default.isExecutableFile(atPath: venvPython) {
            return venvPython
        }
        return "/usr/bin/python3"
    }

    func stop() {
        if let process, process.isRunning {
            sendRawLine(#"{"action":"shutdown"}"#)
            process.terminate()
        }
        process = nil
        stdinHandle = nil
    }

    func initSession(indexName: String) async throws -> Int {
        let response = try await send(action: "init_session", payload: ["index_name": indexName])
        return response["doc_count"] as? Int ?? 0
    }

    func addDocs(files: [String]) async throws -> (
        added: Int,
        updated: Int,
        chunks: Int,
        filesIndexed: Int,
        skipped: Int,
        docCount: Int
    ) {
        let response = try await send(action: "add_docs", payload: ["files": files])
        return (
            added: response["added"] as? Int ?? 0,
            updated: response["updated"] as? Int ?? 0,
            chunks: response["chunks_indexed"] as? Int ?? 0,
            filesIndexed: response["files_indexed"] as? Int ?? 0,
            skipped: response["files_skipped"] as? Int ?? 0,
            docCount: response["doc_count"] as? Int ?? 0
        )
    }

    func query(indexName: String, query: String, topK: Int = 5) async throws -> [SearchResult] {
        let response = try await send(
            action: "query",
            payload: ["index": indexName, "query": query, "top_k": topK]
        )
        if let error = response["error"] as? String {
            throw MossBridgeError.mossError(error)
        }
        let timingMs = response["timing_ms"] as? Double ?? 0
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

    func pushIndex() async throws -> (docCount: Int, jobID: String?) {
        let response = try await send(action: "push_index", payload: [:])
        return (
            docCount: response["doc_count"] as? Int ?? 0,
            jobID: response["job_id"] as? String
        )
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

    private func send(action: String, payload: [String: Any]) async throws -> [String: Any] {
        try start()
        var body = payload
        body["action"] = action
        let data = try JSONSerialization.data(withJSONObject: body)
        guard let line = String(data: data, encoding: .utf8) else {
            throw MossBridgeError.invalidResponse
        }
        return try await withCheckedThrowingContinuation { continuation in
            ioQueue.async { [weak self] in
                guard let self else { return }
                self.pendingContinuations.append(continuation)
                self.sendRawLine(line)
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
        guard !pendingContinuations.isEmpty else { return }
        let continuation = pendingContinuations.removeFirst()
        switch result {
        case .success(let json):
            continuation.resume(returning: json)
        case .failure(let error):
            continuation.resume(throwing: error)
        }
    }

    private func failPending(_ error: Error) {
        while !pendingContinuations.isEmpty {
            let c = pendingContinuations.removeFirst()
            c.resume(throwing: error)
        }
    }
}

nonisolated enum KeychainHelper {
    static func read(account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "dev.moss.pikachu",
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
}
