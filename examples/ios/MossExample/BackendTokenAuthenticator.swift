import Foundation
import Moss

/// Production-ready `Authenticator` that keeps your long-lived `projectKey` on
/// your own backend and lets the app authenticate with short-lived tokens.
///
/// ## Why cache on-device?
///
/// The SDK calls `getAuthHeader()` on **every** outbound request and does not
/// cache delegated tokens for you (unlike the static-key path, where the SDK
/// caches internally). If `getAuthHeader()` called your backend every time,
/// you'd pay a network round-trip per `query` / `loadIndex`.
///
/// So this implementation caches the token on-device and only calls your
/// backend when the cached token is missing or about to expire. The expiry
/// check is a local clock comparison — no network — so steady-state queries
/// never touch your server.
///
/// ## Backend contract
///
/// Your token endpoint should return JSON in the same shape Moss's own token
/// endpoint uses:
///
/// ```json
/// { "token": "eyJhbGciOi...", "expiresIn": 3600 }
/// ```
///
/// `expiresIn` is the token's lifetime in seconds. We refresh 60 seconds early
/// (the same safety margin the SDK uses internally) so a token can't expire
/// while a request is in flight.
///
/// ## Usage
///
/// ```swift
/// let auth = BackendTokenAuthenticator(
///     tokenURL: URL(string: "https://api.yourapp.com/moss-token")!
/// )
/// let client = try MossClient(projectId: "your_project_id", authenticator: auth)
/// ```
///
/// Only `let` stored properties (all `Sendable`) live on the class; the mutable
/// cache is isolated in the `TokenStore` actor, so the type is safely
/// `Sendable` as the `Authenticator` protocol requires.
final class BackendTokenAuthenticator: Authenticator {

    /// Your backend endpoint that vends a short-lived Moss token.
    private let tokenURL: URL
    private let session: URLSession
    private let store = TokenStore()

    init(tokenURL: URL, session: URLSession = .shared) {
        self.tokenURL = tokenURL
        self.session = session
    }

    func getAuthHeader() async throws -> String {
        // 1. On-device check — return the cached token with no network call
        //    as long as it's still valid.
        if let cached = await store.valid() {
            return cached
        }

        // 2. Missing or expired — fetch a fresh token from your backend and
        //    cache it (with the 60s safety buffer applied in TokenStore.set).
        let fetched = try await fetchToken()
        await store.set(fetched.token, expiresIn: fetched.expiresIn)

        // Return the RAW token only — the SDK prepends "Bearer " itself.
        return fetched.token
    }

    // ── Backend call ─────────────────────────────────────────────────────────

    private struct TokenResponse: Decodable {
        let token: String
        let expiresIn: TimeInterval // seconds
    }

    private func fetchToken() async throws -> TokenResponse {
        var request = URLRequest(url: tokenURL)
        request.httpMethod = "GET"

        // Authenticate *this* request with your own user credential so your
        // backend knows who's asking before it hands out a Moss token, e.g.:
        //
        //   request.setValue("Bearer \(myUserSessionToken)",
        //                    forHTTPHeaderField: "Authorization")

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw AuthError(message: "Token endpoint returned a non-HTTP response")
        }
        guard (200..<300).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw AuthError(message: "Token endpoint failed (HTTP \(http.statusCode)): \(body)")
        }
        return try JSONDecoder().decode(TokenResponse.self, from: data)
    }
}

/// Thread-safe token cache. An `actor` because the SDK may invoke
/// `getAuthHeader()` from a background worker thread.
actor TokenStore {
    private var token: String?
    private var expiresAt: Date = .distantPast

    /// Returns the cached token if it's still valid, otherwise `nil`.
    func valid() -> String? {
        guard let token, expiresAt > Date() else { return nil }
        return token
    }

    /// Caches a token, expiring it 60s early to match the SDK's internal
    /// safety margin (avoids a token lapsing mid-request under clock skew).
    func set(_ token: String, expiresIn: TimeInterval) {
        self.token = token
        self.expiresAt = Date().addingTimeInterval(max(0, expiresIn - 60))
    }
}

/// Error raised when the token endpoint can't be reached or returns a failure.
private struct AuthError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}
