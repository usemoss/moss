import Foundation

extension MossInference {
    /// Browser tasks: an agent works toward a goal in a browser on Moss, within time and dollar limits.
    ///
    /// `run` creates a task and waits until it ends, as `create` and then `wait` do,
    /// and `retrieve`, `cancel`, `trace` and `files` read or stop a task. `create` and `run` send only
    /// their own `apiKey` as `X-Moss-Provider-Key`, for the task's model calls; see the pricing docs.
    /// Tasks never use the client's `apiKey`, and the other task calls never send a key.
    /// `timeout`, `idleTimeout` and `maxRetries` replace the client's for one call, as they do for `responses`,
    /// but the `timeout` of `run` and `wait` limits the whole wait. A failed call throws `InferenceError`.
    /// Task calls retry as `responses` does, but never after a 409.
    public struct Tasks: Sendable {
        let client: MossInference

        /// The screenshots and output files of a task, ready once it ends.
        public var files: Files { Files(client: client) }

        /// Queues a task and returns it, `queued`.
        ///
        /// Only the parameters you give are sent, so the gateway picks the model, effort and limits you leave out,
        /// and it refuses a field it does not know. Each one wins over the same key in `extra`, which holds any other field.
        /// Each create sends an `Idempotency-Key`, a new one per call or `idempotencyKey`, and the same one on every retry.
        /// The gateway answers a repeated key with the same body, within 24 hours, with the task it created,
        /// so a retried create never starts a second task. To retry a create yourself, pass your own key.
        /// `apiKey` is sent for the task's model calls, and an empty one is refused. The client's `apiKey` is never used.
        public func create(
            goal: String,
            environment: TaskEnvironment,
            outputSchema: [String: JSONValue]? = nil,
            limits: TaskLimits? = nil,
            model: String? = nil,
            effort: TaskEffort? = nil,
            metadata: [String: JSONValue]? = nil,
            idempotencyKey: String? = nil,
            apiKey: String? = nil,
            timeout: TimeInterval? = nil,
            idleTimeout: TimeInterval? = nil,
            maxRetries: Int? = nil,
            extra: [String: JSONValue] = [:]
        ) async throws -> MossTask {
            try apiKey.map { try MossInference.checkValue("apiKey", $0) }
            var body = extra
            body["goal"] = .string(goal)
            body["environment"] = .object(environment.raw)
            if let outputSchema { body["output_schema"] = .object(outputSchema) }
            if let limits { body["limits"] = .object(limits.raw) }
            if let model { body["model"] = .string(model) }
            if let effort { body["effort"] = .string(effort.rawValue) }
            if let metadata { body["metadata"] = .object(metadata) }
            let reply = try await client.fetch(
                "POST", "/tasks", body: body, idempotencyKey: idempotencyKey, apiKey: apiKey, timeout: timeout,
                idleTimeout: idleTimeout, maxRetries: maxRetries
            )
            return MossTask(raw: try reply.object())
        }

        /// Fetches a task by its id.
        public func retrieve(
            _ taskId: String, timeout: TimeInterval? = nil, idleTimeout: TimeInterval? = nil, maxRetries: Int? = nil
        ) async throws -> MossTask {
            let path = try MossInference.taskPath(taskId)
            let reply = try await client.fetch("GET", path, timeout: timeout, idleTimeout: idleTimeout, maxRetries: maxRetries)
            return MossTask(raw: try reply.object())
        }

        /// Stops a task. A queued task comes back `cancelled`.
        /// A running one comes back with `cancelRequested` and ends `cancelled` soon after.
        public func cancel(
            _ taskId: String, timeout: TimeInterval? = nil, idleTimeout: TimeInterval? = nil, maxRetries: Int? = nil
        ) async throws -> MossTask {
            let path = try MossInference.taskPath(taskId) + "/cancel"
            let reply = try await client.fetch("POST", path, timeout: timeout, idleTimeout: idleTimeout, maxRetries: maxRetries)
            return MossTask(raw: try reply.object())
        }

