import Foundation

/// Surfaced for any failure reported by the underlying libmoss runtime.
public struct MossError: LocalizedError {
    public let code: Int32
    public let message: String

    public var errorDescription: String? { message }

    init(code: Int32, message: String) {
        self.code = code
        self.message = message
    }
}
