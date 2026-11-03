// An `any` index signature, unlike `unknown`, also accepts values whose types are interfaces.
/* eslint-disable @typescript-eslint/no-explicit-any */

/** A message of the conversation, such as `{ role: "user", content: "Hi" }`. */
export interface EasyInputMessage {
  type?: "message";
  role: "user" | "assistant" | "system" | "developer";
  /** Text, or a list of parts such as `{ type: "input_text", text }`. */
  content: string | { type: string; [key: string]: any }[];
  [key: string]: any;
}

/** The result of a {@link ResponseFunctionToolCall}, for the `input` of the next request. */
export interface FunctionCallOutput {
  type: "function_call_output";
  /** The `call_id` of the call. */
  call_id: string;
  /** Text, or a list of parts such as `{ type: "input_text", text }`. */
  output: string | { type: string; [key: string]: any }[];
  [key: string]: any;
}

/**
 * An item of `input`: a message, the result of a function call,
 * or an item of an earlier response's `output`, sent back unchanged.
 */
export type ResponseInputItem = EasyInputMessage | FunctionCallOutput | ResponseOutputItem;

/** A function the model may call. Your code runs it and sends back the result. */
export interface FunctionTool {
  type: "function";
  name: string;
  description?: string | null;
  parameters?: Record<string, unknown> | null;
  strict?: boolean | null;
}

/** An MCP server the gateway calls for the model during the turn. */
export interface McpServer {
  /** Marks this `tools` entry as an MCP server. */
  type: "mcp";
  /** The server's label, unique in the request. */
  server_label: string;
  /** The server's https URL. */
  server_url: string;
  /** Headers for this server only, such as its `Authorization`. */
  headers?: Record<string, string>;
  /** The only tools of the server the model may call. */
  allowed_tools?: string[];
  /** `streamable_http` by default, or `sse` for an older server. */
  transport?: "streamable_http" | "sse";
}

/**
 * OpenAI's Responses parameters plus the Moss options.
 * `indexes`, `retrieve` and `cache` travel as headers, the rest in the body
 * unchanged, including parameters this type does not name. The body always says `stream: true`.
 */
export interface ResponseCreateParamsBase {
  /** `moss` by default, Moss's own model. A vendor model such as `gpt-4o-mini` needs `apiKey`. */
  model?: string;
  /** The text to answer, or the whole conversation so far, since Moss stores none. */
  input: string | ResponseInputItem[];
  /** The system message, before `input`. */
  instructions?: string | null;
  stream?: boolean | null;
  /**
   * Moss indexes to search, every index when left out and none when empty.
   * Names travel in a single header, so each must be Latin-1 text with no comma.
   */
  indexes?: string[];
  /** False skips retrieval for this call. */
  retrieve?: boolean;
  /** False always asks the model instead of the gateway's reply cache. */
  cache?: boolean;
  /** Functions your code runs, MCP servers the gateway calls, or any other tool object. */
  tools?: (FunctionTool | McpServer | { type: string; [key: string]: any })[];
  /** Whether and which tool the model calls, such as `{ type: "function", name }`. */
  tool_choice?: "none" | "auto" | "required" | { type: string; [key: string]: any };
  /** False asks the model for at most one tool call per response. */
  parallel_tool_calls?: boolean | null;
  /** The most tokens the response can have. A longer one ends `incomplete`. */
  max_output_tokens?: number | null;
  temperature?: number | null;
  top_p?: number | null;
  /** Such as `{ format: { type: "json_schema", name, schema } }` for structured output. */
  text?: { format?: { type: string; [key: string]: any }; [key: string]: any } | null;
  /** Such as `{ effort: "low" }`. */
  reasoning?: { effort?: string | null; [key: string]: any } | null;
  metadata?: Record<string, string> | null;
  user?: string;
  /** Any other OpenAI parameter. */
  [param: string]: any;
}

/** Parameters that return a {@link ResponseStream}. */
export interface ResponseCreateParamsStreaming extends ResponseCreateParamsBase {
  stream: true;
}

/** Parameters that return one {@link Response}. */
export interface ResponseCreateParamsNonStreaming extends ResponseCreateParamsBase {
  stream?: false | null;
}

/** Parameters of `responses.create`. */
export type ResponseCreateParams = ResponseCreateParamsStreaming | ResponseCreateParamsNonStreaming;

/**
 * Settings of a `MossInference` client.
 * Timeouts are in milliseconds, and `null` or `Infinity` removes the limit.
 */
export interface MossInferenceOptions {
  /**
   * Your own OpenAI, Anthropic or Google key, for a vendor model such as `gpt-4o-mini`.
   * `moss` ignores it, and a vendor model without one is refused. A call's `apiKey` wins.
   */
  apiKey?: string;
  /** The limit for each whole call, streaming included. None by default. */
  timeout?: number | null;
  /**
   * The longest wait for response headers or for more of the body. 120 000 by default.
   * Node's fetch also ends a silence of 300 000, unless its global dispatcher allows more.
   */
  idleTimeout?: number | null;
  /**
   * Retries before the stream starts, 2 by default and 0 for none.
   * A failed connection or a 408, 409, 429 or 5xx response is retried.
   */
  maxRetries?: number;
  /** Headers sent on every call. Host, Content-Length and Transfer-Encoding are an error. */
  headers?: Record<string, string>;
}

