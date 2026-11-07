import Foundation

/// A JSON value, for request and response fields the typed API does not model.
public enum JSONValue: Sendable, Hashable {
    case null
    case bool(Bool)
    case int(Int)
    case double(Double)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])

    /// The member named `key` when this is an object.
    public subscript(key: String) -> JSONValue? {
        if case .object(let object) = self { return object[key] }
        return nil
    }

    var string: String? { if case .string(let value) = self { value } else { nil } }
    var bool: Bool? { if case .bool(let value) = self { value } else { nil } }
    var array: [JSONValue]? { if case .array(let value) = self { value } else { nil } }
    var object: [String: JSONValue]? { if case .object(let value) = self { value } else { nil } }
    var int: Int? {
        if case .int(let value) = self { value } else if case .double(let value) = self { Int(exactly: value) } else { nil }
    }
    var double: Double? {
        if case .double(let value) = self { value } else if case .int(let value) = self { Double(value) } else { nil }
    }
}

extension JSONValue: Codable {
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() { self = .null }
        else if let value = try? container.decode(Bool.self) { self = .bool(value) }
        else if let value = try? container.decode(Int.self) { self = .int(value) }
        else if let value = try? container.decode(Double.self) { self = .double(value) }
        else if let value = try? container.decode(String.self) { self = .string(value) }
        else if let value = try? container.decode([JSONValue].self) { self = .array(value) }
        else { self = .object(try container.decode([String: JSONValue].self)) }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .null: try container.encodeNil()
        case .bool(let value): try container.encode(value)
        case .int(let value): try container.encode(value)
        case .double(let value): try container.encode(value)
        case .string(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        }
    }
}

extension JSONValue: ExpressibleByNilLiteral, ExpressibleByBooleanLiteral, ExpressibleByIntegerLiteral,
    ExpressibleByFloatLiteral, ExpressibleByStringLiteral, ExpressibleByArrayLiteral,
    ExpressibleByDictionaryLiteral
{
    public init(nilLiteral: ()) { self = .null }
    public init(booleanLiteral value: Bool) { self = .bool(value) }
    public init(integerLiteral value: Int) { self = .int(value) }
    public init(floatLiteral value: Double) { self = .double(value) }
    public init(stringLiteral value: String) { self = .string(value) }
    public init(arrayLiteral elements: JSONValue...) { self = .array(elements) }
    public init(dictionaryLiteral elements: (String, JSONValue)...) {
        self = .object(Dictionary(elements, uniquingKeysWith: { _, last in last }))
    }
}

/// The `input` of a request: one user message, or the conversation so far as items, oldest first.
public enum Input: Sendable, Hashable, ExpressibleByStringLiteral, ExpressibleByArrayLiteral {
    /// The text of one user message.
    case text(String)
    /// The conversation so far: messages, the `output` items of earlier responses and the outputs of their function calls.
    case items([InputItem])

    /// The text of one user message.
    public init(stringLiteral value: String) { self = .text(value) }
    /// The items in order.
    public init(arrayLiteral elements: InputItem...) { self = .items(elements) }

    var json: JSONValue {
        switch self {
        case .text(let text): .string(text)
        case .items(let items): .array(items.map(\.json))
        }
    }
}

/// One item of `input`.
public enum InputItem: Sendable, Hashable {
    /// A system message.
    case system(String)
    /// A developer message, which ranks below a system message.
    case developer(String)
    /// A user message.
    case user(String)
    /// An earlier message of the model, as text.
    case assistant(String)
    /// The output of the function call whose `callId` this is.
    case functionCallOutput(callId: String, output: String)
    /// Any other item as its JSON object.
    case raw([String: JSONValue])

    /// An `output` item of an earlier response, sent back as it came, with every field the model sent.
    public init(_ item: OutputItem) { self = .raw(item.raw) }

    var json: JSONValue {
        switch self {
        case .system(let text): ["role": "system", "content": .string(text)]
        case .developer(let text): ["role": "developer", "content": .string(text)]
        case .user(let text): ["role": "user", "content": .string(text)]
        case .assistant(let text): ["role": "assistant", "content": .string(text)]
        case .functionCallOutput(let callId, let output): ["type": "function_call_output", "call_id": .string(callId), "output": .string(output)]
        case .raw(let object): .object(object)
        }
    }
}

