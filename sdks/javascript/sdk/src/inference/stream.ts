import { InferenceError, codeText, transportError, type ResponseFields } from "./error";
import type { Response as MossResponse, ResponseStreamEvent } from "./types";

/** The most UTF-16 code units in one line or in the data of one event. */
const MAX_EVENT = 1 << 20;
/** The most bytes of an error body read for its message. */
const MAX_ERROR_BODY = 1 << 20;

/** A timer that runs only while armed, so a slow reader never trips it. */
interface IdleTimer {
  arm(): void;
  clear(): void;
}

/** Calls `onIdle` when an armed timer runs `ms` milliseconds. Null `ms` never fires. */
export function idleTimer(ms: number | null, onIdle: () => void): IdleTimer {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return {
    arm() {
      clearTimeout(timer);
      if (ms !== null) timer = setTimeout(onIdle, ms);
    },
    clear: () => clearTimeout(timer),
  };
}

/**
 * Reads an error body, arming `idle` while each read waits.
 * It stops after {@link MAX_ERROR_BODY} bytes and cancels the rest of the body.
 */
export async function errorText(response: Response, idle: IdleTimer): Promise<string> {
  if (!response.body) return "";
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let text = "";
  let size = 0;
  try {
    while (size < MAX_ERROR_BODY) {
      idle.arm();
      const { value, done } = await reader.read();
      idle.clear();
      if (done) break;
      size += value.byteLength;
      text += decoder.decode(value, { stream: true });
    }
    return text + decoder.decode();
  } finally {
    reader.cancel().catch(() => {});
  }
}

/** True for the reason of a plain `abort()`, which ends a stream quietly. */
function isAbortError(reason: unknown): boolean {
  return (reason as { name?: unknown } | null)?.name === "AbortError";
}

/** True when the socket ended with no OS error, which undici reports as `UND_ERR_SOCKET`. */
function socketEnded(error: unknown): boolean {
  return (error as { cause?: { code?: unknown } } | null)?.cause?.code === "UND_ERR_SOCKET";
}

/**
 * Yields the data of each server-sent event, joining multi-line data with `\n`.
 * Like any SSE parser, it drops an event that the body ends before its blank line.
 * It splits only the newly read text, so a long line costs time in proportion to its length.
 * A line or the data of one event over {@link MAX_EVENT} throws a `server_error` InferenceError.
 */
async function* sseData(
  body: ReadableStream<Uint8Array>,
  idle: IdleTimer,
  fields: ResponseFields,
): AsyncGenerator<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const tooLarge = () =>
    new InferenceError("The gateway sent an event over 1 MiB.", {
      type: "server_error",
      ...fields,
    });
  let pending = "";
  let data: string[] = [];
  let size = 0;
  try {
    for (;;) {
      idle.arm();
      const { value, done } = await reader.read();
      idle.clear();
      if (done) return;
      const lines = decoder.decode(value, { stream: true }).split("\n");
      lines[0] = pending + lines[0];
      pending = lines.pop() ?? "";
      for (const raw of lines) {
        if (raw.length > MAX_EVENT) throw tooLarge();
        const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
        if (line === "") {
          if (data.length > 0) yield data.join("\n");
          data = [];
          size = 0;
        } else if (line.startsWith("data:")) {
          const part = line.slice(line.startsWith("data: ") ? 6 : 5);
          size += part.length + (data.length > 0 ? 1 : 0);
          if (size > MAX_EVENT) throw tooLarge();
          data.push(part);
        }
      }
      if (pending.length > MAX_EVENT) throw tooLarge();
    }
  } finally {
    reader.cancel().catch(() => {});
  }
}

/**
 * The streamed response of `responses.create` with `stream: true`.
 *
 * Iterate it once with `for await`. It ends after `response.completed` or `response.incomplete`.
 * Leaving the loop early, or calling `controller.abort()`, ends the loop quietly,
 * closes the connection and stops the model. An abort with any other reason,
 * such as the `TimeoutError` of `AbortSignal.timeout()`, throws that reason.
 * A failure inside the stream, such as `response.failed`, throws an {@link InferenceError}
 * after the events before it, with `errorCode` `failed_after_tool_call` once an event carried an `mcp_call` item.
 */
export class ResponseStream implements AsyncIterable<ResponseStreamEvent> {
  /** Aborts the request. */
  readonly controller: AbortController;
  /** The `X-Moss-Request-Id` of the response, undefined when it has none. */
  readonly requestId: string | undefined;
  #events: AsyncIterator<ResponseStreamEvent> | undefined;
  readonly #next: () => Promise<IteratorResult<ResponseStreamEvent>>;
  /** What reading the events threw, which the final response throws again. */
  #failure: { error: unknown } | undefined;
  /** The `response` of the last event, once it came. */
  #response: MossResponse | undefined;
  #final: Promise<MossResponse> | undefined;

