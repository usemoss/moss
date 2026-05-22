import Foundation
import MossC

/// Implement to inject a custom auth flow into [MossClient].
///
/// The native runtime calls [getAuthHeader] whenever it needs a fresh bearer
/// token. Implementations typically fetch from a server endpoint and cache.
///
/// Tokens returned must be the raw bearer token (no `Bearer ` prefix).
///
/// Implementations must be safe to call from any thread; the native side may
/// invoke from a background worker.
public protocol Authenticator: AnyObject, Sendable {
    func getAuthHeader() async throws -> String
}

// ── Internal C-callback dispatch ─────────────────────────────────────

/// Holds a strong reference to the user's authenticator so the C callback can
/// dispatch back. The pointer to this box becomes the `user_data` passed to
/// `moss_client_new_with_authenticator`. The actual C trampoline lives in
/// MossClient.swift to avoid Swift emitting duplicate `@_cdecl` symbols
/// across translation units that reference it (eager linking would
/// otherwise reject the build).
///
/// `@unchecked Sendable`: the box only holds an immutable `any Authenticator`,
/// and the `Authenticator` protocol itself requires `Sendable`. The Swift
/// compiler can't see that across the `Unmanaged.fromOpaque` boundary —
/// hence `@unchecked`.
final class AuthenticatorBox: @unchecked Sendable {
    let inner: any Authenticator
    init(_ inner: any Authenticator) { self.inner = inner }
}
