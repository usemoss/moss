import Foundation

enum DotEnvLoader {
    /// Parses a `.env` file for KEY=VALUE pairs. Does not log values.
    static func load(from url: URL) -> [String: String] {
        guard let contents = try? String(contentsOf: url, encoding: .utf8) else {
            return [:]
        }
        var result: [String: String] = [:]
        for line in contents.split(whereSeparator: \.isNewline) {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty || trimmed.hasPrefix("#") { continue }
            let parts = trimmed.split(separator: "=", maxSplits: 1).map(String.init)
            guard parts.count == 2 else { continue }
            let key = parts[0].trimmingCharacters(in: .whitespaces)
            var value = parts[1].trimmingCharacters(in: .whitespaces)
            if (value.hasPrefix("\"") && value.hasSuffix("\"")) ||
                (value.hasPrefix("'") && value.hasSuffix("'")) {
                value = String(value.dropFirst().dropLast())
            }
            result[key] = value
        }
        return result
    }

    /// Walks up from start directory looking for `.env`.
    static func findRepoDotEnv(startingAt: URL, maxDepth: Int = 6) -> URL? {
        var dir = startingAt
        for _ in 0..<maxDepth {
            let candidate = dir.appendingPathComponent(".env")
            if FileManager.default.fileExists(atPath: candidate.path) {
                return candidate
            }
            let parent = dir.deletingLastPathComponent()
            if parent.path == dir.path { break }
            dir = parent
        }
        return nil
    }

    static func mossCredentials() -> (String, String)? {
        guard let envURL = findRepoDotEnv(startingAt: URL(fileURLWithPath: #filePath)) else {
            return nil
        }
        let vars = load(from: envURL)
        guard let id = vars["MOSS_PROJECT_ID"], !id.isEmpty,
              let key = vars["MOSS_PROJECT_KEY"], !key.isEmpty else {
            return nil
        }
        return (id, key)
    }
}
