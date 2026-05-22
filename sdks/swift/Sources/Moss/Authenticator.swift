import Foundation
import MossC

/// Implement to inject a custom auth flow into [MossClient].
///
/// The native runtime calls [getAuthHeader] whenever it needs a fresh bearer
/// token for an outbound request. Implementations typically fetch the token
/// from your backend (and cache it until expiry).
///
/// ## Return-value contract
///
/// Return **the raw bearer token only** — do **not** include the `Bearer `
/// prefix or any other Authorization-header decoration:
///
/// ```swift
/// // ✅ correct
/// return "eyJhbGciOi..."
/// // ❌ wrong — the SDK prepends `Bearer ` itself
/// return "Bearer eyJhbGciOi..."
/// ```
///
/// The Swift wrapper passes this string directly to the native side, which
/// constructs the full `Authorization: Bearer <token>` header. The JS SDK's
/// `IAuthenticator.getAuthHeader()` happens to use the opposite convention
/// (returns the full `Bearer ...` value); that's because the JS SDK builds
/// the request in JS userland rather than going through the native C ABI.
/// Don't copy the JS convention here.
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
