import Foundation

struct SearchResult: Codable, Identifiable, Equatable {
    let id: String
    let text: String
    let score: Double
    let filename: String
    let path: String
    let timingMs: Double

    enum CodingKeys: String, CodingKey {
        case id, text, score, filename, path
        case timingMs = "timing_ms"
    }
}
