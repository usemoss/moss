import Foundation

/// Where a task runs. A browser is the only environment for now.
public struct TaskEnvironment: Sendable, Hashable {
    /// The environment as JSON, as sent or as the gateway sent it.
    public let raw: [String: JSONValue]
    /// `browser`.
    public var type: String { raw["type"]?.string ?? "" }
    /// The page the browser opens first.
    public var startURL: String? { raw["start_url"]?.string }
    /// Whether the task has a `liveURL` to watch the browser while it runs.
    public var liveView: Bool? { raw["live_view"]?.bool }

    init(raw: [String: JSONValue]) { self.raw = raw }

    /// A browser that opens `startURL` first. `liveView` asks for a `liveURL` to watch it while the task runs.
    public static func browser(startURL: String? = nil, liveView: Bool? = nil) -> TaskEnvironment {
        var raw: [String: JSONValue] = ["type": "browser"]
        raw["start_url"] = startURL.map(JSONValue.string)
        raw["live_view"] = liveView.map(JSONValue.bool)
        return TaskEnvironment(raw: raw)
    }
}

/// The limits of a task. The gateway sets the ones a request leaves out.
public struct TaskLimits: Sendable, Hashable {
    /// The limits as JSON, as sent or as the gateway sent them.
    public let raw: [String: JSONValue]
    /// The longest the task may run, in seconds.
    public var maxRuntimeSeconds: TimeInterval? { raw["max_runtime_seconds"]?.double }
    /// The most the task may spend, in US dollars.
    public var maxCostUSD: Double? { raw["max_cost_usd"]?.double }

    init(raw: [String: JSONValue]) { self.raw = raw }

    /// Holds the limits given. A limit left out is not sent.
    public init(maxRuntimeSeconds: TimeInterval? = nil, maxCostUSD: Double? = nil) {
        var raw: [String: JSONValue] = [:]
        raw["max_runtime_seconds"] = maxRuntimeSeconds.map(JSONValue.double)
        raw["max_cost_usd"] = maxCostUSD.map(JSONValue.double)
        self.raw = raw
    }
}

/// How hard the agent works on a task.
public enum TaskEffort: String, Sendable, Hashable {
    case low, medium, high
}

/// A task, as the gateway sent it.
///
/// `status` is `queued` or `running` until it ends `completed`, `failed` or `cancelled`,
/// or it is a status that a newer gateway adds. The SDK does not check `result`: `verification`
/// says whether it matched `outputSchema`. `raw` is the task as it came, with the fields these properties leave out.
/// Swift's concurrency type is `Task`, so this one is `MossTask`.
public struct MossTask: Sendable, Hashable {
    /// The task object as the gateway sent it.
    public let raw: [String: JSONValue]
    /// Such as `task_...`.
    public var id: String { raw["id"]?.string ?? "" }
    /// `task`.
    public var object: String { raw["object"]?.string ?? "" }
    /// `queued`, `running`, `completed`, `failed` or `cancelled`.
    public var status: String { raw["status"]?.string ?? "" }
    /// What the agent should do, in plain words.
    public var goal: String { raw["goal"]?.string ?? "" }
    /// Where the task runs.
    public var environment: TaskEnvironment { TaskEnvironment(raw: raw["environment"]?.object ?? [:]) }
    /// The JSON Schema that `result.output` should match, when the task has one.
    public var outputSchema: [String: JSONValue]? { raw["output_schema"]?.object }
    /// The limits the task runs with, the gateway's own where the request left one out.
    public var limits: TaskLimits { TaskLimits(raw: raw["limits"]?.object ?? [:]) }
    /// The model of the Moss catalog that runs the task.
    public var model: String? { raw["model"]?.string }
    /// `low`, `medium` or `high`.
    public var effort: String? { raw["effort"]?.string }
    /// Your own data, sent back as given.
    public var metadata: [String: JSONValue]? { raw["metadata"]?.object }
    /// The answer once the task ends. A failed or cancelled task can have one too.
    public var result: TaskResult? { raw["result"]?.object.map(TaskResult.init(raw:)) }
    /// How the answer was checked, once it was.
    public var verification: TaskVerification? { raw["verification"]?.object.map(TaskVerification.init(raw:)) }
    /// What the task used so far.
    public var usage: TaskUsage? { raw["usage"]?.object.map(TaskUsage.init(raw:)) }
    /// Why the task failed, once it did.
    public var error: TaskError? { raw["error"]?.object.map(TaskError.init(raw:)) }
    /// Whether `tasks.trace` has the agent's record.
    public var traceAvailable: Bool { raw["trace_available"]?.bool ?? false }
    /// A link to watch the browser while the task runs, with `liveView`.
    public var liveURL: String? { raw["live_url"]?.string }
    /// Whether a cancel waits for the running task to stop.
    public var cancelRequested: Bool { raw["cancel_requested"]?.bool ?? false }
    /// When the task was queued, as ISO 8601 text.
    public var createdAt: String? { raw["created_at"]?.string }
    /// When the task started to run, as ISO 8601 text.
    public var startedAt: String? { raw["started_at"]?.string }
    /// When the task ended, as ISO 8601 text.
    public var finishedAt: String? { raw["finished_at"]?.string }
    /// When the gateway removes the trace and files, 7 days after the task ends, as ISO 8601 text.
    public var filesExpireAt: String? { raw["files_expire_at"]?.string }
}