/// A tool the model may use: a function you run, an MCP server the gateway calls, or any other entry as JSON.
public enum Tool: Sendable, Hashable {
    /// A function you run. `parameters` is its JSON Schema, and `strict` asks the model to follow it exactly.
    case function(name: String, description: String? = nil, parameters: [String: JSONValue]? = nil, strict: Bool? = nil)
    /// An MCP server whose tools the gateway calls.
    case mcp(McpServer)
    /// Any other `tools` entry, sent and printed as it is, so MCP credentials belong in `.mcp(server)`.
    case raw([String: JSONValue])

    var json: JSONValue {
        switch self {
        case .function(let name, let description, let parameters, let strict):
            var function: [String: JSONValue] = ["type": "function", "name": .string(name)]
            function["description"] = description.map(JSONValue.string)
            function["parameters"] = parameters.map(JSONValue.object)
            function["strict"] = strict.map(JSONValue.bool)
            return .object(function)
        case .mcp(let server): return server.json
        case .raw(let object): return .object(object)
        }
    }
}

/// Whether and how the model calls tools.
public enum ToolChoice: Sendable, Hashable {
    /// `auto` lets the model choose, `never` forbids a tool call and sends `none`, and `required` needs at least one.
    case auto, never, required
    /// The function with this name, which the model must call.
    case function(String)
    /// Any other `tool_choice` object, sent as it is.
    case raw([String: JSONValue])

    /// Spelled `.never`, since `.none` on a `ToolChoice?` is `nil` and sends no `tool_choice`.
    @available(*, unavailable, renamed: "never")
    public static var none: ToolChoice { .never }

    var json: JSONValue {
        switch self {
        case .auto: "auto"
        case .never: "none"
        case .required: "required"
        case .function(let name): ["type": "function", "name": .string(name)]
        case .raw(let object): .object(object)
        }
    }
}

/// An MCP server the gateway calls, given in `tools` as `.mcp(server)`.
/// Its URL and `headers` can hold your credentials, so `description`, `debugDescription`
/// and `dump` show only the label and how many headers there are, never their names or values.
public struct McpServer: Sendable, Hashable, CustomStringConvertible, CustomDebugStringConvertible, CustomReflectable {
    /// How the gateway talks to the server.
    public enum Transport: String, Sendable, Hashable {
        case streamableHTTP = "streamable_http", sse
    }

    /// The server's name, which its `mcp_call` items carry.
    public let serverLabel: String
    /// The URL the gateway reaches the server at.
    public let serverURL: String
    /// Headers the gateway sends to the server, such as `Authorization`.
    public let headers: [String: String]?
    /// The server's tools the model may call, or all of them when `nil`.
    public let allowedTools: [String]?
    /// `streamableHTTP`, the gateway's default, or `sse`.
    public let transport: Transport?

    /// Holds the fields as given.
    public init(
        serverLabel: String, serverURL: String, headers: [String: String]? = nil, allowedTools: [String]? = nil, transport: Transport? = nil
    ) {
        self.serverLabel = serverLabel
        self.serverURL = serverURL
        self.headers = headers
        self.allowedTools = allowedTools
        self.transport = transport
    }

    /// The label and how many headers there are.
    public var description: String { "McpServer(serverLabel: \(serverLabel), headers: \(headers?.count ?? 0))" }
    /// The same as `description`.
    public var debugDescription: String { description }
    /// The label and how many headers there are, for `dump`.
    public var customMirror: Mirror { Mirror(self, children: ["serverLabel": serverLabel, "headers": headers?.count ?? 0]) }

    var json: JSONValue {
        var object: [String: JSONValue] = ["type": "mcp", "server_label": .string(serverLabel), "server_url": .string(serverURL)]
        object["headers"] = headers.map { .object($0.mapValues(JSONValue.string)) }
        object["allowed_tools"] = allowedTools.map { .array($0.map(JSONValue.string)) }
        object["transport"] = transport.map { .string($0.rawValue) }
        return .object(object)
    }
}

