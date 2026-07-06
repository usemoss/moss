import Foundation

enum PythonEnvironmentError: LocalizedError {
    case pythonNotFound
    case mossNotInstalled(String)

    var errorDescription: String? {
        switch self {
        case .pythonNotFound:
            return "Python environment not found. Build again in Xcode (⌘R) or run ./scripts/setup-moss-venv.sh from the project root."
        case .mossNotInstalled(let detail):
            return "Moss Python package is not installed. \(detail)"
        }
    }
}

nonisolated enum PythonEnvironment {
    /// Repo root: three levels above MossPikachu/Services.
    nonisolated static func repoRoot(from sourceFile: String = #filePath) -> URL {
        URL(fileURLWithPath: sourceFile)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
    }

    nonisolated static func venvPythonPath(from sourceFile: String = #filePath) -> String {
        repoRoot(from: sourceFile).appendingPathComponent(".venv/bin/python3").path
    }

    nonisolated static func resolvePythonPath(from sourceFile: String = #filePath) -> String? {
        let venv = venvPythonPath(from: sourceFile)
        if FileManager.default.isExecutableFile(atPath: venv) {
            return venv
        }
        let system = "/usr/bin/python3"
        if FileManager.default.isExecutableFile(atPath: system) {
            return system
        }
        return nil
    }

    /// Verifies the venv can import Moss before starting the worker.
    nonisolated static func preflight(from sourceFile: String = #filePath) throws {
        guard let python = resolvePythonPath(from: sourceFile) else {
            throw PythonEnvironmentError.pythonNotFound
        }

        let venv = venvPythonPath(from: sourceFile)
        if python != venv {
            throw PythonEnvironmentError.pythonNotFound
        }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: python)
        proc.arguments = ["-c", "from moss import MossClient"]

        let stderrPipe = Pipe()
        proc.standardOutput = Pipe()
        proc.standardError = stderrPipe

        try proc.run()
        proc.waitUntilExit()

        guard proc.terminationStatus == 0 else {
            let errData = stderrPipe.fileHandleForReading.readDataToEndOfFile()
            let errText = String(data: errData, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? "import failed"
            throw PythonEnvironmentError.mossNotInstalled(errText)
        }
    }
}
