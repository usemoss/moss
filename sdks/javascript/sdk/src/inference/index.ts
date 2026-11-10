import { randomUUID } from "node:crypto";
import {
  InferenceError,
  errorFromResponse,
  responseFields,
  transportError,
  type ResponseFields,
} from "./error";
import { ResponseStream, errorText, idleTimer, readBody } from "./stream";
import type {
  InferenceRequestOptions,
  MossInferenceOptions,
  Response as MossResponse,
  ResponseCreateParams,
  ResponseCreateParamsNonStreaming,
  ResponseCreateParamsStreaming,
  Task,
  TaskCreateOptions,
  TaskCreateParams,
  TaskFileContent,
  TaskFileList,
  TaskRequestOptions,
  TaskRunOptions,
  TaskWaitOptions,
} from "./types";

/** The production gateway, up to and including `/v1`. */
const DEFAULT_URL = "https://inference.moss.dev/v1";
const DEFAULT_MODEL = "moss";
const DEFAULT_IDLE_TIMEOUT = 120_000;
const DEFAULT_RETRIES = 2;
/** The longest delay `setTimeout` holds. */
const MAX_DELAY = 2 ** 31 - 1;
/** The longest `Retry-After` a retry waits, in milliseconds. A longer one waits the backoff. */
const MAX_RETRY_AFTER = 60_000;
/** The milliseconds between the polls of `tasks.wait`. */
const DEFAULT_POLL = 2000;

function env(name: string): string | undefined {
  return (typeof process !== "undefined" && process.env[name]) || undefined;
}

function invalid(message: string): InferenceError {
  return new InferenceError(message, { type: "invalid_request_error" });
}

/** `value` as JSON text, or an `invalid_request_error` when it has no JSON form, as with `NaN`. */
function json(value: unknown): string {
  try {
    return JSON.stringify(value, (_key, item: unknown) => {
      if (typeof item === "number" && !Number.isFinite(item))
        throw new TypeError("A number in the parameters is not finite.");
      return item;
    });
  } catch (cause) {
    throw new InferenceError("The parameters cannot be sent as JSON.", {
      type: "invalid_request_error",
      cause,
    });
  }
}

/** Printable Latin-1 with no space or tab at either end, which fetch would trim. */
const HEADER_SAFE = /^(?![\t ])[\t\x20-\x7e\x80-\xff]*(?<![\t ])$/;

/** Returns `value` when a header carries it unchanged. The error names `what`, never the value. */
function headerSafe(what: string, value: unknown): string {
  if (typeof value === "string" && HEADER_SAFE.test(value)) return value;
  throw invalid(`${what} must be printable Latin-1 text without surrounding spaces.`);
}

function credential(what: string, value: unknown): string {
  if (value == null || value === "") throw invalid(`${what} is missing or empty.`);
  return headerSafe(what, value);
}

/** The authority after `http://` or `https://`, up to the path. */
const AUTHORITY = /^https?:\/\/([^/]*)/i;

/**
 * `MOSS_INFERENCE_URL` without its trailing slash, or production when it is unset or empty.
 *
 * `new URL` repairs malformed text, so the text must be printable ASCII
 * that starts with `http://` or `https://`, then a host with no user info or port 0,
 * with no backslash, query or fragment. Anything else throws, naming the variable but not the value.
 */