/// A failed inference call.
///
/// `status` is the HTTP status, `nil` when the call failed before a response or mid-stream.
/// `type` is the gateway's error type, such as `capacity` or `mcp_error`, or else one of `authentication_error`,
/// `permission_error`, `not_found_error`, `rate_limit_error`, `invalid_request_error` for another 4xx or an argument
/// refused, `server_error` for a 3xx or 5xx, `model_error` for a `response.failed` without a type or an `error` event,
/// `connection_error` for a transport failure, `timeout` for a passed limit, or `incomplete_stream` when the stream
/// ends before `response.completed`.
public struct InferenceError: LocalizedError, Sendable, Hashable {
    public let status: Int?
    public let type: String
    public let message: String
    /// The gateway's error `code`, with an integer code as its decimal text, or `failed_after_tool_call`
    /// for any failure once an MCP call has arrived, since a tool may have changed data and the call should not be replayed.
    public internal(set) var code: String?
    /// The gateway's `X-Moss-Request-Id` for the call, once a response has arrived.
    public let requestId: String?
    /// The seconds to wait before trying again, from the `Retry-After` header of an error response.
    public let retryAfter: TimeInterval?
    /// The task of a failed `tasks.wait`, or of a `tasks.run` that failed after its create,
    /// so you can still wait on, cancel or read it. Any other call leaves it `nil`.
    public internal(set) var taskId: String?

    public var errorDescription: String? { message }

    init(status: Int?, type: String, message: String, code: String? = nil, requestId: String? = nil, retryAfter: TimeInterval? = nil) {
        self.status = status
        self.type = type
        self.message = message
        self.code = code
        self.requestId = requestId
        self.retryAfter = retryAfter
    }
}

extension InferenceError {
    /// Maps a response that is not 2xx, whose body is JSON in one of the gateway's shapes or anything else,
    /// which becomes the message with its whitespace collapsed and cut to 300 characters, unless it is empty.
    init(response: HTTPURLResponse?, body: Data) {
        let status = response?.statusCode ?? 0
        let json = try? JSONDecoder().decode(JSONValue.self, from: body)
        let error = json?["error"]
        let detail = json?["detail"].map { $0.string ?? String(decoding: (try? JSONEncoder().encode($0)) ?? Data(), as: UTF8.self) }
        let text = String(decoding: body, as: UTF8.self).split(whereSeparator: \.isWhitespace).joined(separator: " ")
        let statusLine = "HTTP \(status) \(HTTPURLResponse.localizedString(forStatusCode: status))"
        let fallback = json != nil || text.isEmpty ? statusLine : text.count > 300 ? String(text.prefix(297)) + "..." : text
        self.init(
            status: status,
            type: error?["type"]?.string ?? Self.type(forStatus: status),
            message: error?["message"]?.string ?? error?.string ?? detail ?? fallback,
            code: Self.code(body, at: ["error"]),
            requestId: response?.requestId,
            retryAfter: response?.retryAfter
        )
    }

    /// The `code` of the error object at `path` in the JSON `body`: a string as it is,
    /// an integer as its decimal text, and `nil` for a fraction, an exponent, a boolean or anything else.
    static func code(_ body: Data, at path: [String]) -> String? {
        let error = path.reduce(try? JSONSerialization.jsonObject(with: body)) { ($0 as? [String: Any])?[$1] }
        switch (error as? [String: Any])?["code"] {
        case let code as String: return code
        case let code as NSNumber where CFGetTypeID(code) != CFBooleanGetTypeID() && !CFNumberIsFloatType(code): return code.stringValue
        default: return nil
        }
    }

    /// A `Retry-After` value in delta-seconds, a non-negative integer, or `nil` for an HTTP-date or anything else.
    static func seconds(_ retryAfter: String) -> TimeInterval? {
        guard !retryAfter.isEmpty, retryAfter.allSatisfy({ ("0"..."9").contains($0) }) else { return nil }
        return TimeInterval(retryAfter)
    }

    static func type(forStatus status: Int) -> String {
        switch status {
        case 401: "authentication_error"
        case 403: "permission_error"
        case 404: "not_found_error"
        case 429: "rate_limit_error"
        case 400..<500: "invalid_request_error"
        default: "server_error"
        }
    }

    static func invalidRequest(_ message: String) -> InferenceError {
        InferenceError(status: nil, type: "invalid_request_error", message: message)
    }
}

extension HTTPURLResponse {
    /// The `X-Moss-Request-Id` header, or `nil` when it is missing or empty.
    var requestId: String? { value(forHTTPHeaderField: "X-Moss-Request-Id").flatMap { $0.isEmpty ? nil : $0 } }
    /// The `Retry-After` header in seconds, or `nil` unless it is delta-seconds.
    var retryAfter: TimeInterval? { value(forHTTPHeaderField: "Retry-After").flatMap(InferenceError.seconds) }
}

