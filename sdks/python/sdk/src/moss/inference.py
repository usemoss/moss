"""Responses grounded in your Moss indexes, in the shape of OpenAI's Responses API,
and browser tasks that an agent runs on Moss.

Moss adds the facts it finds in your indexes to the prompt.
`MossInference(project_id, project_key)` is a client with your credentials.
Its `responses.create` takes OpenAI's arguments, plus the `indexes` to search,
and its `tasks` queue a goal for an agent in a browser, then poll for the result.
`MossInferenceSync` makes the `tasks` calls without an event loop.
"""

import asyncio
import contextlib
import ipaddress
import json
import math
import os
import random
import re
import threading
import uuid
from dataclasses import dataclass, field, fields, is_dataclass
from functools import partial
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
    Generic,
    Iterable,
    Literal,
    Mapping,
    Sequence,
    TypedDict,
    TypeVar,
    overload,
)
from urllib.parse import quote, urlsplit

import httpx

_PRODUCTION_URL = "https://inference.moss.dev/v1"
_T = TypeVar("_T")
_Output = TypeVar("_Output")
_STATUS_TYPES = {
    401: "authentication_error",
    403: "permission_error",
    404: "not_found_error",
    429: "rate_limit_error",
}
_CLIENT_ARGUMENTS = ("project_id", "project_key")
_ENV = ("MOSS_PROJECT_ID", "MOSS_PROJECT_KEY", "MOSS_INFERENCE_URL")
_TOKEN = re.compile(r"[-!#$%&'*+.^_`|~0-9A-Za-z]+")
_URL_TEXT = re.compile(r"[!-~]+")
_HOST = re.compile(r"[a-z0-9_.~-]+")
_BAD_URL = (
    "MOSS_INFERENCE_URL must be an http or https URL with a host, "
    "and no user info, query or fragment"
)
_HTTP_HEADERS = frozenset({"host", "content-length", "transfer-encoding"})
_RETRY_STATUSES = frozenset({408, 409, 429})
_TASK_RETRY_STATUSES = frozenset({408, 429})
"""The statuses below 500 a task call goes again after. The files routes send 409
until a task ends, so a task call does not retry it."""
_RETRY_ERRORS = (httpx.NetworkError, httpx.RemoteProtocolError, httpx.ConnectTimeout)
_WAITING = frozenset({"queued", "running"})
_FILE_TYPE = "application/octet-stream"
_LIMITS = httpx.Limits(max_connections=1000, max_keepalive_connections=100)
_ERROR_BODY_BYTES = 65_536
_EVENT_BYTES = 1_048_576
_OVERSIZE = "The gateway sent an event over 1 MiB."

_DEFAULT_IDLE_TIMEOUT = 120.0
"""The seconds of a client's `idle_timeout` when it is given None."""

_CONNECT_TIMEOUT = 10.0
"""The most seconds a call waits to connect, or `idle_timeout` when shorter.
It holds even with `idle_timeout` off, since a model can stay silent for minutes
while a service that is up connects in about a second, so a dead one fails fast."""

_EXCERPT_CHARS = 300
"""The most characters an error message keeps of a body that is not JSON."""

_POLL_INTERVAL = 2.0
"""The seconds between the polls of `tasks.wait`."""


class InferenceError(RuntimeError):
    """A failed inference call.

    Errors with no service type use `invalid_request_error` for bad arguments,
    `connection_error`, `timeout`, or `incomplete_stream` for a stream cut short.

    Attributes:
        message: What failed, the text of `str(error)`.
        status: The HTTP status of a refused request, else None.
        type: The error type, such as `authentication_error` or `model_error`.
        code: The error code, such as `rate_limit_exceeded`, else None.
            It is `failed_after_tool_call` for any error after a tool step,
            since a tool may have changed data, so do not replay the call blindly.
        request_id: The `X-Moss-Request-Id` of the response, when one arrived.
        retry_after: The seconds an error response asks to wait in `Retry-After`.
        task_id: The task an error of `tasks.wait` or `tasks.run` concerns,
            which may still be running, so it can still be read or cancelled.
    """

    def __init__(
        self,
        message: str,
        *,
        type: str,
        status: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
        task_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.type: str = type
        self.status: int | None = status
        self.code: str | None = code
        self.request_id: str | None = request_id
        self.retry_after: float | None = retry_after
        self.task_id: str | None = task_id

    def __reduce__(self) -> tuple[Any, ...]:
        """How pickle and copy rebuild the error, with `type` as a keyword."""
        return partial(type(self), type=self.type), (self.message,), self.__dict__


@dataclass(frozen=True, kw_only=True)
class InputTokensDetails:
    """Token counts of the parts of a prompt, such as its cached tokens."""

    cached_tokens: int = 0


@dataclass(frozen=True, kw_only=True)
class OutputTokensDetails:
    """Token counts of the parts of a reply, such as its reasoning."""

    reasoning_tokens: int = 0


@dataclass(frozen=True, kw_only=True)
class ResponseUsage:
    """Token counts of a response."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_tokens_details: InputTokensDetails | None = None
    output_tokens_details: OutputTokensDetails | None = None


@dataclass(frozen=True, kw_only=True)
class ResponseOutputText:
    """The text of a message."""

    type: str = "output_text"
    text: str = ""
    annotations: list[Any] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class ResponseOutputMessage:
    """A message of the model, an item of `output`.
    `raw` is the item as it came, which is what goes back into `input`."""

    id: str = ""
    type: str = "message"
    role: str = "assistant"
    status: str | None = None
    content: list[ResponseOutputText | dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True, kw_only=True)
class ResponseFunctionToolCall:
    """A call of one of your function tools, an item of `output`.

    Run the function and send its result back as a `function_call_output` item
    with the same `call_id`, after this call, in the `input` of the next request.
    `raw` is the item as it came, with the fields these types leave out,
    such as Gemini's `extra_content`. It is what goes back into `input`.
    """

    id: str = ""
    type: str = "function_call"
    call_id: str = ""
    name: str = ""
    arguments: str = ""
    status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True, kw_only=True)
class McpCall:
    """A call that Moss ran on one of your MCP servers, an item of `output`.

    `raw` is the item as it came, for the fields these types leave out.
    Sent back in `input`, it gives the model the earlier tool result.

    Attributes:
        id: The ID of the call.
        server_label: The `server_label` of the tool's server.
        name: The name of the tool.
        arguments: The JSON arguments.
        output: The tool's output, when it succeeded.
        error: What failed, when the tool failed.
        status: `in_progress`, `completed` or `failed`.
        duration_ms: The milliseconds the tool took.
    """

    id: str = ""
    type: str = "mcp_call"
    server_label: str = ""
    name: str = ""
    arguments: str = ""
    output: str | None = None
    error: Any = None
    status: str | None = None
    duration_ms: float | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


ResponseOutputItem = (
    ResponseOutputMessage | ResponseFunctionToolCall | McpCall | dict[str, Any]
)
"""An item of `output`. An item of another type stays the dict it came as."""


@dataclass(frozen=True, kw_only=True)
class IncompleteDetails:
    """Why a response is incomplete: `max_output_tokens` or `content_filter`."""

    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class Response:
    """A whole response.

    `output_text` joins the text of its messages. `raw` is the response as it came,
    for the fields these types leave out, and `request_id` the `X-Moss-Request-Id`
    of the HTTP response, when it had one. A response cut short is `incomplete`.
    """

    id: str = ""
    object: str = "response"
    created_at: float = 0
    status: str | None = None
    model: str = ""
    instructions: str | None = None
    output: list[ResponseOutputItem] = field(default_factory=list)
    usage: ResponseUsage | None = None
    incomplete_details: IncompleteDetails | None = None
    metadata: dict[str, str] | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
    request_id: str | None = field(default=None, repr=False, compare=False)

    @property
    def output_text(self) -> str:
        """The text of the messages in `output`, joined."""
        return "".join(
            part.text
            for item in self.output
            if isinstance(item, ResponseOutputMessage)
            for part in item.content
            if isinstance(part, ResponseOutputText)
        )


@dataclass(frozen=True, kw_only=True)
class ResponseStreamEvent:
    """One event of a streamed response, such as `response.output_text.delta`.

    Each type of event sets its own fields and leaves the others None, as OpenAI's do:
    `delta` on a delta, `item` on `response.output_item.added` and `.done`, and
    `response` on `response.created`, `response.completed` and `response.incomplete`.
    `raw` is the decoded event, for the fields these types leave out.
    """

    type: str = ""
    sequence_number: int | None = None
    response: Response | None = None
    output_index: int | None = None
    item_id: str | None = None
    item: ResponseOutputItem | None = None
    content_index: int | None = None
    delta: str | None = None
    text: str | None = None
    arguments: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True, kw_only=True)
class McpServer:
    """An MCP server whose tools the model can call, as an entry of `tools`.

    Moss connects to it and runs its tools during the reply.
    `server_url` and `headers` never show in a repr, since either can hold a secret.

    Attributes:
        type: Always `mcp`.
        server_label: The server's name.
        server_url: The server's https URL.
        headers: Headers for the server, such as its `Authorization`.
        allowed_tools: The names of the tools the model can call, else all of them.
        transport: `streamable_http`, the default, or `sse`.
    """

    type: Literal["mcp"] = field(default="mcp", init=False)
    server_label: str
    server_url: str = field(repr=False)
    headers: dict[str, str] | None = field(default=None, repr=False)
    allowed_tools: list[str] | None = None
    transport: Literal["streamable_http", "sse"] | None = None


ResponseInputItemParam = (
    Mapping[str, Any] | ResponseOutputMessage | ResponseFunctionToolCall | McpCall
)
"""An item of `input`: an OpenAI input item dict, or an `output` item of a response."""

ToolParam = Mapping[str, Any] | McpServer
"""An entry of `tools`: an `McpServer`, or a tool dict such as a function tool.
A function tool is flat: `{"type": "function", "name": ..., "parameters": ...}`."""

ToolChoiceParam = Literal["none", "auto", "required"] | Mapping[str, Any]
"""A `tool_choice`: `none`, `auto`, `required`, or a dict such as a function to call."""


class _Environment(TypedDict):
    type: Literal["browser"]


class TaskEnvironmentParam(_Environment, total=False):
    """Where a task runs. A browser is the only environment for now.
    `start_url` is the page it opens first, and `live_view` asks for a `live_url`."""

    start_url: str
    live_view: bool


class TaskLimitsParam(TypedDict, total=False):
    """The limits of a task, in seconds and US dollars.
    The gateway sets the ones a request leaves out."""

    max_runtime_seconds: float
    max_cost_usd: float


@dataclass(frozen=True, kw_only=True)
class TaskResult(Generic[_Output]):
    """The agent's answer. `output` is the JSON object that `output_schema` asked for."""

    output_text: str = ""
    output: _Output | None = None


@dataclass(frozen=True, kw_only=True)
class TaskVerification:
    """How the answer was checked: `agent_reported` or `output_schema`.
    `passed` is None when only the agent checked it, and False with `problems`
    when the answer does not match `output_schema`."""

    method: str = ""
    passed: bool | None = None
    problems: list[str] | None = None


@dataclass(frozen=True, kw_only=True)
class TaskUsage:
    """What a task used. `raw` holds every field the gateway sent, such as `browser_minutes`."""

    model_calls: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True, kw_only=True)