function baseURL(): string {
  const text = env("MOSS_INFERENCE_URL") ?? DEFAULT_URL;
  const authority = AUTHORITY.exec(text)?.[1];
  let url: URL | undefined;
  try {
    url = new URL(text);
  } catch {
    url = undefined;
  }
  if (
    !/^[!-~]+$/.test(text) ||
    !authority ||
    authority.includes("@") ||
    !url ||
    url.port === "0" ||
    /[\\?#]/.test(text)
  ) {
    throw invalid(
      "MOSS_INFERENCE_URL must be an absolute http or https URL with a host and no user info, query or fragment.",
    );
  }
  return url.href.replace(/\/$/, "");
}

/** Throws when `options` names a gateway URL, which only `MOSS_INFERENCE_URL` sets. */
function refuseURL(options: object): void {
  const { baseURL, baseUrl } = options as {
    baseURL?: unknown;
    baseUrl?: unknown;
  };
  if (baseURL !== undefined || baseUrl !== undefined)
    throw invalid("Set the gateway URL in MOSS_INFERENCE_URL. There is no baseURL option.");
}

/** Headers fetch derives from the URL and the body. */
const FETCH_HEADERS = ["host", "content-length", "transfer-encoding"];

function headersOf(init: Record<string, string> | undefined): Headers {
  let headers: Headers;
  try {
    headers = new Headers(init);
  } catch {
    throw invalid("The headers option holds a name or value a header cannot carry.");
  }
  if (FETCH_HEADERS.some((name) => headers.has(name)))
    throw invalid("Host, Content-Length and Transfer-Encoding cannot be set.");
  for (const [name, value] of headers) headerSafe(`The ${name} header`, value);
  return headers;
}

/** Milliseconds for a timer, or null for no limit. */
function delay(what: string, value: unknown): number | null {
  if (value === null || value === Infinity) return null;
  if (typeof value === "number" && value > 0 && value < Infinity) return Math.min(value, MAX_DELAY);
  throw invalid(`${what} must be a positive number of milliseconds, or null for no limit.`);
}

/** A retry count, a whole number of 0 or more. */
function retries(value: unknown): number {
  if (typeof value === "number" && Number.isSafeInteger(value) && value >= 0) return value;
  throw invalid("maxRetries must be a whole number of 0 or more.");
}

/** The statuses below 500 that a call may send again after. */
const RETRY_STATUSES = [408, 409, 429];
/** The same for a task call, which leaves out the 409 that the files routes send until a task ends. */
const TASK_RETRY_STATUSES = [408, 429];

/**
 * True when a failed response may be sent again.
 * Its `x-should-retry` decides when present, else one of `statuses` or a 5xx does.
 */
function retryable(response: Response, statuses: number[]): boolean {
  const header = response.headers.get("x-should-retry");
  if (header === "true" || header === "false") return header === "true";
  return statuses.includes(response.status) || response.status >= 500;
}

/** `error` with the task it concerns, when it is an {@link InferenceError} that names none. */
function withTask(error: unknown, taskId: string): unknown {
  if (error instanceof InferenceError && error.taskId === undefined)
    Object.defineProperty(error, "taskId", { value: taskId, enumerable: true });
  return error;
}

/** Resolves after `ms`, or at once when `signal` aborts. */
function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      signal.removeEventListener("abort", done);
      resolve();
    };
    const timer = setTimeout(done, ms);
    signal.addEventListener("abort", done, { once: true });
  });
}

/** The `responses` namespace of a {@link MossInference} client, shaped like OpenAI's. */
export interface Responses {
  /**
   * Creates a response through the Moss inference gateway.
   *
   * The gateway searches `indexes` and adds what it finds to the prompt.
   * Failures reject with {@link InferenceError}. With `stream: true` this
   * resolves to a {@link ResponseStream} once the gateway accepts the request,
   * and otherwise to the `Response` of the stream's last event.
   */
  create(
    params: ResponseCreateParamsStreaming,
    options?: InferenceRequestOptions,
  ): Promise<ResponseStream>;
  create(
    params: ResponseCreateParamsNonStreaming,
    options?: InferenceRequestOptions,
  ): Promise<MossResponse>;
  create(
    params: ResponseCreateParams,
    options?: InferenceRequestOptions,
  ): Promise<ResponseStream | MossResponse>;
}