        /// Polls a task every `pollInterval` seconds until it is neither `queued` nor `running`, and returns it.
        ///
        /// A `failed` or `cancelled` task returns too, so read its `status` and `error`.
        /// Each poll is a `retrieve` limited by the time left in the wait, or by the client's `timeout` when shorter.
        /// `timeout` limits the whole wait and is off by default. Past it, this throws `InferenceError` of type `timeout`,
        /// and the task goes on: wait again or cancel it. Every `InferenceError` it throws names the task in `taskId`.
        /// Cancelling the Swift task that waits throws `CancellationError`.
        public func wait(
            _ taskId: String, timeout: TimeInterval? = nil, pollInterval: TimeInterval = 2, idleTimeout: TimeInterval? = nil,
            maxRetries: Int? = nil
        ) async throws -> MossTask {
            let waiting = try Waiting(timeout: timeout, pollInterval: pollInterval)
            return try await poll(taskId, waiting, idleTimeout: idleTimeout, maxRetries: maxRetries)
        }

        /// Creates a task and waits for it, as `create` and then `wait` do, and returns it once it ends.
        ///
        /// `timeout` and `pollInterval` apply to the wait. They are checked before the create, so a bad one sends nothing.
        /// `idleTimeout` and `maxRetries` apply to every call, and the other parameters are those of `create`.
        /// Once the task exists, every `InferenceError` it throws names the task in `taskId`.
        public func run(
            goal: String,
            environment: TaskEnvironment,
            outputSchema: [String: JSONValue]? = nil,
            limits: TaskLimits? = nil,
            model: String? = nil,
            effort: TaskEffort? = nil,
            metadata: [String: JSONValue]? = nil,
            idempotencyKey: String? = nil,
            apiKey: String? = nil,
            timeout: TimeInterval? = nil,
            pollInterval: TimeInterval = 2,
            idleTimeout: TimeInterval? = nil,
            maxRetries: Int? = nil,
            extra: [String: JSONValue] = [:]
        ) async throws -> MossTask {
            let waiting = try Waiting(timeout: timeout, pollInterval: pollInterval)
            let task = try await create(
                goal: goal, environment: environment, outputSchema: outputSchema, limits: limits, model: model, effort: effort,
                metadata: metadata, idempotencyKey: idempotencyKey, apiKey: apiKey, idleTimeout: idleTimeout, maxRetries: maxRetries,
                extra: extra
            )
            return try await poll(task.id, waiting, idleTimeout: idleTimeout, maxRetries: maxRetries)
        }

        /// Reads `taskId` every `waiting.pollInterval` until the task ends.
        /// Each read has the time left in the wait as its `timeout`, or the client's when shorter.
        /// Once `waiting.limit` has passed, or a read is cut off at it, this throws `InferenceError` of type `timeout`.
        /// A bad `taskId` throws before the first read, and every later `InferenceError` names the task in `taskId`.
        private func poll(_ taskId: String, _ waiting: Waiting, idleTimeout: TimeInterval?, maxRetries: Int?) async throws -> MossTask {
            _ = try MossInference.taskPath(taskId)
            let start = DispatchTime.now()
            let left = { (waiting.limit ?? .infinity) - Double(DispatchTime.now().uptimeNanoseconds - start.uptimeNanoseconds) / 1e9 }
            var status = "unfinished"
            do {
                while true {
                    let bound = waiting.limit.map { _ in max(min(left(), client.timeout ?? .infinity), 0.001) }
                    let task: MossTask
                    do {
                        task = try await retrieve(taskId, timeout: bound, idleTimeout: idleTimeout, maxRetries: maxRetries)
                    } catch let error as InferenceError where error.type == "timeout" && left() <= 0 {
                        throw waiting.expiry(taskId, status)
                    }
                    guard ["queued", "running"].contains(task.status) else { return task }
                    status = task.status
                    let remaining = left()
                    guard remaining > 0 else { throw waiting.expiry(taskId, status) }
                    try await Task.sleep(nanoseconds: UInt64(min(waiting.pollInterval, remaining) * 1e9))
                }
            } catch var error as InferenceError {
                error.taskId = taskId
                throw error
            }
        }

