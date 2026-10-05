import Foundation

/// Surfaced for any failure reported by the underlying libmoss runtime.
///
/// `code` is a `MossResult` value from libmoss; compare it with the constants below.
/// `message` is fixed text for each kind of core failure. An argument the SDK rejects keeps its own text.
/// `detail` is diagnostic text for logs and support, not a stable contract, and `nil` when there is none.
/// It holds the core error text, or the Foundation error when the model cache directory cannot be created.
public struct MossError: LocalizedError {
    public let code: Int32
    public let message: String
    public let detail: String?

    public var errorDescription: String? { message }

    /// A required pointer argument was NULL.
    public static let nullPointer: Int32 = -1
    /// An argument was rejected.
    public static let invalidArgument: Int32 = -2
    /// The Moss service could not be reached or did not answer in time.
    public static let network: Int32 = -3
    /// The index does not exist or is not loaded.
    public static let notFound: Int32 = -4
    /// The embedding model could not be downloaded, verified or loaded.
    public static let modelUnavailable: Int32 = -5
    /// A failure inside the SDK.
    public static let internalError: Int32 = -7
    /// The project credentials, token or plan were rejected.
    public static let unauthorized: Int32 = -8
    /// Index data, a snapshot or a service response could not be decoded.
    public static let deserialization: Int32 = -9

    init(code: Int32, message: String, detail: String? = nil) {
        self.code = code
        self.message = message
        self.detail = detail
    }
}