  /** @internal */
  constructor(
    response: Response,
    controller: AbortController,
    idle: { arm(): void; clear(): void },
    onSettled: () => void,
    fields: { requestId?: string; errorCode?: "failed_after_tool_call" },
  ) {
    this.controller = controller;
    this.requestId = fields.requestId;
    const generator = events(response, controller, idle, onSettled, fields);
    this.#next = async () => {
      try {
        const result = await generator.next();
        if (!result.done && isLast(result.value)) this.#response = result.value.response;
        return result;
      } catch (error) {
        this.#failure = { error };
        throw error;
      }
    };
    this.#events = {
      next: this.#next,
      return: (value?: unknown) => {
        controller.abort();
        onSettled();
        return generator.return(value);
      },
    };
  }

  /** Iterates the events once. Its `return()` closes the connection, even before the first event. */
  [Symbol.asyncIterator](): AsyncIterator<ResponseStreamEvent> {
    const iterator = this.#events;
    if (!iterator) throw new Error("A ResponseStream can be iterated only once.");
    this.#events = undefined;
    return iterator;
  }

  /**
   * The `response` of the last event, as a call without `stream: true` returns.
   *
   * Every call returns the same response.
   * Call it after the loop ends, or instead of one.
   * It reads the events the loop has not read.
   * It rejects with what the loop throws, or with the signal's reason
   * after an abort that came before the last event.
   */
  finalResponse(): Promise<MossResponse> {
    return (this.#final ??= this.#drain());
  }

  async #drain(): Promise<MossResponse> {
    while (!(await this.#next()).done);
    if (this.#failure) throw this.#failure.error;
    if (this.#response) return this.#response;
    throw this.controller.signal.reason;
  }
}

/** True for a JSON object, not null or an array. */
const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/** True for the last event of a stream, which holds the whole response. */
const isLast = (event: ResponseStreamEvent): event is { type: string; response: MossResponse } =>
  ["response.completed", "response.incomplete"].includes(event.type) && isObject(event.response);

async function* events(
  response: Response,
  controller: AbortController,
  idle: IdleTimer,
  onSettled: () => void,
  fields: ResponseFields,
): AsyncGenerator<ResponseStreamEvent> {
  const notObject = "The gateway sent an event that is not a JSON object.";
  let done = false;
  try {
    if (!response.body) {
      throw new InferenceError("The response has no body.", {
        type: "incomplete_stream",
        ...fields,
      });
    }
    for await (const data of sseData(response.body, idle, fields)) {
      if (data === "[DONE]") break;
      let event: ResponseStreamEvent;
      try {
        event = JSON.parse(data);
      } catch (cause) {
        throw new InferenceError(notObject, { type: "server_error", cause, ...fields });
      }
      if (!isObject(event)) {
        throw new InferenceError(notObject, { type: "server_error", ...fields });
      }
      if (event.type === "response.failed" || event.type === "error") {
        const failed = event.type === "response.failed";
        const error: { message?: unknown; type?: unknown; code?: unknown } = failed
          ? (event.response?.error ?? {})
          : event;
        throw new InferenceError(
          typeof error.message === "string" ? error.message : "The model failed during the stream.",
          {
            type: failed && typeof error.type === "string" ? error.type : "model_error",
            errorCode: codeText(error.code),
            ...fields,
          },
        );
      }
      if (event.item?.type === "mcp_call") fields.errorCode = "failed_after_tool_call";
      if (isObject(event.response)) {
        const output = Array.isArray(event.response.output) ? event.response.output : [];
        event.response.output_text = output
          .flatMap((item) =>
            item?.type === "message" && Array.isArray(item.content) ? item.content : [],
          )
          .filter((part) => part?.type === "output_text" && typeof part.text === "string")
          .map((part) => part.text)
          .join("");
        Object.defineProperty(event.response, "requestId", { value: fields.requestId });
      }
      done = isLast(event);
      yield event;
      if (done) return;
    }
    throw new InferenceError("The stream ended before response.completed.", {
      type: "incomplete_stream",
      ...fields,
    });
  } catch (error) {
    if (error instanceof InferenceError) throw error;
    const { aborted, reason } = controller.signal;
    if (aborted) {
      if (isAbortError(reason)) return;
      throw reason;
    }
    if (socketEnded(error)) {
      throw new InferenceError("The connection closed before response.completed.", {
        type: "incomplete_stream",
        cause: error,
        ...fields,
      });
    }
    throw transportError(error, "The connection failed", fields);
  } finally {
    if (!done) controller.abort();
    onSettled();
  }
}