class TaskError:
    """Why a task failed, with a code such as `time_limit` or `budget_exceeded`."""

    code: str = ""
    message: str = ""


@dataclass(frozen=True, kw_only=True)
class Task(Generic[_Output]):
    """A browser task. `Task[T]` types `result.output` as T, such as a TypedDict.

    The SDK does not check `result.output`: `verification` says whether it matched
    `output_schema`. `raw` is the task as it came, for the fields these types leave out.

    Attributes:
        id: The ID of the task, such as `task_...`.
        status: `queued`, `running`, `completed`, `failed` or `cancelled`.
        limits: The limits it runs with, the gateway's own where the request left one out.
        result: The answer once it ends. A failed or cancelled task can have one too.
        error: Why it failed, else None.
        trace_available: Whether `tasks.trace` has the agent's record.
        live_url: A link to watch the browser while it runs, with `live_view`.
        cancel_requested: Whether a cancel waits for the running task to stop.
        created_at: When it was queued, as ISO 8601 text, like `started_at` and `finished_at`.
        files_expire_at: When the gateway removes the trace and files, 7 days after it ends.
    """

    id: str = ""
    object: str = "task"
    status: str = ""
    goal: str = ""
    environment: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    limits: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    effort: str | None = None
    metadata: dict[str, Any] | None = None
    result: TaskResult[_Output] | None = None
    verification: TaskVerification | None = None
    usage: TaskUsage | None = None
    error: TaskError | None = None
    trace_available: bool = False
    live_url: str | None = None
    cancel_requested: bool = False
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    files_expire_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True, kw_only=True)
class TaskFile:
    """A file of a task, such as a screenshot, with its `path` and size in `bytes`."""

    path: str = ""
    bytes: int = 0


@dataclass(frozen=True, kw_only=True)
class TaskFileList:
    """The files of a task."""

    object: str = "list"
    data: list[TaskFile] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class TaskFileContent:
    """The bytes of a task's file and its `Content-Type`. The SDK never opens a file."""

    data: bytes = b""
    content_type: str = _FILE_TYPE