/// A whole response, the `response` of the stream's last event.
///
/// `status` is `completed`, or `incomplete` for a response cut short, as by `maxOutputTokens`, which
/// `incompleteDetails` explains. `raw` is the response as it came, with the fields the typed properties leave out,
/// such as `instructions` and `metadata`.
public struct Response: Sendable, Hashable {
    /// The response object as the gateway sent it.
    public let raw: [String: JSONValue]
    /// The items of the response in order, which go back into the next request's `input` as `InputItem(item)`.
    public let output: [OutputItem]
    /// The gateway's `X-Moss-Request-Id` for the call, or `nil` when the response has none.
    public let requestId: String?
    /// The response's id, such as `resp_1`.
    public var id: String { raw["id"]?.string ?? "" }
    /// When the response was made, in seconds since 1970.
    public var createdAt: TimeInterval { raw["created_at"]?.double ?? 0 }
    /// `in_progress` on the first event, then `completed` or `incomplete`.
    public var status: String? { raw["status"]?.string }
    /// The model that answered.
    public var model: String { raw["model"]?.string ?? "" }
    /// The token counts, once the response has ended.
    public var usage: Usage? { raw["usage"]?.object.map(Usage.init(raw:)) }
    /// Why the response is `incomplete`, or `nil` when it is not.
    public var incompleteDetails: IncompleteDetails? { raw["incomplete_details"]?.object.map(IncompleteDetails.init(raw:)) }
    /// The text of every message in `output`, joined.
    public var outputText: String { output.map { if case .message(let message) = $0 { message.text } else { "" } }.joined() }

    init(raw: [String: JSONValue], requestId: String?) {
        self.raw = raw
        self.requestId = requestId
        output = (raw["output"]?.array ?? []).compactMap { $0.object.map(OutputItem.init) }
    }
}

/// Token counts of a response.
public struct Usage: Sendable, Hashable {
    /// The usage object as the gateway sent it, with every field, such as Moss's own.
    public let raw: [String: JSONValue]
    /// The tokens of the prompt.
    public var inputTokens: Int { raw["input_tokens"]?.int ?? 0 }
    /// The tokens of the response.
    public var outputTokens: Int { raw["output_tokens"]?.int ?? 0 }
    /// The input and output tokens together.
    public var totalTokens: Int { raw["total_tokens"]?.int ?? 0 }
    /// The input tokens the provider read from its cache, when the gateway counts them.
    public var cachedTokens: Int? { raw["input_tokens_details"]?["cached_tokens"]?.int }
    /// The output tokens the model spent reasoning, when the gateway counts them.
    public var reasoningTokens: Int? { raw["output_tokens_details"]?["reasoning_tokens"]?.int }
}

/// Why a response is `incomplete`.
public struct IncompleteDetails: Sendable, Hashable {
    /// The object as the gateway sent it.
    public let raw: [String: JSONValue]
    /// `max_output_tokens` or `content_filter`.
    public var reason: String? { raw["reason"]?.string }
}

/// An item of a response's `output`. Its `raw` is the item as it came, which `InputItem(item)` sends back.
public enum OutputItem: Sendable, Hashable {
    /// A message of the model.
    case message(OutputMessage)
    /// A call of one of your functions.
    case functionCall(FunctionCall)
    /// A call that Moss ran on one of your MCP servers.
    case mcpCall(McpCall)
    /// An item of another type, such as `reasoning`, as its JSON object.
    case other([String: JSONValue])

    init(_ raw: [String: JSONValue]) {
        switch raw["type"]?.string {
        case "message": self = .message(OutputMessage(raw: raw))
        case "function_call": self = .functionCall(FunctionCall(raw: raw))
        case "mcp_call": self = .mcpCall(McpCall(raw: raw))
        default: self = .other(raw)
        }
    }

    /// The item as it came, with every field the model sent.
    public var raw: [String: JSONValue] {
        switch self {
        case .message(let item): item.raw
        case .functionCall(let item): item.raw
        case .mcpCall(let item): item.raw
        case .other(let raw): raw
        }
    }
}

