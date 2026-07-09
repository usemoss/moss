import Foundation

nonisolated struct SearchResult: Codable, Identifiable, Equatable, Sendable {
    let id: String
    let text: String
    let score: Double
    let filename: String
    let path: String
    let timingMs: Double
    let isMissingOnDisk: Bool

    nonisolated enum CodingKeys: String, CodingKey {
        case id, text, score, filename, path
        case timingMs = "timing_ms"
        case isMissingOnDisk = "is_missing_on_disk"
    }

    nonisolated init(
        id: String,
        text: String,
        score: Double,
        filename: String,
        path: String,
        timingMs: Double,
        isMissingOnDisk: Bool = false
    ) {
        self.id = id
        self.text = text
        self.score = score
        self.filename = filename
        self.path = path
        self.timingMs = timingMs
        self.isMissingOnDisk = isMissingOnDisk
    }

    nonisolated init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        text = try container.decode(String.self, forKey: .text)
        score = try container.decode(Double.self, forKey: .score)
        filename = try container.decode(String.self, forKey: .filename)
        path = try container.decode(String.self, forKey: .path)
        timingMs = try container.decode(Double.self, forKey: .timingMs)
        isMissingOnDisk = try container.decodeIfPresent(Bool.self, forKey: .isMissingOnDisk) ?? false
    }
}