/** The files of a task, under `tasks.files`. */
export interface TaskFiles {
  /**
   * Lists the screenshots and output files of a task once it ends.
   * Before, it rejects with `task_not_finished`, and after `files_expire_at` with `files_expired`.
   */
  list(taskId: string, options?: TaskRequestOptions): Promise<TaskFileList>;
  /**
   * Downloads one file, by a `path` that `list` gave, such as `screenshots/step-1.png`.
   * It resolves to the bytes and the media type, and never opens or renders the file.
   */
  content(taskId: string, path: string, options?: TaskRequestOptions): Promise<TaskFileContent>;
}

/**
 * The `tasks` namespace of a {@link MossInference} client: an agent works toward
 * a goal in a browser on Moss, within time and dollar limits, and you poll for the result.
 * `Output` types `result.output`, which `output_schema` describes. The SDK does not check it.
 * Failures reject with {@link InferenceError}.
 */
export interface Tasks {
  /**
   * Queues a task and resolves to it, `queued`.
   * Each call sends a new `Idempotency-Key`, or the one in its own `headers`, and the same on every
   * retry. The gateway answers a repeated key with the same body, within 24 hours, with the task
   * it created, so a retried create never starts a second task. To retry one yourself, pass a key.
   * Only the call's own `apiKey` goes as `X-Moss-Provider-Key`, for the task's model calls; see
   * the pricing docs. The client's `apiKey` is never used, and no other task call sends a key.
   */
  create<Output = unknown>(
    params: TaskCreateParams,
    options?: TaskCreateOptions,
  ): Promise<Task<Output>>;
  /** Fetches a task by its id. */
  retrieve<Output = unknown>(taskId: string, options?: TaskRequestOptions): Promise<Task<Output>>;
  /**
   * Stops a task. A queued task comes back `cancelled`.
   * A running one comes back with `cancel_requested` and ends `cancelled` soon after.
   */
  cancel<Output = unknown>(taskId: string, options?: TaskRequestOptions): Promise<Task<Output>>;
  /**
   * Polls a task every `pollInterval` until it is neither `queued` nor `running`, and resolves to it.
   * A `failed` task resolves too, so read its `status` and `error`.
   * Past `timeout` it rejects with a `timeout` InferenceError, and the task goes on.
   * Its errors carry `taskId`.
   */
  wait<Output = unknown>(taskId: string, options?: TaskWaitOptions): Promise<Task<Output>>;
  /**
   * Creates a task and waits for it, as `create` and then `wait` do.
   * `timeout` and `pollInterval` apply to the wait, `apiKey` to the create, and the other options
   * to every request.
   * An error after the create carries the new task's `taskId`, so it can still be read or cancelled.
   */
  run<Output = unknown>(params: TaskCreateParams, options?: TaskRunOptions): Promise<Task<Output>>;
  /**
   * The agent's step-by-step record, as the gateway sent it.
   * It rejects with `not_found_error` until `trace_available` is true,
   * and with `files_expired` after `files_expire_at`, 7 days after the task ends.
   */
  trace(taskId: string, options?: TaskRequestOptions): Promise<unknown>;
  readonly files: TaskFiles;
}

/** A Tasks API request, with its path under the base URL. */
interface TaskCall {
  method: "GET" | "POST";
  path: string;
  /** The parameters of a create, the one call with a body, which must not start two tasks. */
  body?: TaskCreateParams;
  /** Sent as `Accept`, `application/json` by default. */
  accept?: string;
  /** The milliseconds left in a wait, which cut the call's `timeout` when shorter. */
  within?: number;
}

/** The body of a successful Tasks API response, with what its errors carry. */
interface TaskReply {
  data: Uint8Array;
  contentType: string;
  fields: ResponseFields;
}

/** The settings of one call, the client's where the call leaves one out. */
interface Settings {
  timeout: number | null;
  idleTimeout: number | null;
  maxRetries: number;
  signal?: AbortSignal;
}