        /// The agent's step-by-step record, the JSON the gateway sent.
        /// It throws `InferenceError` of type `not_found_error` until `traceAvailable` is `true`.
        /// The gateway removes it 7 days after the task ends, at `filesExpireAt`, and from then on it throws a 410 `files_expired`.
        public func trace(
            _ taskId: String, timeout: TimeInterval? = nil, idleTimeout: TimeInterval? = nil, maxRetries: Int? = nil
        ) async throws -> JSONValue {
            let path = try MossInference.taskPath(taskId) + "/trace"
            return try await client.fetch("GET", path, timeout: timeout, idleTimeout: idleTimeout, maxRetries: maxRetries).json()
        }

        /// The screenshots and output files of a task, ready once it ends.
        ///
        /// While the task is queued or running they throw a 409 `task_not_finished`, which is never retried.
        /// The gateway removes them 7 days after the task ends, at its `filesExpireAt`,
        /// and from then on they throw a 410 `files_expired`.
        public struct Files: Sendable {
            let client: MossInference

            /// Lists the files of a task, each with the `path` that `content` takes.
            public func list(
                _ taskId: String, timeout: TimeInterval? = nil, idleTimeout: TimeInterval? = nil, maxRetries: Int? = nil
            ) async throws -> TaskFileList {
                let path = try MossInference.taskPath(taskId) + "/files"
                let reply = try await client.fetch("GET", path, timeout: timeout, idleTimeout: idleTimeout, maxRetries: maxRetries)
                return TaskFileList(raw: try reply.object())
            }

            /// Downloads one file, by a `path` that `list` gave, such as `screenshots/step-1.png`.
            /// It returns the bytes and their media type, and never writes, opens or renders the file.
            public func content(
                _ taskId: String, path: String, timeout: TimeInterval? = nil, idleTimeout: TimeInterval? = nil, maxRetries: Int? = nil
            ) async throws -> TaskFileContent {
                let route = try MossInference.taskPath(taskId) + "/files/" + MossInference.filePath(path)
                let reply = try await client.fetch(
                    "GET", route, accept: "*/*", timeout: timeout, idleTimeout: idleTimeout, maxRetries: maxRetries
                )
                let type = reply.response.value(forHTTPHeaderField: "Content-Type").flatMap { $0.isEmpty ? nil : $0 }
                return TaskFileContent(data: reply.data, contentType: type ?? "application/octet-stream")
            }
        }
    }