/// The agent's answer, with `output` as the JSON that `outputSchema` asked for.
public struct TaskResult: Sendable, Hashable {
    /// The result as the gateway sent it.
    public let raw: [String: JSONValue]
    /// The answer as text.
    public var outputText: String { raw["output_text"]?.string ?? "" }
    /// The answer as JSON, or `nil` when there is none.
    public var output: JSONValue? {
        guard let output = raw["output"], output != .null else { return nil }
        return output
    }

    /// `output` decoded as `type`, or `nil` when there is none.
    /// The SDK does not check it, so this throws the decoder's error when it does not fit.
    public func decodeOutput<Output: Decodable>(_ type: Output.Type, using decoder: JSONDecoder = JSONDecoder()) throws -> Output? {
        guard let output else { return nil }
        return try decoder.decode(type, from: JSONEncoder().encode(output))
    }
}

/// How the answer was checked: by the agent itself, or against `outputSchema`.
public struct TaskVerification: Sendable, Hashable {
    /// The verification as the gateway sent it.
    public let raw: [String: JSONValue]
    /// `agent_reported` or `output_schema`.
    public var method: String { raw["method"]?.string ?? "" }
    /// `false` when the answer does not match `outputSchema`, `nil` when only the agent checked it.
    public var passed: Bool? { raw["passed"]?.bool }
    /// What does not match, when `passed` is `false`.
    public var problems: [String]? { raw["problems"]?.array?.compactMap(\.string) }
}

/// What a task used. `raw` holds every field the gateway sent, such as `steps` and `browser_minutes`.
public struct TaskUsage: Sendable, Hashable {
    /// The usage as the gateway sent it.
    public let raw: [String: JSONValue]
    /// The calls to the model.
    public var modelCalls: Int { raw["model_calls"]?.int ?? 0 }
    /// The tokens of the prompts.
    public var inputTokens: Int { raw["input_tokens"]?.int ?? 0 }
    /// The input tokens the provider read from its cache.
    public var cachedInputTokens: Int { raw["cached_input_tokens"]?.int ?? 0 }
    /// The tokens the model wrote.
    public var outputTokens: Int { raw["output_tokens"]?.int ?? 0 }
    /// What the task cost, in US dollars.
    public var costUSD: Double { raw["cost_usd"]?.double ?? 0 }
}

/// Why a task failed, with a `code` such as `time_limit` or `budget_exceeded`.
public struct TaskError: Sendable, Hashable {
    /// The error as the gateway sent it.
    public let raw: [String: JSONValue]
    /// Such as `time_limit` or `budget_exceeded`.
    public var code: String { raw["code"]?.string ?? "" }
    /// What went wrong, in plain words.
    public var message: String { raw["message"]?.string ?? "" }
}

/// A file of a task, such as a screenshot.
public struct TaskFile: Sendable, Hashable {
    /// The file as the gateway sent it.
    public let raw: [String: JSONValue]
    /// The path for `tasks.files.content`, such as `screenshots/step-1.png`.
    public var path: String { raw["path"]?.string ?? "" }
    /// The size in bytes.
    public var bytes: Int { raw["bytes"]?.int ?? 0 }
}

/// The files of a task.
public struct TaskFileList: Sendable, Hashable {
    /// The list as the gateway sent it.
    public let raw: [String: JSONValue]
    /// `list`.
    public var object: String { raw["object"]?.string ?? "" }
    /// The files, each with the `path` that `tasks.files.content` takes.
    public var data: [TaskFile] { (raw["data"]?.array ?? []).compactMap { $0.object.map(TaskFile.init(raw:)) } }
}

/// The bytes of a task's file and their media type. The SDK never opens or renders a file.
public struct TaskFileContent: Sendable, Hashable {
    /// The bytes of the file.
    public let data: Data
    /// The `Content-Type` the gateway sent, `application/octet-stream` when it sent none.
    public let contentType: String
}