/** An OK response, with the timers and abort of its call still set until `settle`. */
interface Sent {
  response: Response;
  controller: AbortController;
  idle: ReturnType<typeof idleTimer>;
  settle: () => void;
  fields: ResponseFields;
}

/** The URL path of a task, after its id is checked and encoded. */
function taskPath(taskId: unknown): string {
  if (typeof taskId !== "string" || taskId === "" || taskId === "." || taskId === "..")
    throw invalid("taskId must be a task id, such as task_...");
  return `/tasks/${encodeURIComponent(taskId)}`;
}

/** The URL path of a task's file, each part encoded. Empty, `.` and `..` parts are an error. */
function filePath(path: unknown): string {
  const parts = typeof path === "string" ? path.split("/") : [""];
  if (parts.some((part) => part === "" || part === "." || part === ".."))
    throw invalid("path must be a path that files.list gave, such as screenshots/step-1.png.");
  return parts.map(encodeURIComponent).join("/");
}

/** The JSON of a reply, which must be an object when `object` is true. */
function decode(reply: TaskReply, object = true): unknown {
  let value: unknown;
  try {
    value = JSON.parse(new TextDecoder().decode(reply.data));
  } catch {
    value = undefined;
  }
  const isObject = typeof value === "object" && value !== null && !Array.isArray(value);
  if (value === undefined || (object && !isObject)) {
    throw new InferenceError("The gateway sent a reply that is not a JSON object.", {
      type: "server_error",
      ...reply.fields,
    });
  }
  return value;
}

/** The wait limit, poll interval and per-request options of `wait` and `run`, checked. */
function waiting(options: TaskWaitOptions) {
  const { timeout = null, pollInterval = DEFAULT_POLL, ...call } = options;
  const limit = delay("timeout", timeout);
  if (typeof pollInterval !== "number" || !(pollInterval > 0 && pollInterval < Infinity))
    throw invalid("pollInterval must be a positive number of milliseconds.");
  return { limit, pollInterval: Math.min(pollInterval, MAX_DELAY), call };
}

/** The `tasks` namespace over `send`, which makes one Tasks API request. */
function tasksOf(send: (call: TaskCall, options?: TaskCreateOptions) => Promise<TaskReply>): Tasks {
  const task = async <Output>(call: TaskCall, options?: TaskCreateOptions) =>
    decode(await send(call, options)) as Task<Output>;
  const retrieve = async <Output>(taskId: string, options?: TaskRequestOptions) =>
    task<Output>({ method: "GET", path: taskPath(taskId) }, options);
  const create = async <Output>(params: TaskCreateParams, options?: TaskCreateOptions) =>
    task<Output>({ method: "POST", path: "/tasks", body: params }, options);
  const poll = async <Output>(taskId: string, settings: ReturnType<typeof waiting>) => {
    const { limit, pollInterval, call } = settings;
    const deadline = limit === null ? Infinity : Date.now() + limit;
    const signal = call.signal ?? new AbortController().signal;
    const late = (status: string, cause?: unknown) =>
      new InferenceError(
        `Task ${taskId} is still ${status} after ${limit} ms. It goes on: wait again or cancel it.`,
        { type: "timeout", taskId, cause },
      );
    const path = taskPath(taskId);
    let status = "unfinished";
    for (;;) {
      const within = limit === null ? undefined : deadline - Date.now();
      const found = await task<Output>({ method: "GET", path, within }, call).catch((error) => {
        const expired = error instanceof InferenceError && error.type === "timeout";
        throw expired && Date.now() >= deadline ? late(status, error) : withTask(error, taskId);
      });
      if (found.status !== "queued" && found.status !== "running") return found;
      status = found.status;
      const left = deadline - Date.now();
      if (left <= 0) throw late(status);
      await pause(Math.min(pollInterval, left), signal);
      if (signal.aborted) throw signal.reason;
    }
  };
  return Object.freeze({
    create,
    retrieve,
    cancel: async <Output>(taskId: string, options?: TaskRequestOptions) =>
      task<Output>({ method: "POST", path: `${taskPath(taskId)}/cancel` }, options),
    wait: async <Output>(taskId: string, options: TaskWaitOptions = {}) =>
      poll<Output>(taskId, waiting(options)),
    run: async <Output>(params: TaskCreateParams, { apiKey, ...options }: TaskRunOptions = {}) => {
      const settings = waiting(options);
      const { id } = await create(params, { ...settings.call, apiKey });
      return poll<Output>(id, settings);
    },
    trace: async (taskId: string, options?: TaskRequestOptions) =>
      decode(await send({ method: "GET", path: `${taskPath(taskId)}/trace` }, options), false),
    files: Object.freeze({
      list: async (taskId: string, options?: TaskRequestOptions) =>
        decode(
          await send({ method: "GET", path: `${taskPath(taskId)}/files` }, options),
        ) as TaskFileList,
      content: async (taskId: string, path: string, options?: TaskRequestOptions) => {
        const where = `${taskPath(taskId)}/files/${filePath(path)}`;
        const { data, contentType } = await send(
          { method: "GET", path: where, accept: "*/*" },
          options,
        );
        return { data, contentType };
      },
    }),
  });
}