/// A message of the model, an item of `output`.
public struct OutputMessage: Sendable, Hashable {
    /// The item as it came.
    public let raw: [String: JSONValue]
    /// The item's id, which the events about it carry as `itemId`.
    public var id: String { raw["id"]?.string ?? "" }
    /// `assistant`.
    public var role: String { raw["role"]?.string ?? "assistant" }
    /// `in_progress`, `completed` or `incomplete`.
    public var status: String? { raw["status"]?.string }
    /// The parts of the message, such as an `output_text` part with its `text` and `annotations`.
    public var content: [JSONValue] { raw["content"]?.array ?? [] }
    /// The text of its `output_text` parts, joined.
    public var text: String { content.filter { $0["type"] == "output_text" }.compactMap { $0["text"]?.string }.joined() }
}

/// A call of one of your functions, an item of `output`.
///
/// Run the function, then send this item back as `InputItem(item)` and its result as
/// `.functionCallOutput(callId:output:)` in the `input` of the next request. `raw` keeps
/// every field the model sent, such as the thought signature Gemini needs in `extra_content`.
public struct FunctionCall: Sendable, Hashable {
    /// The item as it came.
    public let raw: [String: JSONValue]
    /// The item's id, such as `fc_1`.
    public var id: String { raw["id"]?.string ?? "" }
    /// The id that the call's `functionCallOutput` names.
    public var callId: String { raw["call_id"]?.string ?? "" }
    /// The function's name.
    public var name: String { raw["name"]?.string ?? "" }
    /// The arguments as JSON text.
    public var arguments: String { raw["arguments"]?.string ?? "" }
    /// `in_progress` or `completed`.
    public var status: String? { raw["status"]?.string }
}

/// A call that Moss ran on one of your MCP servers, an item of `output`.
/// Sent back in `input` as it is, it gives the model the earlier tool result.
public struct McpCall: Sendable, Hashable {
    /// The item as it came.
    public let raw: [String: JSONValue]
    /// The item's id.
    public var id: String { raw["id"]?.string ?? "" }
    /// The `serverLabel` of the tool's server.
    public var serverLabel: String { raw["server_label"]?.string ?? "" }
    /// The tool's name on its server.
    public var name: String { raw["name"]?.string ?? "" }
    /// The arguments as JSON text.
    public var arguments: String { raw["arguments"]?.string ?? "" }
    /// The tool's output, once it succeeded.
    public var output: String? { raw["output"]?.string }
    /// What failed, once the tool failed.
    public var error: JSONValue? {
        guard let error = raw["error"], error != .null else { return nil }
        return error
    }
    /// `in_progress`, `completed` or `failed`.
    public var status: String? { raw["status"]?.string }
    /// How long the tool ran in milliseconds, once it ended.
    public var durationMs: Double? { raw["duration_ms"]?.double }
}

/// One event of a streamed response, such as `response.output_text.delta`, with OpenAI's fields.
///
/// Each type of event sets its own fields and leaves the others `nil`: `delta` on a delta,
/// `item` on `response.output_item.added` and `.done`, and `response` on `response.created`,
/// `response.completed` and `response.incomplete`. `raw` is the decoded event, with every field.
public struct ResponseStreamEvent: Sendable, Hashable {
    /// The event as the gateway sent it.
    public let raw: [String: JSONValue]
    /// The response so far, or the whole response on the last event.
    public let response: Response?
    /// The output item that the event adds or finishes.
    public let item: OutputItem?
    /// The event's type, such as `response.output_text.delta`.
    public var type: String { raw["type"]?.string ?? "" }
    /// The event's place in the stream, counted from 0.
    public var sequenceNumber: Int? { raw["sequence_number"]?.int }
    /// The place in `output` of the item the event is about.
    public var outputIndex: Int? { raw["output_index"]?.int }
    /// The id of the item the event is about.
    public var itemId: String? { raw["item_id"]?.string }
    /// The place in the message's `content` of the part the event is about.
    public var contentIndex: Int? { raw["content_index"]?.int }
    /// The new text, or the new piece of a call's arguments.
    public var delta: String? { raw["delta"]?.string }
    /// The whole text of a part, on `response.output_text.done`.
    public var text: String? { raw["text"]?.string }
    /// The whole arguments of a call, on `response.function_call_arguments.done`.
    public var arguments: String? { raw["arguments"]?.string }

    init(raw: [String: JSONValue], requestId: String?) {
        self.raw = raw
        response = raw["response"]?.object.map { Response(raw: $0, requestId: requestId) }
        item = raw["item"]?.object.map(OutputItem.init)
    }
}