class ResponseStream:
    """The events of a streamed response, as an async iterator.

    `create(stream=True)` returns one. It ends after `response.completed`
    or `response.incomplete`, and `response.failed` raises `InferenceError`.
    A cancelled task ends it and raises `CancelledError`.
    `break`, `aclose()` or `async with` end it early and quietly.
    Either way the connection closes, which stops the model's reply.
    A line or an event over 1 MiB fails it with a `server_error` and closes it too.

    Args:
        response: The HTTP response of the call, open on its body.
        deadline: The event loop time the call must end by, or None for no limit.

    Attributes:
        request_id: The `X-Moss-Request-Id` of the response, else None.
    """

    def __init__(self, response: httpx.Response, deadline: float | None) -> None:
        self.request_id: str | None = response.headers.get("x-moss-request-id") or None
        self._response = response
        self._lines = self._split(response.aiter_bytes())
        self._deadline = deadline
        self._closed = False
        self._stepped = False
        self._final: Response | None = None
        self._failure: Exception | None = None

    async def __aiter__(self) -> AsyncIterator[ResponseStreamEvent]:
        try:
            while True:
                try:
                    event = await self.__anext__()
                except StopAsyncIteration:
                    return
                yield event
        finally:
            await self.aclose()

    async def __anext__(self) -> ResponseStreamEvent:
        if self._closed:
            raise StopAsyncIteration
        try:
            event = await _within(self._deadline, self._next_event())
        except BaseException as error:
            closed_by_caller = self._closed
            await self.aclose()
            if closed_by_caller and isinstance(error, Exception):
                raise StopAsyncIteration from None
            failure = error
            if isinstance(error, (httpx.RequestError, asyncio.TimeoutError)):
                failure = _transport_error(error, self._response)
            self._mark(failure)
            if isinstance(failure, Exception):
                self._failure = failure
            if failure is error:
                raise
            raise failure from error
        if self._final is not None:
            await self._finish()
        return event

    async def get_final_response(self) -> Response:
        """The whole response, from the stream's last event.
        It reads the rest first and fails as iteration would,
        or with `incomplete_stream` for a stream closed before its last event."""
        async for _ in self:
            pass
        if self._failure is not None:
            raise self._failure
        if self._final is None:
            error = self._error(
                "The stream was closed before response.completed", "incomplete_stream"
            )
            self._mark(error)
            raise error
        return self._final

    def _mark(self, failure: BaseException) -> None:
        """Mark `failure` with the code `failed_after_tool_call` after an MCP call."""
        if self._stepped and isinstance(failure, InferenceError):
            failure.code = "failed_after_tool_call"

    async def _finish(self) -> None:
        """Close the stream after its last event.
        First, up to 0.1 s within the deadline go to reading the rest of the body,
        so that a connection read to its end can return to the pool for the next call.
        Any failure of that read, such as a line over 1 MiB, only closes the connection.
        """
        cap = asyncio.get_running_loop().time() + 0.1
        deadline = cap if self._deadline is None else min(cap, self._deadline)
        failures = httpx.HTTPError, asyncio.TimeoutError, InferenceError
        try:
            with contextlib.suppress(*failures):
                await _within(deadline, self._rest())
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        """Close the connection. Iteration then stops."""
        self._closed = True
        await self._response.aclose()

    async def __aenter__(self) -> "ResponseStream":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _next_event(self) -> ResponseStreamEvent:
        """The next event. `response.failed` and `error` raise as `InferenceError`."""
        data = await self._next_data()
        if data is None or data == "[DONE]":
            raise self._error(
                "The stream ended before response.completed", "incomplete_stream"
            )
        try:
            event = json.loads(data)
        except ValueError:
            event = None
        if not isinstance(event, dict):
            raise self._error(
                "The stream sent an event that is not a JSON object", "server_error"
            )
        kind = event.get("type")
        if kind in ("response.failed", "error"):
            failed = kind == "response.failed"
            error = (
                _dict(_dict(event.get("response")).get("error")) if failed else event
            )
            message = str(error.get("message") or "The response failed")
            reason = error.get("type") if failed else None
            raise self._error(message, str(reason or "model_error"), _code(error))
        typed = _event(event, self.request_id)
        self._stepped = self._stepped or isinstance(typed.item, McpCall)
        if kind in ("response.completed", "response.incomplete"):
            self._final = typed.response
        return typed

    def _error(
        self, message: str, kind: str, code: str | None = None
    ) -> InferenceError:
        """An error of this stream, with the request id of its response."""
        return _response_error(self._response, message, kind, code=code)

    async def _next_data(self) -> str | None:
        """The data of the next server-sent event, or None at the end of the body."""
        data: bytearray | None = None
        async for line in self._lines:
            if not line and data is not None:
                return data.decode(errors="replace")
            name, _, value = line.partition(b":")
            if name != b"data":
                continue
            if data is None:
                data = bytearray()
            else:
                data += b"\n"
            data += value.removeprefix(b" ")
            if len(data) > _EVENT_BYTES:
                raise self._error(_OVERSIZE, "server_error")
        return None

    async def _rest(self) -> None:
        """Read the body to its end."""
        async for _ in self._lines:
            pass

    async def _split(self, chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        """The lines of a body, split only at CR, LF and CRLF.
        A line over 1 MiB fails the stream, as an event over 1 MiB does.
        Each chunk is scanned only once, however long the line it continues.
        """
        pending = bytearray()
        after_cr = False
        async for chunk in chunks:
            if after_cr and chunk.startswith(b"\n"):
                chunk = chunk[1:]
            after_cr = chunk.endswith(b"\r")
            for line in chunk.splitlines(keepends=True):
                pending += line.rstrip(b"\r\n")
                if len(pending) > _EVENT_BYTES:
                    raise self._error(_OVERSIZE, "server_error")
                if line.endswith((b"\n", b"\r")):
                    yield bytes(pending)
                    pending.clear()
        if pending:
            yield bytes(pending)


class MossInference:
    """A client of Moss inference, with your credentials and a connection pool.

    `api_key` is your own OpenAI, Anthropic or Google key, for a vendor model.
    `moss` ignores it, and a vendor model without one is refused.
    The key is sent as `X-Moss-Provider-Key`, never in the body or an error message.

    Calls go to `https://inference.moss.dev/v1`, or to the base URL in `MOSS_INFERENCE_URL`.

    Bad arguments or a bad URL raise `InferenceError` here, before any request.
    `close()`, or leaving `async with`, closes the connection pool.
    The `tasks` calls never send `api_key`.
    Limits are in seconds, 0 or less turns one off, and `create` can change both.

    Args:
        project_id: The ID of your Moss project.
        project_key: The key of your Moss project.
        api_key: Your own key for a vendor model such as `gpt-4o-mini`, or None.
        timeout: The limit of a whole call, stream included. None turns it off.
        idle_timeout: The limit of each wait for data or a free connection, 120 if None.
        max_retries: The retries of a call that fails before its reply, 2 by default.
        default_headers: Headers for every call, under the headers the SDK sets.

    Attributes:
        responses: The Responses API, called as `client.responses.create(...)`.
        tasks: The Tasks API, called as `client.tasks.create(...)`.
    """

    def __init__(
        self,
        project_id: str,
        project_key: str,
        *,
        api_key: str | None = None,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int = 2,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._authorization = _authorization(project_id, project_key)
        self._base = _base_url(os.environ.get("MOSS_INFERENCE_URL") or _PRODUCTION_URL)
        self._api_key = None if api_key is None else _provider_key(api_key)
        self._default_headers = _header_map(default_headers)
        self._timeout = _limit("timeout", timeout, None)
        self._idle_timeout = _limit("idle_timeout", idle_timeout, _DEFAULT_IDLE_TIMEOUT)
        self._max_retries = _retries(max_retries)
        self._state: tuple[asyncio.AbstractEventLoop, httpx.AsyncClient] | None = None
        self.responses: _Responses = _Responses(self)
        self.tasks: _Tasks = _Tasks(self)

    async def close(self) -> None:
        """Close the connection pool. A later call opens a new one.
        A pool from another event loop cannot close here and is only dropped.
        Its connections then close only when Python collects it, not right away.
        """
        state, self._state = self._state, None
        if state is not None and state[0] is asyncio.get_running_loop():
            await state[1].aclose()

    async def __aenter__(self) -> "MossInference":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    def _pool(self) -> httpx.AsyncClient:
        """The pool of the running event loop, built there on first use.
        The pool of another loop is dropped, not closed, so its calls can go on.
        """
        loop = asyncio.get_running_loop()
        state = self._state
        if state is None or state[0] is not loop:
            state = loop, httpx.AsyncClient(follow_redirects=False, limits=_LIMITS)
            self._state = state
        return state[1]

    async def _send(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        extra_headers: Mapping[str, str] | None,
        content: bytes | None,
        deadline: float | None,
        idle_timeout: float | None,
        retries: int,
        create: bool = False,
        statuses: frozenset[int] = _RETRY_STATUSES,
    ) -> httpx.Response:
        """Send a call to `path` under the base URL, with `headers` over `extra_headers`
        over the client's, and return its successful response, open on its body.
        A failure before the reply starts sends it again, up to `retries` times.
        A `create` carries the `Idempotency-Key` of `extra_headers`, else a new one,
        and the same on every attempt. A key among the client's headers is not used.
        """
        merged = self._default_headers.copy()
        merged.update(_header_map(extra_headers))
        merged.update({**headers, "Authorization": self._authorization})
        if create:
            key = _header_map(extra_headers).get("idempotency-key")
            merged["Idempotency-Key"] = key or str(uuid.uuid4())
        http = self._pool()
        connect = _CONNECT_TIMEOUT
        if idle_timeout is not None:
            connect = min(connect, idle_timeout)
        timeout = httpx.Timeout(
            None, connect=connect, read=idle_timeout, pool=idle_timeout
        )
        url = self._base + path
        request = http.build_request(
            method, url, headers=merged, content=content, timeout=timeout
        )
        for attempt in range(retries + 1):
            try:
                response = await _within(deadline, http.send(request, stream=True))
            except httpx.LocalProtocolError:
                raise _invalid("The headers are not valid HTTP") from None
            except (httpx.RequestError, asyncio.TimeoutError) as error:
                again = isinstance(error, _RETRY_ERRORS)
                if again and await _retry(attempt, retries, deadline, None, statuses):
                    continue
                raise _transport_error(error) from error
            if response.is_success:
                return response
            if await _retry(attempt, retries, deadline, response, statuses):
                continue
            break
        try:
            body = await _within(deadline, _error_body(response))
        except (httpx.TimeoutException, asyncio.TimeoutError) as error:
            raise _transport_error(error, response) from error
        except httpx.RequestError:
            body = b""
        finally:
            await response.aclose()
        raise _status_error(response, body)

    async def _task(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        accept: str = "application/json",
        timeout: float | None,
        idle_timeout: float | None,
        max_retries: int | None,
        extra_headers: Mapping[str, str] | None,
    ) -> httpx.Response:
        """Make a Tasks API call and return its response, read to its end.
        Only a create has a `body`."""
        timeout = _limit("timeout", timeout, self._timeout)
        idle_timeout = _limit("idle_timeout", idle_timeout, self._idle_timeout)
        retries = self._max_retries if max_retries is None else _retries(max_retries)
        headers = {"Accept": accept}
        if body is not None:
            headers["Content-Type"] = "application/json"
        content = None if body is None else _json(body).encode()
        loop = asyncio.get_running_loop()
        deadline = None if timeout is None else loop.time() + timeout
        response = await self._send(
            method,
            path,
            headers,
            extra_headers,
            content,
            deadline,
            idle_timeout,
            retries,
            create=body is not None,
            statuses=_TASK_RETRY_STATUSES,
        )
        try:
            await _within(deadline, response.aread())
        except (httpx.RequestError, asyncio.TimeoutError) as error:
            raise _transport_error(error, response) from error
        finally:
            await response.aclose()
        return response


class _Responses:
    def __init__(self, client: MossInference | None) -> None:
        self._client = client

    @overload
    async def create(
        self,
        *,
        model: str = "moss",
        input: str | Iterable[ResponseInputItemParam],
        stream: Literal[True],
        instructions: str | None = None,
        tools: Sequence[ToolParam] | None = None,
        tool_choice: ToolChoiceParam | None = None,
        parallel_tool_calls: bool | None = None,
        max_output_tokens: int | None = None,
        indexes: Sequence[str] | None = None,
        retrieve: bool = True,
        cache: bool = True,
        api_key: str | None = None,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> ResponseStream: ...

    @overload
    async def create(
        self,
        *,
        model: str = "moss",
        input: str | Iterable[ResponseInputItemParam],
        stream: Literal[False] = False,
        instructions: str | None = None,
        tools: Sequence[ToolParam] | None = None,
        tool_choice: ToolChoiceParam | None = None,
        parallel_tool_calls: bool | None = None,
        max_output_tokens: int | None = None,
        indexes: Sequence[str] | None = None,
        retrieve: bool = True,
        cache: bool = True,
        api_key: str | None = None,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response: ...

    @overload
    async def create(
        self,
        *,
        model: str = "moss",
        input: str | Iterable[ResponseInputItemParam],
        stream: bool,
        instructions: str | None = None,
        tools: Sequence[ToolParam] | None = None,
        tool_choice: ToolChoiceParam | None = None,
        parallel_tool_calls: bool | None = None,
        max_output_tokens: int | None = None,
        indexes: Sequence[str] | None = None,
        retrieve: bool = True,
        cache: bool = True,
        api_key: str | None = None,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response | ResponseStream: ...

    async def create(
        self,
        *,
        model: str = "moss",
        input: str | Iterable[ResponseInputItemParam],
        stream: bool = False,
        instructions: str | None = None,
        tools: Sequence[ToolParam] | None = None,
        tool_choice: ToolChoiceParam | None = None,
        parallel_tool_calls: bool | None = None,
        max_output_tokens: int | None = None,
        indexes: Sequence[str] | None = None,
        retrieve: bool = True,
        cache: bool = True,
        api_key: str | None = None,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Response | ResponseStream:
        """Answer `input` with facts from your Moss indexes.

        None as `timeout`, `idle_timeout` or `max_retries` keeps the client's value,
        and a timeout of 0 or less turns it off for this call only.

        Args:
            model: The model to answer with, `moss` by default, or a vendor model.
            input: The text to answer, or the conversation so far as a list of items:
                OpenAI input item dicts, and the `output` items of earlier responses.
            stream: True streams the response as events, else it comes back whole.
            instructions: The system message, before `input`.
            tools: The tools the model can call: OpenAI function tools and `McpServer`s.
            tool_choice: `none`, `auto`, `required`, or a dict naming a function.
            parallel_tool_calls: Whether the model can call more than one tool at once.
            max_output_tokens: The most tokens the response can have.
            indexes: The indexes to search, by default every index of the project.
                An empty list searches none.
            retrieve: False skips the search.
            cache: False always asks the model, never Moss's reply cache.
            api_key: Your vendor model key for this call, in place of the client's.
            timeout: The seconds the whole call can last, stream included.
            idle_timeout: The seconds each wait for data or a free connection can last.
            max_retries: The retries of this call, in place of the client's.
            extra_headers: Headers over `default_headers`, under the SDK's own.
            extra_body: More request body fields, over `model`, `input` and `kwargs`.
            **kwargs: Other OpenAI arguments, such as `temperature`, sent as is.

        Returns:
            A `ResponseStream` with `stream=True`, else a `Response`.

        Raises:
            InferenceError: The call failed. Bad arguments raise it before any request.
        """
        client = self._client or _from_env()
        for name in _CLIENT_ARGUMENTS:
            if name in kwargs:
                raise _invalid(f"Pass {name} to MossInference, not to create")
        api_key = client._api_key if api_key is None else _provider_key(api_key)
        timeout = _limit("timeout", timeout, client._timeout)
        idle_timeout = _limit("idle_timeout", idle_timeout, client._idle_timeout)
        retries = client._max_retries if max_retries is None else _retries(max_retries)
        headers = _call_headers(indexes, retrieve, cache, api_key)
        typed: dict[str, Any] = {"instructions": instructions, "tools": tools}
        typed.update(tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls)
        typed["max_output_tokens"] = max_output_tokens
        body = {
            "model": model,
            "input": input if isinstance(input, str) else list(input),
            **{name: value for name, value in typed.items() if value is not None},
            **kwargs,
            **(extra_body or {}),
            "stream": True,
        }
        content = _json(body).encode()
        loop = asyncio.get_running_loop()
        deadline = None if timeout is None else loop.time() + timeout
        response = await client._send(
            "POST",
            "/responses",
            headers,
            extra_headers,
            content,
            deadline,
            idle_timeout,
            retries,
        )
        reply = ResponseStream(response, deadline)
        if stream:
            return reply
        return await reply.get_final_response()


class _Tasks:
    """Browser tasks that an agent runs on Moss, within time and dollar limits.

    `create` queues one, `wait` polls it until it ends, and `retrieve`, `cancel`,
    `trace` and `files` read or stop it. A failed call raises `InferenceError`.
    None as `timeout`, `idle_timeout` or `max_retries` keeps the client's value,
    and a timeout of 0 or less turns it off for that call only.
    """

    def __init__(self, client: MossInference | None) -> None:
        self._client = client
        self.files: _TaskFiles = _TaskFiles(client)

    async def create(
        self,
        *,
        goal: str,
        environment: TaskEnvironmentParam,
        output_schema: Mapping[str, Any] | None = None,
        limits: TaskLimitsParam | None = None,
        model: str | None = None,
        effort: Literal["low", "medium", "high"] | None = None,
        metadata: Mapping[str, Any] | None = None,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
    ) -> Task[Any]:
        """Queue a task, which comes back `queued`.

        Only the arguments you give are sent, so the gateway picks the model and
        the limits you leave out, and it refuses a field it does not know.
        Each call sends a new `Idempotency-Key`, or the one in its `extra_headers`,
        and the same one on every retry. The gateway answers a repeated key with the same
        body, within 24 hours, with the task it created, so a retried create never starts
        a second task. To retry a create yourself, pass your own key.

        Args:
            goal: What the agent should do, in plain words.
            environment: Where it runs, `{"type": "browser"}` with an optional
                `start_url` and `live_view`.
            output_schema: A JSON Schema for `result.output`, checked by the gateway.
            limits: `max_runtime_seconds` and `max_cost_usd`.
            model: A model name of the Moss catalog.
            effort: `low`, `medium` or `high`.
            metadata: Your own data, sent back with the task.
            timeout: The seconds the call can last.
            idle_timeout: The seconds each wait for data or a free connection can last.
            max_retries: The retries of this call, in place of the client's.
            extra_headers: Headers over `default_headers`, under the SDK's own.
            extra_body: More body fields, over the ones above.

        Returns:
            The new task, `queued`.
        """
        given: dict[str, Any] = {"goal": goal, "environment": environment}
        given.update(output_schema=output_schema, limits=limits, model=model)
        given.update(effort=effort, metadata=metadata)
        body = {name: value for name, value in given.items() if value is not None}
        body.update(extra_body or {})
        client = self._client or _from_env()
        reply = await client._task(
            "POST",
            "/tasks",
            body=body,
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )
        return _parse_task(_reply_object(reply))

    async def retrieve(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Task[Any]:
        """The task with `task_id`."""
        client = self._client or _from_env()
        reply = await client._task(
            "GET",
            _task_path(task_id),
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )
        return _parse_task(_reply_object(reply))

    async def cancel(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Task[Any]:
        """Stop a task. A queued one comes back `cancelled`.
        A running one comes back with `cancel_requested` and ends `cancelled` soon after.
        """
        client = self._client or _from_env()
        reply = await client._task(
            "POST",
            _task_path(task_id) + "/cancel",
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )
        return _parse_task(_reply_object(reply))

    async def wait(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
        poll_interval: float = _POLL_INTERVAL,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Task[Any]:
        """Poll a task every `poll_interval` seconds until it is neither `queued`
        nor `running`, and return it. A `failed` task returns too, so read its
        `status` and `error`. Each poll is a `retrieve` with the client's timeout.

        Args:
            task_id: The ID of the task.
            timeout: The seconds the whole wait can last, no limit when None or 0.
                Past it, `InferenceError` with type `timeout` is raised, and the task goes on.
            poll_interval: The seconds between polls.
            idle_timeout: The seconds each wait for data or a free connection can last.
            max_retries: The retries of each poll, in place of the client's.
            extra_headers: Headers over `default_headers`, under the SDK's own.

        Returns:
            The task, `completed`, `failed` or `cancelled`.
        """
        limit = _limit("timeout", timeout, None)
        interval = _interval(poll_interval)
        return await self._poll(
            task_id, limit, interval, idle_timeout, max_retries, extra_headers
        )

    async def run(
        self,
        *,
        goal: str,
        environment: TaskEnvironmentParam,
        output_schema: Mapping[str, Any] | None = None,
        limits: TaskLimitsParam | None = None,
        model: str | None = None,
        effort: Literal["low", "medium", "high"] | None = None,
        metadata: Mapping[str, Any] | None = None,
        timeout: float | None = None,
        poll_interval: float = _POLL_INTERVAL,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
    ) -> Task[Any]:
        """Create a task and wait for it, as `create` and then `wait` do.

        `timeout` and `poll_interval` belong to the wait, and the other arguments
        to `create`, except that the create keeps the client's timeout.
        Both are checked before the create, so a bad one sends nothing.

        Returns:
            The task, `completed`, `failed` or `cancelled`.
        """
        limit = _limit("timeout", timeout, None)
        interval = _interval(poll_interval)
        task = await self.create(
            goal=goal,
            environment=environment,
            output_schema=output_schema,
            limits=limits,
            model=model,
            effort=effort,
            metadata=metadata,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
            extra_body=extra_body,
        )
        return await self._poll(
            task.id, limit, interval, idle_timeout, max_retries, extra_headers
        )

    async def _poll(
        self,
        task_id: str,
        limit: float | None,
        interval: float,
        idle_timeout: float | None,
        max_retries: int | None,
        extra_headers: Mapping[str, str] | None,
    ) -> Task[Any]:
        """Retrieve a task every `interval` seconds until it ends, within `limit`.
        Each retrieve gets the time left, or the client's timeout when shorter."""
        own = (self._client or _from_env())._timeout
        loop = asyncio.get_running_loop()
        deadline = math.inf if limit is None else loop.time() + limit
        status = "unfinished"
        while True:
            left = deadline - loop.time()
            bound = own if limit is None else max(min(left, own or math.inf), 0.001)
            try:
                task = await self.retrieve(
                    task_id,
                    timeout=bound,
                    idle_timeout=idle_timeout,
                    max_retries=max_retries,
                    extra_headers=extra_headers,
                )
            except InferenceError as error:
                if error.type == "timeout" and loop.time() >= deadline:
                    raise _late(task_id, status, limit) from error
                error.task_id = error.task_id or task_id
                raise
            if task.status not in _WAITING:
                return task
            status = task.status
            left = deadline - loop.time()
            if left <= 0:
                raise _late(task_id, status, limit)
            await asyncio.sleep(min(interval, left))

    async def trace(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Any:
        """The agent's step-by-step record, the JSON the gateway sent.
        It raises `InferenceError` with `not_found_error` until `trace_available` is True,
        and with `files_expired` after `files_expire_at`, 7 days after the task ends.
        """
        client = self._client or _from_env()
        reply = await client._task(
            "GET",
            _task_path(task_id) + "/trace",
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )
        return _reply_json(reply)


class _TaskFiles:
    """The screenshots and output files of a task."""

    def __init__(self, client: MossInference | None) -> None:
        self._client = client

    async def list(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> TaskFileList:
        """The files of a task once it ends, each with the `path` that `content` takes.
        Before, it raises `task_not_finished`, and after `files_expire_at` `files_expired`.
        """
        client = self._client or _from_env()
        reply = await client._task(
            "GET",
            _task_path(task_id) + "/files",
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )
        data = _reply_object(reply)
        items = [item for item in _list(data.get("data")) if isinstance(item, dict)]
        return TaskFileList(
            **_known(data, "object"), data=[_typed(TaskFile, item) for item in items]
        )

    async def content(
        self,
        task_id: str,
        path: str,
        *,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> TaskFileContent:
        """The bytes and the type of one file, by a `path` that `list` gave,
        such as `screenshots/step-1.png`. The SDK never opens or renders it."""
        client = self._client or _from_env()
        reply = await client._task(
            "GET",
            f"{_task_path(task_id)}/files/{_file_path(path)}",
            accept="*/*",
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )
        kind = reply.headers.get("content-type") or _FILE_TYPE
        return TaskFileContent(data=reply.content, content_type=kind)


responses: _Responses = _Responses(None)
"""`responses.create` on a client built from the environment,
with the credentials of `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY`
and the base URL in `MOSS_INFERENCE_URL`, when it is set."""

tasks: _Tasks = _Tasks(None)
"""`tasks` on a client built from the environment, as `responses` is."""

_default: tuple[tuple[str, ...], MossInference] | None = None
"""The client of `responses`, with the environment it came from."""


def _from_env() -> MossInference:
    """The client of `responses`, built again when the environment changes."""
    global _default
    env = tuple(os.environ.get(name, "") for name in _ENV)
    if _default is None or _default[0] != env:
        if not env[0] or not env[1]:
            raise _invalid(
                "Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY, or use MossInference"
            )
        _default = env, MossInference(env[0], env[1])
    return _default[1]


class MossInferenceSync:
    """A client of the Tasks API whose calls block, for code with no event loop.

    It takes the arguments of `MossInference` but `api_key`, and its `tasks`
    has the calls of `MossInference.tasks`, which return their result here.
    They run on an event loop in a thread of its own, which the first call starts.
    `close()`, or leaving `with`, cancels the calls under way and stops it.
    One left open ends with the interpreter. A fork keeps no threads, so in a forked
    child the first call starts a new thread and connection pool.

    Attributes:
        tasks: The Tasks API, called as `client.tasks.create(...)`.
    """

    def __init__(
        self,
        project_id: str,
        project_key: str,
        *,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int = 2,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._client = MossInference(
            project_id,
            project_key,
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            default_headers=default_headers,
        )
        self._lock = threading.Lock()
        self._loop: tuple[asyncio.AbstractEventLoop, threading.Thread] | None = None
        self.tasks: _SyncTasks = _SyncTasks(self)

    def close(self) -> None:
        """Cancel the calls under way, which then raise `CancelledError`,
        close the connection pool and stop the thread. A later call starts both again.
        """
        with self._lock:
            running, self._loop = self._loop, None
        if running is None or not running[1].is_alive():
            return
        loop, thread = running
        try:
            asyncio.run_coroutine_threadsafe(self._shutdown(), loop).result()
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()
            loop.close()

    def __enter__(self) -> "MossInferenceSync":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    async def _shutdown(self) -> None:
        """Cancel the calls under way, then close the connection pool."""
        current = asyncio.current_task()
        others = [task for task in asyncio.all_tasks() if task is not current]
        for task in others:
            task.cancel()
        await asyncio.gather(*others, return_exceptions=True)
        await self._client.close()

    def _run(
        self, call: Callable[..., Coroutine[Any, Any, _T]], /, **arguments: Any
    ) -> _T:
        """Run `call(**arguments)` on the event loop of a daemon thread, which never
        holds up the interpreter's exit, and wait for its result.
        An interrupt here, such as Ctrl-C, cancels the call there."""
        with self._lock:
            if self._loop is None or not self._loop[1].is_alive():
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=loop.run_forever, name="MossInferenceSync", daemon=True
                )
                thread.start()
                self._loop = loop, thread
            future = asyncio.run_coroutine_threadsafe(call(**arguments), self._loop[0])
        try:
            return future.result()
        except BaseException:
            future.cancel()
            raise


class _SyncTasks:
    """The `tasks` of `MossInferenceSync`: the calls of `MossInference.tasks`, which block."""

    def __init__(self, client: MossInferenceSync) -> None:
        self._sync = client
        self._tasks = client._client.tasks
        self.files: _SyncTaskFiles = _SyncTaskFiles(client)

    def create(
        self,
        *,
        goal: str,
        environment: TaskEnvironmentParam,
        output_schema: Mapping[str, Any] | None = None,
        limits: TaskLimitsParam | None = None,
        model: str | None = None,
        effort: Literal["low", "medium", "high"] | None = None,
        metadata: Mapping[str, Any] | None = None,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
    ) -> Task[Any]:
        """Queue a task, which comes back `queued`, as `MossInference.tasks.create` does."""
        return self._sync._run(
            self._tasks.create,
            goal=goal,
            environment=environment,
            output_schema=output_schema,
            limits=limits,
            model=model,
            effort=effort,
            metadata=metadata,
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
            extra_body=extra_body,
        )

    def retrieve(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Task[Any]:
        """The task with `task_id`."""
        return self._sync._run(
            self._tasks.retrieve,
            task_id=task_id,
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )

    def cancel(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Task[Any]:
        """Stop a task, as `MossInference.tasks.cancel` does."""
        return self._sync._run(
            self._tasks.cancel,
            task_id=task_id,
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )

    def run(
        self,
        *,
        goal: str,
        environment: TaskEnvironmentParam,
        output_schema: Mapping[str, Any] | None = None,
        limits: TaskLimitsParam | None = None,
        model: str | None = None,
        effort: Literal["low", "medium", "high"] | None = None,
        metadata: Mapping[str, Any] | None = None,
        timeout: float | None = None,
        poll_interval: float = _POLL_INTERVAL,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
    ) -> Task[Any]:
        """Create a task and wait for it, as `MossInference.tasks.run` does."""
        return self._sync._run(
            self._tasks.run,
            goal=goal,
            environment=environment,
            output_schema=output_schema,
            limits=limits,
            model=model,
            effort=effort,
            metadata=metadata,
            timeout=timeout,
            poll_interval=poll_interval,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
            extra_body=extra_body,
        )

    def wait(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
        poll_interval: float = _POLL_INTERVAL,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Task[Any]:
        """Poll a task until it ends, as `MossInference.tasks.wait` does."""
        return self._sync._run(
            self._tasks.wait,
            task_id=task_id,
            timeout=timeout,
            poll_interval=poll_interval,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )

    def trace(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> Any:
        """The agent's step-by-step record, as `MossInference.tasks.trace` gives it."""
        return self._sync._run(
            self._tasks.trace,
            task_id=task_id,
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )


class _SyncTaskFiles:
    """The `tasks.files` of `MossInferenceSync`, whose calls block."""

    def __init__(self, client: MossInferenceSync) -> None:
        self._sync = client
        self._tasks = client._client.tasks.files

    def list(
        self,
        task_id: str,
        *,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> TaskFileList:
        """The files of a task once it ends, each with the `path` that `content` takes.
        Before, it raises `task_not_finished`, and after `files_expire_at` `files_expired`.
        """
        return self._sync._run(
            self._tasks.list,
            task_id=task_id,
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )

    def content(
        self,
        task_id: str,
        path: str,
        *,
        timeout: float | None = None,
        idle_timeout: float | None = None,
        max_retries: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> TaskFileContent:
        """The bytes and the type of one file, by a `path` that `list` gave."""
        return self._sync._run(
            self._tasks.content,
            task_id=task_id,
            path=path,
            timeout=timeout,
            idle_timeout=idle_timeout,
            max_retries=max_retries,
            extra_headers=extra_headers,
        )


def _invalid(message: str) -> InferenceError:
    return InferenceError(message, type="invalid_request_error")


def _authorization(project_id: str, project_key: str) -> str:
    """The `Authorization` header of a client's credentials."""
    if not project_id or not project_key:
        raise _invalid("project_id and project_key cannot be empty")
    if not _sendable(project_id) or not _sendable(project_key):
        raise _invalid(
            "project_id and project_key must be printable ASCII "
            "without surrounding spaces"
        )
    if ":" in project_id:
        raise _invalid("project_id cannot contain ':'")
    return f"Bearer {project_id}:{project_key}"


def _base_url(base: str) -> str:
    """`base` without its trailing slash, when it is an http or https URL with a host.
    The error leaves `base` out, since a URL can hold a secret."""
    url = base.removesuffix("/")
    try:
        parts = urlsplit(base)
        valid = (
            _URL_TEXT.fullmatch(base) is not None
            and parts.scheme in ("http", "https")
            and parts.hostname is not None
            and _is_host(parts.hostname)
            and parts.port != 0
            and "@" not in parts.netloc
            and not {"?", "#"} & set(base)
        )
        httpx.URL(url)
    except (ValueError, httpx.InvalidURL):
        valid = False
    if not valid:
        raise _invalid(_BAD_URL)
    return url


def _is_host(host: str) -> bool:
    """Whether `host`, from `urlsplit`, is a name or an IPv6 address.
    A name, an IPv4 address among them, has only letters, digits and `_.~-`,
    and so does the zone after the `%` of an IPv6 address, when there is one."""
    address, percent, zone = host.partition("%")
    try:
        ipaddress.IPv6Address(address)
    except ValueError:
        return _HOST.fullmatch(host) is not None
    return not percent or _HOST.fullmatch(zone) is not None


def _provider_key(api_key: str) -> str:
    """`api_key`, when it can go in a header as is."""
    if not api_key:
        raise _invalid("api_key cannot be empty")
    if not _sendable(api_key):
        raise _invalid("api_key must be printable ASCII without surrounding spaces")
    return api_key


def _call_headers(
    indexes: Sequence[str] | None, retrieve: bool, cache: bool, api_key: str | None
) -> dict[str, str]:
    names = [indexes] if isinstance(indexes, str) else list(indexes or ())
    for name in names:
        if not _sendable(name) or "," in name:
            raise _invalid(
                f"Invalid index name {name!r}: it is empty, has a ',' "
                "or is not printable ASCII"
            )
    retrieve = retrieve and (indexes is None or bool(names))
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-Moss-Indexes": ",".join(names) or None,
        "X-Moss-Retrieve": None if retrieve else "off",
        "X-Moss-Cache": None if cache else "off",
        "X-Moss-Provider-Key": api_key,
    }
    return {name: value for name, value in headers.items() if value is not None}


def _header_map(headers: Mapping[str, str] | None) -> httpx.Headers:
    """`headers`, when each name is an HTTP token and each value printable ASCII.
    Host, Content-Length and Transfer-Encoding are refused, since httpx sets them.
    """
    try:
        checked = httpx.Headers(headers or {})
    except (TypeError, UnicodeEncodeError):
        checked = None
    if checked is None or not all(
        _TOKEN.fullmatch(name) and (value == "" or _sendable(value))
        for name, value in checked.multi_items()
    ):
        raise _invalid(
            "A header name is not an HTTP token, or a value is not printable ASCII"
        )
    if not _HTTP_HEADERS.isdisjoint(checked.keys()):
        raise _invalid("Host, Content-Length and Transfer-Encoding cannot be set")
    return checked


def _sendable(value: object) -> bool:
    """Whether `value` is printable ASCII, not empty and with no space at either end."""
    return (
        isinstance(value, str)
        and value != ""
        and value.isascii()
        and value.isprintable()
        and value == value.strip()
    )


def _limit(name: str, value: float | None, default: float | None) -> float | None:
    """The limit of `value` seconds, None for no limit.
    `default` stands in for None, and 0 or less turns the limit off."""
    if value is None:
        return default
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    try:
        seconds = float(value) if number else math.nan
    except OverflowError:
        seconds = math.nan
    if math.isnan(seconds):
        raise _invalid(f"{name} must be a number of seconds, or None")
    return seconds if seconds > 0 else None


def _retries(value: int) -> int:
    """`value`, when it is a whole number of retries."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _invalid("max_retries must be a whole number, 0 or more")
    return value


async def _retry(
    attempt: int,
    retries: int,
    deadline: float | None,
    response: httpx.Response | None,
    statuses: frozenset[int] = _RETRY_STATUSES,
) -> bool:
    """Whether a call that failed before its reply goes again, after a wait.

    `response` is None for a connection failure, else it is closed to go again.
    `x-should-retry` decides when it is `true` or `false`, and else its status:
    one of `statuses` or a 5xx.
    The wait is a `Retry-After` of at most 60 s, else 0.5 s doubled for each attempt,
    at most 8 s and up to a quarter less at random. A wait past `deadline` gives False.
    """
    if attempt >= retries:
        return False
    after = None
    if response is not None:
        status = response.status_code
        should = response.headers.get("x-should-retry", "")
        again = status in statuses or status >= 500
        if not {"true": True, "false": False}.get(should, again):
            return False
        after = _seconds(response.headers.get("retry-after", ""))
    wait = min(0.5 * 2 ** min(attempt, 4), 8.0) * (1 - random.random() / 4)
    wait = after if after is not None and after <= 60 else wait
    if deadline is not None and asyncio.get_running_loop().time() + wait >= deadline:
        return False
    if response is not None:
        await response.aclose()
    await asyncio.sleep(wait)
    return True


async def _within(deadline: float | None, step: Awaitable[_T]) -> _T:
    if deadline is None:
        return await step
    remaining = deadline - asyncio.get_running_loop().time()
    return await asyncio.wait_for(step, max(remaining, 0.0))


def _transport_error(
    error: Exception, response: httpx.Response | None = None
) -> InferenceError:
    """The error of a timeout, a stream cut short, or a lost connection.

    With no `response` yet, a lost connection means the service was not reached.
    After one, a body cut short when the peer closes the connection is a cut stream.
    """
    cut = isinstance(error, httpx.RemoteProtocolError) and "peer closed" in str(error)
    if isinstance(error, httpx.ReadTimeout):
        message, kind = "Nothing came within idle_timeout", "timeout"
    elif isinstance(error, httpx.PoolTimeout):
        message, kind = "No connection was free within idle_timeout", "timeout"
    elif isinstance(error, (asyncio.TimeoutError, httpx.TimeoutException)):
        message, kind = "The call timed out", "timeout"
    elif response is None:
        message = f"Could not reach the inference service: {error!r}"
        kind = "connection_error"
    elif cut:
        message, kind = (
            "The stream ended before response.completed",
            "incomplete_stream",
        )
    else:
        message, kind = f"The connection failed: {error!r}", "connection_error"
    if response is None:
        return InferenceError(message, type=kind)
    return _response_error(response, message, kind)


def _response_error(
    response: httpx.Response,
    message: str,
    kind: str,
    *,
    status: int | None = None,
    code: str | None = None,
) -> InferenceError:
    """An error after `response` arrived, with its `X-Moss-Request-Id`
    and, when it is an error response, the delay in its `Retry-After`."""
    headers = response.headers
    delay = None if response.is_success else _seconds(headers.get("retry-after", ""))
    return InferenceError(
        message,
        type=kind,
        status=status,
        code=code,
        request_id=headers.get("x-moss-request-id") or None,
        retry_after=delay,
    )


def _seconds(value: str) -> float | None:
    """The seconds of a `Retry-After`.
    A date or any value but delta-seconds gives None."""
    if not (value.isascii() and value.isdigit()):
        return None
    seconds = float(value)
    return seconds if math.isfinite(seconds) else None


def _code(error: dict[str, Any]) -> str | None:
    """The `code` of an error object as text, when it is a string or an integer."""
    code = error.get("code")
    if isinstance(code, int) and not isinstance(code, bool):
        return str(code)
    return code if isinstance(code, str) else None


async def _error_body(response: httpx.Response) -> bytes:
    """The first 64 KiB of the body of a refused request."""
    body = b""
    async for chunk in response.aiter_bytes():
        body += chunk
        if len(body) >= _ERROR_BODY_BYTES:
            break
    return body[:_ERROR_BODY_BYTES]


def _status_error(response: httpx.Response, body: bytes) -> InferenceError:
    """The error of a refused request, from its JSON body, its text, or its status."""
    text = body.decode(errors="replace")
    try:
        payload = json.loads(text)
        excerpt = ""
    except ValueError:
        payload, excerpt = None, " ".join(text.split())
    if len(excerpt) > _EXCERPT_CHARS:
        excerpt = excerpt[: _EXCERPT_CHARS - 3] + "..."
    payload = _dict(payload)
    error = payload.get("error")
    error = {"message": error} if isinstance(error, str) else _dict(error)
    message = error.get("message") or payload.get("detail") or excerpt
    if message and not isinstance(message, str):
        message = json.dumps(message)
    status = response.status_code
    kind = error.get("type")
    if not isinstance(kind, str) or not kind:
        fallback = "invalid_request_error" if 400 <= status < 500 else "server_error"
        kind = _STATUS_TYPES.get(status, fallback)
    message = message or f"HTTP {status} {response.reason_phrase}".strip()
    return _response_error(response, message, kind, status=status, code=_code(error))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


_ITEMS: dict[Any, Any] = {
    "message": ResponseOutputMessage,
    "function_call": ResponseFunctionToolCall,
    "mcp_call": McpCall,
}


def _event(data: dict[str, Any], request_id: str | None) -> ResponseStreamEvent:
    """An event from a decoded event, without its unknown or null keys."""
    names = ("type", "sequence_number", "output_index", "item_id", "content_index")
    known = _known(data, *names, "delta", "text", "arguments")
    response = data.get("response")
    if isinstance(response, dict):
        known["response"] = _response(response, request_id)
    if isinstance(data.get("item"), dict):
        known["item"] = _item(data["item"])
    return ResponseStreamEvent(**known, raw=data)


def _response(data: dict[str, Any], request_id: str | None) -> Response:
    """A response from its decoded object."""
    usage = data.get("usage")
    if usage is not None:
        counts = _dict(usage)
        usage = _typed(
            ResponseUsage,
            counts,
            input_tokens_details=_typed(
                InputTokensDetails, counts.get("input_tokens_details")
            ),
            output_tokens_details=_typed(
                OutputTokensDetails, counts.get("output_tokens_details")
            ),
        )
    names = ("id", "object", "created_at", "status", "model", "instructions")
    return Response(
        **_known(data, *names, "metadata"),
        output=[
            _item(item) for item in _list(data.get("output")) if isinstance(item, dict)
        ],
        usage=usage,
        incomplete_details=_typed(IncompleteDetails, data.get("incomplete_details")),
        raw=data,
        request_id=request_id,
    )


def _item(data: dict[str, Any]) -> ResponseOutputItem:
    """A typed output item, or the dict it came as when its type has no class here."""
    kind = _ITEMS.get(data["type"]) if isinstance(data.get("type"), str) else None
    if kind is None:
        return data
    if kind is ResponseOutputMessage:
        content = [
            (
                _typed(ResponseOutputText, part)
                if part.get("type") == "output_text"
                else part
            )
            for part in _list(data.get("content"))
            if isinstance(part, dict)
        ]
        return _typed(kind, data, content=content, raw=data)
    return _typed(kind, data, raw=data)


def _typed(kind: Any, data: Any, **values: Any) -> Any:
    """A `kind` from `values` and the fields `data` has, or None when not a dict."""
    if not isinstance(data, dict):
        return None
    names = [item.name for item in fields(kind) if item.name not in values]
    return kind(**_known(data, *names), **values)


def _known(data: Any, *names: str) -> dict[str, Any]:
    """The `names` that `data` has a value for, when it is a dict.
    A null is left out, so its field keeps its default, as when the key is missing."""
    return {k: v for k, v in _dict(data).items() if k in names and v is not None}


def _json(body: dict[str, Any]) -> str:
    """`body` as JSON text, or `invalid_request_error` when it has no JSON form."""
    try:
        return json.dumps(body, separators=(",", ":"), allow_nan=False, default=_plain)
    except (TypeError, ValueError) as error:
        raise _invalid(f"The request body is not valid JSON: {error}") from None


def _task_path(task_id: str) -> str:
    """The URL path of a task, after its ID is checked and encoded."""
    if not isinstance(task_id, str) or task_id in ("", ".", ".."):
        raise _invalid("task_id must be the ID of a task, such as task_...")
    return "/tasks/" + quote(task_id, safe="")


def _file_path(path: str) -> str:
    """The URL path of a task's file, each part encoded.
    An empty, `.` or `..` part is an error, since it would change the URL."""
    parts = path.split("/") if isinstance(path, str) else [""]
    if any(part in ("", ".", "..") for part in parts):
        raise _invalid(
            "path must be a path that files.list gave, such as screenshots/step-1.png"
        )
    return "/".join(quote(part, safe="") for part in parts)


def _late(task_id: str, status: str, limit: float | None) -> InferenceError:
    """The error of a wait that ran out of time, which leaves the task running."""
    return InferenceError(
        f"Task {task_id} is still {status} after {limit:g} s. "
        "It goes on: wait again or cancel it.",
        type="timeout",
        task_id=task_id,
    )


def _interval(value: float) -> float:
    """`value`, when it is a positive number of seconds."""
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    if not number or not 0 < value < math.inf:
        raise _invalid("poll_interval must be a positive number of seconds")
    return float(value)


def _reply_json(response: httpx.Response) -> Any:
    """The JSON of a Tasks API reply."""
    try:
        return json.loads(response.content)
    except ValueError:
        message = "The gateway sent a reply that is not JSON"
        raise _response_error(response, message, "server_error") from None


def _reply_object(response: httpx.Response) -> dict[str, Any]:
    """The JSON object of a Tasks API reply."""
    value = _reply_json(response)
    if not isinstance(value, dict):
        message = "The gateway sent a reply that is not a JSON object"
        raise _response_error(response, message, "server_error")
    return value


_TASK_PARTS = frozenset({"result", "verification", "usage", "error", "raw"})


def _parse_task(data: dict[str, Any]) -> Task[Any]:
    """A task from its decoded object."""
    names = [item.name for item in fields(Task) if item.name not in _TASK_PARTS]
    usage = data.get("usage")
    return Task(
        **_known(data, *names),
        result=_typed(TaskResult, data.get("result")),
        verification=_typed(TaskVerification, data.get("verification")),
        usage=_typed(TaskUsage, usage, raw=_dict(usage)),
        error=_typed(TaskError, data.get("error")),
        raw=data,
    )


def _plain(value: Any) -> Any:
    """JSON for this module's types: `raw` when it is set,
    else every field that is not None, except `raw` itself. A mapping is a dict."""
    if is_dataclass(value) and not isinstance(value, type):
        if raw := getattr(value, "raw", None):
            return raw
        names = (f.name for f in fields(value) if f.name != "raw")
        pairs = ((name, getattr(value, name)) for name in names)
        return {k: v for k, v in pairs if v is not None}
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
