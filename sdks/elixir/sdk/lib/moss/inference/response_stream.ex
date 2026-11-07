defmodule Moss.Inference.ResponseStream do
  @moduledoc """
  A streamed response: an `Enumerable` of the events of OpenAI's Responses API, as decoded maps.

  Each event has string keys and its `"type"`, such as `"response.output_text.delta"` with its
  `"delta"`, or `"response.output_item.added"` and `"response.output_item.done"` with an `"item"`.
  The last event is `"response.completed"`, or `"response.incomplete"` for a response cut
  by `max_output_tokens`, and its `"response"` is the whole response. The stream ends after it.
  An item of type `"mcp_call"` is a call Moss made to an MCP server.
  A `"response.failed"` or `"error"` event raises `Moss.Inference.Error` where it comes,
  after the events before it, and so does any other failure once the response has started,
  with code `"failed_after_tool_call"` once an `"mcp_call"` item has come.
  An event or line over 1 MiB raises `"server_error"` and closes the connection.
  A connection reset raises `"incomplete_stream"`, since Erlang's `:ssl` reports it as a close.

  The connection belongs to the process that called
  `Moss.Inference.Responses.create/3`, so enumerate the stream there, and only once.
  A stream read to its end gives its connection back for the next call.
  Halting early, for example with `Enum.take/2`, closes the connection and stops the model,
  and so does a failure. `close/1` does the same from any process, after which the stream
  ends without an error.
  """

  alias Moss.Inference.{Error, Pool, Request}

  @drain_timeout 1_000

  # The most bytes one line, or the data of one event, may hold.
  @event_limit 1_048_576

  # The types of the event that ends a response.
  @last ["response.completed", "response.incomplete"]

  # Slots of the flags every copy of a stream shares.
  @claimed 1
  @connection 2

  # The @connection slot: the stream holds it, close/1 closed it, or the stream let it go.
  @open 0
  @closed 1
  @released 2

  # `details` holds the error fields each failure of the reply carries.
  @derive {Inspect, only: []}
  defstruct [:conn, :received, :owner, :limits, :flags, :origin, :details, :request_id]

  @typedoc """
  A stream. `request_id` is the reply's `X-Moss-Request-Id` header, else `nil`.
  The other fields are internal.
  """
  @type t :: %__MODULE__{request_id: String.t() | nil}

  @doc """
  Closes the connection of a stream that will not be read to the end.

  A stream that already ended has let its connection go, and is left as it is.
  """
  @spec close(t()) :: :ok
  def close(%__MODULE__{conn: conn, flags: flags}) do
    if :atomics.compare_exchange(flags, @connection, @open, @closed) == :ok,
      do: Mint.HTTP1.close(conn)

    :ok
  end

  # The calling process owns the connection and reads it,
  # and only a reply read to its end gives it back to the pool.
  @doc false
  @spec open(URI.t(), [{String.t(), String.t()}], binary(), Request.settings()) ::
          {:ok, t()} | {:error, Error.t()}
  def open(%URI{} = uri, headers, body, settings) do
    headers = [{"content-type", "application/json"} | headers]

    with {:ok, reply} <- Request.open("POST", uri, headers, body, settings, [408, 409, 429]) do
      {:ok,
       %__MODULE__{
         conn: reply.conn,
         received: reply.received,
         owner: self(),
         limits: reply.limits,
         flags: :atomics.new(2, []),
         origin: reply.origin,
         details: %{request_id: reply.request_id},
         request_id: reply.request_id
       }}
    end
  end

  @doc false
  def resource(%__MODULE__{} = stream) do
    Stream.resource(fn -> claim(stream) end, &next/1, &finish/1)
  end

  defp claim(%__MODULE__{owner: owner, flags: flags} = stream) do
    cond do
      self() != owner ->
        raise ArgumentError, "enumerate the stream in the process that created it"

      :atomics.compare_exchange(flags, @claimed, 0, 1) != :ok ->
        raise ArgumentError, "the stream was already read"

      true ->
        state = %{stream: stream, conn: stream.conn, received: stream.received}
        Map.merge(state, %{buffer: "", data: nil, events: [], ended: false})
    end
  end

  defp next(state), do: if(closed?(state), do: {:halt, state}, else: step(state))

  # The last event ends the stream, and whatever came after it is dropped.
  defp step(%{events: [{:event, %{"type" => type} = event} | _]} = state) when type in @last,
    do: {[event], %{state | events: [:end]}}

  # Once an MCP tool has run, it may have changed data, and every error after it says so.
  defp step(%{events: [{:event, %{"item" => %{"type" => "mcp_call"}} = event} | rest]} = state) do
    state = put_in(state.stream.details[:code], "failed_after_tool_call")
    {[event], %{state | events: rest}}
  end

  defp step(%{events: [{:event, event} | rest]} = state), do: {[event], %{state | events: rest}}
  defp step(%{events: [:end | _]} = state), do: {:halt, drain(state, drain_limits(state))}
  defp step(%{events: [{:error, error} | _]} = state), do: fail(state, error)

  defp step(%{events: []} = state) do
    case Request.await_part(state, state.stream.limits) do
      {:part, part, state} -> next(parse(state, part))
      {:end, state} -> halt_or_raise(state, incomplete())
      {{:failed, reason}, state} -> halt_or_raise(state, failure(state.stream, reason))
    end
  end

  # A stream closed with close/1, here or in another process, ends without an error.
  defp halt_or_raise(state, error),
    do: if(closed?(state), do: {:halt, state}, else: fail(state, error))

  defp fail(state, error), do: raise(struct(error, state.stream.details))

  defp closed?(state), do: :atomics.get(state.stream.flags, @connection) == @closed

  # Reads the rest of the reply after the last event, for @drain_timeout ms at most,
  # so that a connection read to its end can serve the next call to the gateway.
  defp drain(state, limits) do
    case Request.await_part(state, limits) do
      {:part, _part, state} -> drain(state, limits)
      {:end, state} -> %{state | ended: true}
      {{:failed, _reason}, state} -> state
    end
  end

  defp drain_limits(%{stream: %{limits: {deadline, idle}}}),
    do: {min(deadline, now() + @drain_timeout), idle}

  # Only a reply read to its end gives its connection back, idle from then,
  # unless close/1 got there first.
  defp finish(%{stream: stream, conn: conn} = state) do
    released? = :atomics.compare_exchange(stream.flags, @connection, @open, @released) == :ok

    if released? and state.ended,
      do: Pool.checkin(stream.origin, Mint.HTTP1.put_private(conn, :idle_since, now())),
      else: Mint.HTTP1.close(conn)
  end

  # Splits only the new part, so a long line is not scanned again as each part arrives.
  defp parse(state, part) do
    {lines, buffer} =
      case :binary.split(part, "\n", [:global]) do
        [partial] ->
          {[], state.buffer <> partial}

        [first | more] ->
          {lines, [partial]} = Enum.split(more, -1)
          {[state.buffer <> first | lines], partial}
      end

    case Enum.reduce_while(lines, {state.data, []}, &line/2) do
      {:over, events} ->
        too_large(state, events)

      {_data, events} when byte_size(buffer) > @event_limit ->
        too_large(state, events)

      {data, events} ->
        %{state | buffer: buffer, data: data, events: Enum.reverse(events)}
    end
  end

  # `data` is the event's data so far, or nil before its first data line.
  defp line(line, {_data, events}) when byte_size(line) > @event_limit,
    do: {:halt, {:over, events}}

  defp line(line, {data, events}) do
    case String.trim_trailing(line, "\r") do
      "" when data == nil -> {:cont, {nil, events}}
      "" -> {:cont, {nil, [event(data) | events]}}
      "data:" <> value -> add_data(data, String.replace_prefix(value, " ", ""), events)
      _comment_or_other_field -> {:cont, {data, events}}
    end
  end

  defp add_data(nil, value, events), do: {:cont, {value, events}}

  defp add_data(data, value, events) when byte_size(data) + 1 + byte_size(value) > @event_limit,
    do: {:halt, {:over, events}}

  defp add_data(data, value, events), do: {:cont, {<<data::binary, ?\n, value::binary>>, events}}

  # Drops what the stream holds, and fails after the events that came before.
  defp too_large(state, events) do
    error = %Error{type: "server_error", message: "The gateway sent an event over 1 MiB."}
    %{state | buffer: "", data: nil, events: Enum.reverse([{:error, error} | events])}
  end

  # A response never ends with [DONE], so one that comes first cuts the stream.
  defp event("[DONE]"), do: {:error, incomplete()}

  defp event(data) do
    case Jason.decode(data) do
      {:ok, %{"type" => "response.failed", "response" => %{"error" => %{} = error}}} ->
        {:error, event_error(error, error["type"])}

      {:ok, %{"type" => "response.failed"}} ->
        {:error, event_error(%{}, nil)}

      {:ok, %{"type" => "error"} = error} ->
        {:error, event_error(error, nil)}

      {:ok, event} when is_map(event) ->
        {:event, event}

      _not_an_object ->
        {:error,
         %Error{type: "server_error", message: "The gateway sent an event that is not JSON."}}
    end
  end

  defp event_error(error, type) do
    %Error{
      type: if(is_binary(type), do: type, else: "model_error"),
      message:
        if(is_binary(error["message"]), do: error["message"], else: "The response failed."),
      code: Request.code(error)
    }
  end

  defp failure(stream, %Mint.TransportError{reason: :timeout}),
    do: Request.timeout_error(stream.limits)

  defp failure(_stream, %Mint.TransportError{reason: :closed}), do: incomplete()

  defp failure(_stream, reason) do
    %Error{
      type: "connection_error",
      message: "The connection to the gateway failed: #{Exception.message(reason)}"
    }
  end

  defp incomplete,
    do: %Error{type: "incomplete_stream", message: "The stream ended before response.completed."}

  defp now, do: System.monotonic_time(:millisecond)
end

defimpl Enumerable, for: Moss.Inference.ResponseStream do
  def reduce(stream, acc, fun),
    do: Moss.Inference.ResponseStream.resource(stream).(acc, fun)

  def count(_stream), do: {:error, __MODULE__}
  def member?(_stream, _value), do: {:error, __MODULE__}
  def slice(_stream), do: {:error, __MODULE__}
end