/**
 * A drop-in for OpenAI's client that answers from your Moss indexes.
 *
 * Calls go to the production gateway, or to the base URL
 * in `MOSS_INFERENCE_URL` when the client is built.
 * A wrong URL, credential, provider key, header or timeout, or a `baseURL` option,
 * makes the constructor throw {@link InferenceError} with `invalid_request_error`.
 */
export class MossInference {
  /** OpenAI's `responses`, answered by the Moss inference gateway. */
  readonly responses: Responses;
  /** Browser tasks with time and dollar limits, run by the Moss inference gateway. */
  readonly tasks: Tasks;
  /** The base URL of every call, up to and including `/v1`. */
  readonly #base: string;
  /** The caller's headers for every call. */
  readonly #headers: Headers;
  /** The `Authorization` of every call, which wins over the caller's headers. */
  readonly #authorization: string;
  readonly #timeout: number | null;
  readonly #idleTimeout: number | null;
  readonly #maxRetries: number;
  /** The provider key for `responses` calls that do not pass their own. Tasks never use it. */
  readonly #apiKey: string | undefined;

  constructor(projectId: string, projectKey: string, options: MossInferenceOptions = {}) {
    const id = credential("projectId", projectId);
    const key = credential("projectKey", projectKey);
    if (id.includes(":")) throw invalid("projectId must not contain a colon.");
    refuseURL(options);
    this.#base = baseURL();
    this.#timeout = delay("timeout", options.timeout ?? null);
    const { idleTimeout = DEFAULT_IDLE_TIMEOUT, maxRetries = DEFAULT_RETRIES } = options;
    this.#idleTimeout = delay("idleTimeout", idleTimeout);
    this.#maxRetries = retries(maxRetries);
    this.#headers = headersOf(options.headers);
    this.#authorization = `Bearer ${id}:${key}`;
    this.#apiKey = options.apiKey == null ? undefined : credential("apiKey", options.apiKey);
    const create = (params: ResponseCreateParams, call?: InferenceRequestOptions) =>
      this.#create(params, call);
    this.responses = Object.freeze({ create: create as Responses["create"] });
    this.tasks = tasksOf((call, options) => this.#task(call, options));
  }

  /** The settings of a call: its own where given, else the client's. */
  #settings(options: TaskRequestOptions): Settings {
    return {
      timeout: options.timeout === undefined ? this.#timeout : delay("timeout", options.timeout),
      idleTimeout:
        options.idleTimeout === undefined
          ? this.#idleTimeout
          : delay("idleTimeout", options.idleTimeout),
      maxRetries: options.maxRetries === undefined ? this.#maxRetries : retries(options.maxRetries),
      signal: options.signal,
    };
  }