/** Per-call settings that never reach the request body. */
export interface InferenceRequestOptions {
  /** Replaces the client's `apiKey` for this call. An empty string is an error. */
  apiKey?: string;
  /** Aborts the call. */
  signal?: AbortSignal;
  /** Replaces the client's `timeout` for this call. */
  timeout?: number | null;
  /** Replaces the client's `idleTimeout` for this call. */
  idleTimeout?: number | null;
  /** Replaces the client's `maxRetries` for this call. */
  maxRetries?: number;
  /**
   * Headers for this call, over the client's.
   * The SDK's own headers win over both, and Host,
   * Content-Length and Transfer-Encoding are an error.
   */
  headers?: Record<string, string>;
}

/** Token counts for one call, with every field the gateway sent, such as `moss`. */
export interface ResponseUsage {
  input_tokens: number;
  input_tokens_details: { cached_tokens: number; [key: string]: any };
  output_tokens: number;
  output_tokens_details: { reasoning_tokens: number; [key: string]: any };
  total_tokens: number;
  [key: string]: any;
}

/** The text of a message, with its annotations. */
export interface ResponseOutputText {
  type: "output_text";
  text: string;
  annotations: any[];
  [key: string]: any;
}

/** A message of the model, an item of `output`. */
export interface ResponseOutputMessage {
  type: "message";
  id: string;
  role: "assistant";
  status: "in_progress" | "completed" | "incomplete";
  content: ResponseOutputText[];
  [key: string]: any;
}

/**
 * A call of one of your function tools, an item of `output`.
 * Fields the model adds, such as Gemini's `extra_content`, stay on the object,
 * so it goes back into `input` unchanged, before its {@link FunctionCallOutput}.
 */
export interface ResponseFunctionToolCall {
  type: "function_call";
  id: string;
  /** The id its {@link FunctionCallOutput} names. */
  call_id: string;
  name: string;
  /** The arguments as JSON text. */
  arguments: string;
  status: "in_progress" | "completed" | "incomplete";
  [key: string]: any;
}

/**
 * A call that the gateway ran on one of your MCP servers, an item of `output`.
 * Sent back in `input` with the rest of `output`, it gives the model the tool's earlier result.
 */
export interface McpCall {
  type: "mcp_call";
  id: string;
  /** The label of the MCP server, as sent in `tools`. */
  server_label: string;
  /** The tool's name on its server. */
  name: string;
  /** The arguments as JSON text. */
  arguments: string;
  /** The tool's result, cut when long, once it succeeded. */
  output?: string | null;
  /** What failed, once the tool failed. */
  error?: { type: string; [key: string]: any } | null;
  status: "in_progress" | "completed" | "failed";
  /** How long the call took in milliseconds, once it ended. */
  duration_ms?: number;
  [key: string]: any;
}

/** The reasoning of a reasoning model, an item of `output`, kept as the gateway sent it. */
export interface ResponseReasoningItem {
  type: "reasoning";
  id: string;
  [key: string]: any;
}

/** An item of `output`. An item of another type comes as the gateway sent it. */
export type ResponseOutputItem =
  ResponseOutputMessage | ResponseFunctionToolCall | McpCall | ResponseReasoningItem;

/**
 * A response, the JSON the gateway sent, plus `output_text`.
 * `JSON.stringify` keeps `output_text` and leaves out `requestId`.
 * A call without `stream: true`, and `finalResponse()`, return the one of the last event.
 */
export interface Response {
  /** Such as `resp_...`. */
  id: string;
  object: "response";
  /** In seconds since the epoch. */
  created_at: number;
  /** `incomplete` when `max_output_tokens` or a content filter cut the response. */
  status: "completed" | "incomplete" | "failed" | "in_progress" | (string & {});
  model: string;
  output: ResponseOutputItem[];
  /** The text of every `output_text` part of every message in `output`, joined. */
  output_text: string;
  usage: ResponseUsage | null;
  error: { code: string; message: string; [key: string]: any } | null;
  incomplete_details: { reason: "max_output_tokens" | "content_filter" | (string & {}) } | null;
  instructions: string | null;
  metadata: Record<string, string> | null;
  /** The `X-Moss-Request-Id` of the HTTP response. */
  readonly requestId?: string;
  /** The other request fields the gateway repeats, such as `temperature`. */
  [key: string]: any;
}

/**
 * One event of a streamed response, the JSON the gateway sent.
 * Each type sets its own fields, such as `delta` on `response.output_text.delta`,
 * `item` on `response.output_item.added` and `.done`, and `response` on
 * `response.created`, `response.completed` and `response.incomplete`.
 */
export interface ResponseStreamEvent {
  type: string;
  sequence_number?: number;
  response?: Response;
  output_index?: number;
  item_id?: string;
  item?: ResponseOutputItem;
  content_index?: number;
  delta?: string;
  text?: string;
  arguments?: string;
  [key: string]: any;
}
