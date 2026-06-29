import Foundation
import PDFKit    // built-in iOS framework, no extra dependency
import UniformTypeIdentifiers

/// Extracts and chunks text from PDF and plain-text files.
/// Pure static functions — no state, no Moss dependency.
enum FileIngester {

    // MARK: - Public API

    /// Returns ~400-char chunks with sentence-boundary preference.
    static func chunk(url: URL, filename: String) -> [String] {
        let raw = extract(url: url)
        guard !raw.isEmpty else { return [] }
        return splitIntoChunks(raw, maxChars: 400, overlap: 60)
    }

    // MARK: - Extraction

    private static func extract(url: URL) -> String {
        let ext = url.pathExtension.lowercased()
        switch ext {
        case "pdf":
            return extractPDF(url: url)
        default:
            // Try UTF-8 first, fall back to Latin-1 for legacy files
            return (try? String(contentsOf: url, encoding: .utf8))
                ?? (try? String(contentsOf: url, encoding: .isoLatin1))
                ?? ""
        }
    }

    private static func extractPDF(url: URL) -> String {
        guard let pdf = PDFDocument(url: url) else { return "" }
        return (0..<pdf.pageCount)
            .compactMap { pdf.page(at: $0)?.string }
            .joined(separator: "\n")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: - Chunking

    /// Splits text into overlapping chunks.
    /// Prefers splitting at sentence boundaries (". ", "? ", "! ", "\n\n")
    /// so each chunk is semantically self-contained — better for retrieval.
    private static func splitIntoChunks(_ text: String, maxChars: Int, overlap: Int) -> [String] {
        let sentences = roughSplit(text)
        var chunks: [String] = []
        var current: [String] = []
        var currentLen = 0

        for sentence in sentences {
            let sLen = sentence.count
            if currentLen + sLen > maxChars, !current.isEmpty {
                chunks.append(current.joined(separator: " "))
                // Overlap: walk backwards, keep sentences until we exceed overlap budget
                var tail: [String] = []
                var tailLen = 0
                for s in current.reversed() {
                    guard tailLen + s.count < overlap else { break }
                    tail.insert(s, at: 0)
                    tailLen += s.count
                }
                current = tail
                currentLen = tailLen
            }
            current.append(sentence)
            currentLen += sLen
        }
        if !current.isEmpty {
            chunks.append(current.joined(separator: " "))
        }
        return chunks.filter { $0.count > 20 }   // discard noise fragments
    }

    /// Split on sentence boundaries: ". ", "? ", "! ", paragraph breaks.
    private static func roughSplit(_ text: String) -> [String] {
        let normalized = text
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r",   with: "\n")

        // Insert a newline after each sentence terminator so we can split cleanly,
        // then flatten paragraphs — no manual index arithmetic.
        let split = normalized
            .replacingOccurrences(of: ". ",  with: ".\n")
            .replacingOccurrences(of: "? ",  with: "?\n")
            .replacingOccurrences(of: "! ",  with: "!\n")
            .components(separatedBy: "\n")

        return split
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }
}