    /// Makes one Tasks API call to `path` under the base URL and returns its reply, read to the end.
    /// Only a create has a `body`. It sends an `Idempotency-Key`, `idempotencyKey` or a new one, on every attempt,
    /// and `apiKey` as `X-Moss-Provider-Key`.
    func fetch(
        _ method: String, _ path: String, body: [String: JSONValue]? = nil, accept: String = "application/json", idempotencyKey: String? = nil,
        apiKey: String? = nil, timeout: TimeInterval?, idleTimeout: TimeInterval?, maxRetries: Int?
    ) async throws -> Reply {
        let (timeout, idleTimeout, maxRetries) = try limits(timeout: timeout, idleTimeout: idleTimeout, maxRetries: maxRetries)
        try idempotencyKey.map { try Self.checkValue("idempotencyKey", $0) }
        var request = URLRequest(
            url: try Self.join(base, path), cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: idleTimeout ?? Self.noLimit
        )
        request.httpMethod = method
        request.setValue(authorization, forHTTPHeaderField: "Authorization")
        request.setValue(accept, forHTTPHeaderField: "Accept")
        if let body {
            request.httpBody = try Self.encode(body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue(idempotencyKey ?? UUID().uuidString.lowercased(), forHTTPHeaderField: "Idempotency-Key")
        }
        if let apiKey { request.setValue(apiKey, forHTTPHeaderField: "X-Moss-Provider-Key") }
        let answer = try await Answer.send(
            request, in: session, timeout: timeout, idleTimeout: idleTimeout, maxRetries: maxRetries, statuses: Self.taskRetry
        )
        return try await answer.read()
    }

    /// `body` as JSON, or `invalid_request_error` for a number that JSON cannot carry, such as `.nan`.
    static func encode(_ body: [String: JSONValue]) throws -> Data {
        do { return try JSONEncoder().encode(body) } catch {
            throw InferenceError.invalidRequest("The parameters cannot be sent as JSON: a number in them is not finite")
        }
    }

    /// The 4xx statuses a task call goes again after. A 409 says the task has not finished.
    static let taskRetry: Set<Int> = [408, 429]

    /// Letters, digits and `-._~`, which a path segment keeps as they are.
    static let unreserved = CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")

    /// The path of a task, with its id checked and percent-encoded as one segment.
    static func taskPath(_ taskId: String) throws -> String {
        guard !["", ".", ".."].contains(taskId), let id = taskId.addingPercentEncoding(withAllowedCharacters: unreserved) else {
            throw InferenceError.invalidRequest("taskId must be a task id, such as task_...")
        }
        return "/tasks/" + id
    }

    /// The path of a task's file, each part percent-encoded.
    /// An empty, `.` or `..` part is refused, since it would change the URL.
    static func filePath(_ path: String) throws -> String {
        let parts = path.components(separatedBy: "/")
        let encoded = parts.compactMap { ["", ".", ".."].contains($0) ? nil : $0.addingPercentEncoding(withAllowedCharacters: unreserved) }
        guard encoded.count == parts.count else {
            throw InferenceError.invalidRequest("path must be a path that files.list gave, such as screenshots/step-1.png")
        }
        return encoded.joined(separator: "/")
    }
}

/// The limit of a wait and the pause between its polls, checked before any request.
struct Waiting {
    /// The longest the whole wait may last, `nil` for no limit.
    let limit: TimeInterval?
    /// The seconds between two polls.
    let pollInterval: TimeInterval

    init(timeout: TimeInterval?, pollInterval: TimeInterval) throws {
        limit = try MossInference.limit(timeout, "timeout")
        guard pollInterval > 0, pollInterval.isFinite else {
            throw InferenceError.invalidRequest("pollInterval must be a positive number of seconds")
        }
        self.pollInterval = min(pollInterval, MossInference.noLimit)
    }

    /// The error of a wait that ran past `limit` while the task was still `status`.
    func expiry(_ taskId: String, _ status: String) -> InferenceError {
        let message = "Task \(taskId) is still \(status) after \(limit ?? 0) seconds. It goes on: wait again or cancel it."
        return InferenceError(status: nil, type: "timeout", message: message)
    }
}

/// The body of a Tasks API reply and the response it came in.
struct Reply {
    let data: Data
    let response: HTTPURLResponse

    /// The JSON of the body, or `server_error` when it is not JSON.
    func json() throws -> JSONValue {
        guard let value = try? JSONDecoder().decode(JSONValue.self, from: data) else {
            throw failure("The gateway sent a reply that is not JSON")
        }
        return value
    }

    /// The JSON object of the body, or `server_error` when it is not one.
    func object() throws -> [String: JSONValue] {
        guard let object = try json().object else { throw failure("The gateway sent a reply that is not a JSON object") }
        return object
    }

    private func failure(_ message: String) -> InferenceError {
        InferenceError(status: nil, type: "server_error", message: message, requestId: response.requestId)
    }
}

extension Answer {
    /// Reads the whole body. A passed limit, a cancelled task or a lost connection ends the read with its error.
    func read() async throws -> Reply {
        var data: [UInt8] = []
        do { for try await byte in bytes { data.append(byte) } } catch {
            bytes.task.cancel()
            call.stop()
            throw call.failure(error, requestId: response.requestId)
        }
        call.stop()
        return Reply(data: Data(data), response: response)
    }
}
