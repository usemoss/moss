import Foundation

/// Thin wrapper around OpenAI chat completions.
/// No third-party dependency — uses URLSession directly.
enum LLMService {

    struct Response {
        let answer: String
        let model:  String
        let tokens: Int
    }

    enum LLMError: LocalizedError {
        case missingKey
        case httpError(Int, String)
        case badResponse

        var errorDescription: String? {
            switch self {
            case .missingKey:              return "No OpenAI API key set. Add one in Settings."
            case .httpError(let c, let m): return "OpenAI error \(c): \(m)"
            case .badResponse:             return "Could not parse OpenAI response."
            }
        }
    }

    static func answer(
        query:  String,
        hits:   [SearchHit],
        apiKey: String,
        model:  String = "gpt-4o-mini"
    ) async throws -> Response {
        guard !apiKey.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw LLMError.missingKey
        }

        let context = hits.enumerated().map { i, hit in
            "[\(i + 1)] Source: \(hit.sourceName)\n\(hit.excerpt)"
        }.joined(separator: "\n\n")

        let systemPrompt = """
        You are a helpful assistant that answers questions using only the provided context.
        - If the context contains the answer, give it clearly and concisely.
        - Cite source numbers (e.g. [1], [2]) inline where relevant.
        - If the context is insufficient, say so honestly.
        - Format your answer in plain text. No markdown headers.
        """

        let messages: [[String: Any]] = [
            ["role": "system", "content": systemPrompt],
            ["role": "user",   "content": "Context:\n\(context)\n\nQuestion: \(query)"],
        ]

        let body: [String: Any] = [
            "model":       model,
            "messages":    messages,
            "temperature": 0.2,
            "max_tokens":  1500,
        ]

        var request = URLRequest(url: URL(string: "https://api.openai.com/v1/chat/completions")!)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, urlResponse) = try await URLSession.shared.data(for: request)

        if let http = urlResponse as? HTTPURLResponse, http.statusCode != 200 {
            let msg = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])
                .flatMap { $0["error"] as? [String: Any] }
                .flatMap { $0["message"] as? String }
                ?? String(data: data, encoding: .utf8) ?? "unknown"
            throw LLMError.httpError(http.statusCode, msg)
        }

        guard
            let json    = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let choices = json["choices"] as? [[String: Any]],
            let message = choices.first?["message"] as? [String: Any],
            let content = message["content"] as? String,
            let usage   = json["usage"] as? [String: Any],
            let tokens  = usage["total_tokens"] as? Int,
            let model   = json["model"] as? String
        else { throw LLMError.badResponse }

        return Response(
            answer: content.trimmingCharacters(in: .whitespacesAndNewlines),
            model:  model,
            tokens: tokens
        )
    }
}