  /** The client's headers, then the call's, then `own` and `Authorization`, which win. */
  #merge(call: Record<string, string> | undefined, own: Record<string, string>): Headers {
    const headers = new Headers(this.#headers);
    for (const [name, value] of headersOf(call)) headers.set(name, value);
    for (const [name, value] of Object.entries(own)) headers.set(name, value);
    headers.set("Authorization", this.#authorization);
    return headers;
  }

  async #task(call: TaskCall, options: TaskCreateOptions = {}): Promise<TaskReply> {
    refuseURL(options);
    const settings = this.#settings(options);
    if (call.within !== undefined)
      settings.timeout = Math.max(Math.min(settings.timeout ?? MAX_DELAY, call.within), 1);
    const own: Record<string, string> = {
      Accept: call.accept ?? "application/json",
    };
    if (call.body) {
      if ("apiKey" in call.body || "api_key" in call.body)
        throw invalid("Pass the provider key as apiKey in the options of create, not in params.");
      own["Content-Type"] = "application/json";
      own["Idempotency-Key"] = headersOf(options.headers).get("Idempotency-Key") ?? randomUUID();
      if (options.apiKey != null) own["X-Moss-Provider-Key"] = credential("apiKey", options.apiKey);
    }
    const headers = this.#merge(options.headers, own);
    const init = {
      method: call.method,
      headers,
      body: call.body && json(call.body),
    };
    const { response, controller, idle, settle, fields } = await this.#send(
      this.#base + call.path,
      init,
      settings,
      TASK_RETRY_STATUSES,
    );
    try {
      const data = await readBody(response, idle);
      const contentType = response.headers.get("Content-Type") ?? "application/octet-stream";
      return { data, contentType, fields };
    } catch (error) {
      if (controller.signal.aborted) throw controller.signal.reason;
      throw transportError(error, "The gateway's reply broke off", fields);
    } finally {
      settle();
    }
  }

  async #create(
    params: ResponseCreateParams,
    options: InferenceRequestOptions = {},
  ): Promise<ResponseStream | MossResponse> {
    refuseURL(options);
    const { indexes, retrieve, cache, model = DEFAULT_MODEL, ...body } = params;
    if (body.apiKey !== undefined || body.api_key !== undefined)
      throw invalid("Pass the provider key as apiKey in the options of create, not in params.");
    if (indexes !== undefined && !Array.isArray(indexes))
      throw invalid("indexes must be an array of index names.");
    for (const name of indexes ?? []) {
      if (typeof name !== "string" || name === "" || name.includes(",")) {
        throw invalid(
          `Invalid index name ${JSON.stringify(name)}. Names must be non-empty and contain no comma.`,
        );
      }
      headerSafe(`Index name ${JSON.stringify(name)}`, name);
    }
    const apiKey = options.apiKey == null ? this.#apiKey : credential("apiKey", options.apiKey);
    const settings = this.#settings(options);
    const headers = this.#merge(options.headers, {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    });
    if (indexes?.length) headers.set("X-Moss-Indexes", indexes.join(","));
    else if (indexes) headers.delete("X-Moss-Indexes");
    if (retrieve === false || indexes?.length === 0) headers.set("X-Moss-Retrieve", "off");
    if (cache === false) headers.set("X-Moss-Cache", "off");
    if (apiKey !== undefined) headers.set("X-Moss-Provider-Key", apiKey);
    const payload = json({ model, ...body, stream: true });
    const init = { method: "POST", headers, body: payload };
    const { response, controller, idle, settle, fields } = await this.#send(
      `${this.#base}/responses`,
      init,
      settings,
      RETRY_STATUSES,
    );
    const stream = new ResponseStream(response, controller, idle, settle, fields);
    return params.stream ? stream : stream.finalResponse();
  }

  /**
   * Sends a request and resolves to its OK response, with the call's timers still set.
   * A failure before the response goes again within `maxRetries` and `timeout`.
   */
  async #send(
    url: string,
    init: { method: string; headers: Headers; body?: string },
    { timeout, idleTimeout, maxRetries, signal }: Settings,
    statuses: number[],
  ): Promise<Sent> {
    const controller = new AbortController();
    let fields: ResponseFields = {};
    const expire = (message: string) => () =>
      controller.abort(new InferenceError(message, { type: "timeout", ...fields }));
    const timer =
      timeout === null
        ? undefined
        : setTimeout(expire(`The request timed out after ${timeout} ms.`), timeout);
    const deadline = timeout === null ? Infinity : Date.now() + timeout;
    const idle = idleTimer(idleTimeout, expire(`The gateway sent nothing for ${idleTimeout} ms.`));
    const onAbort = () => controller.abort(signal?.reason);
    signal?.addEventListener("abort", onAbort, { once: true });
    if (signal?.aborted) onAbort();
    const settle = () => {
      clearTimeout(timer);
      idle.clear();
      signal?.removeEventListener("abort", onAbort);
    };

    let response: Response;
    for (let attempt = 0; ; attempt++) {
      fields = {};
      let wait = Math.min(500 * 2 ** attempt, 8000) * (1 - Math.random() / 4);
      try {
        idle.arm();
        response = await fetch(url, {
          ...init,
          signal: controller.signal,
          redirect: "manual",
        });
        idle.clear();
        fields = responseFields(response);
        const after = fields.retryAfter ?? Infinity;
        if (after <= MAX_RETRY_AFTER) wait = after;
        const last = attempt >= maxRetries || Date.now() + wait >= deadline;
        if (response.ok || last || !retryable(response, statuses)) break;
        response.body?.cancel().catch(() => {});
      } catch (error) {
        idle.clear();
        const code = (error as { cause?: { code?: unknown } } | null)?.cause?.code;
        const headersTimeout = code === "UND_ERR_HEADERS_TIMEOUT";
        const last = attempt >= maxRetries || Date.now() + wait >= deadline;
        if (controller.signal.aborted || headersTimeout || last) {
          settle();
          if (controller.signal.aborted) throw controller.signal.reason;
          throw transportError(error, "The inference gateway did not answer");
        }
      }
      await pause(wait, controller.signal);
      if (controller.signal.aborted) {
        settle();
        throw controller.signal.reason;
      }
    }
    if (!response.ok) {
      const text = await errorText(response, idle).catch(() => "");
      settle();
      if (controller.signal.aborted) throw controller.signal.reason;
      throw errorFromResponse(response, text);
    }
    return { response, controller, idle, settle, fields };
  }
}

let fallback: { env: string; client: MossInference } | undefined;

/** The client of `inference`, for the current environment. */
function defaultClient(): MossInference {
  const [id, key] = ["MOSS_PROJECT_ID", "MOSS_PROJECT_KEY"].map(env);
  if (!id || !key) {
    throw invalid(
      "Missing project credentials. Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY, or create a MossInference.",
    );
  }
  const snapshot = JSON.stringify([id, key, env("MOSS_INFERENCE_URL")]);
  if (fallback?.env !== snapshot) fallback = { env: snapshot, client: new MossInference(id, key) };
  return fallback.client;
}

/**
 * Responses and tasks through a {@link MossInference} client.
 * Each call reads `MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY` and `MOSS_INFERENCE_URL`.
 * The client is built on first use, and again when one of them changes.
 */
export const inference: {
  readonly responses: Responses;
  readonly tasks: Tasks;
} = Object.freeze({
  responses: Object.freeze({
    create: (async (params: ResponseCreateParams, options?: InferenceRequestOptions) =>
      defaultClient().responses.create(params, options)) as Responses["create"],
  }),
  /** The `tasks` of the client. Reading it throws {@link InferenceError} without credentials. */
  get tasks(): Tasks {
    return defaultClient().tasks;
  },
});
