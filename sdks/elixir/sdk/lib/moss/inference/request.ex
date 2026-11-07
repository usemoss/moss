defmodule Moss.Inference.Request do
  @moduledoc false

  # One call to the gateway on a pooled or new connection, sent again on a failure
  # before its reply starts, up to the start of a 2xx reply or an error.
  #
  # The calling process owns the connection and reads it,
  # and only a reply read to its end gives it back to the pool.

  alias Moss.Inference.{Error, Pool}

  @connect_timeout 10_000
  @body_part 65_536
  @error_body 65_536

  @typedoc "The monotonic ms a call must end by, and how long the gateway may stay silent."
  @type limits :: {integer() | :infinity, timeout()}

  @type headers :: [{String.t(), String.t()}]

  @typedoc "The whole call's timeout, the idle timeout and the retries."
  @type settings :: {timeout(), timeout(), non_neg_integer()}

  @typedoc "A 2xx reply whose body is still to read, from `received` and then `conn`."
  @type reply :: %{
          conn: Mint.HTTP1.t(),
          received: [term()],
          origin: Pool.origin(),
          limits: limits(),
          headers: headers(),
          request_id: String.t() | nil
        }

  @doc """
  Sends a call and returns its 2xx reply, open on its body.

  `body` is nil for a call without one. A failure before the reply's headers goes again
  within the retries and the timeout: a failed connection, a 5xx, or a 4xx in `statuses`.
  An error reply's `x-should-retry` header decides when it has one.
  """
  @spec open(String.t(), URI.t(), headers(), binary() | nil, settings(), [400..499]) ::
          {:ok, reply()} | {:error, Error.t()}
  def open(method, %URI{} = uri, headers, body, {timeout, idle_timeout, retries}, statuses) do
    limits = {if(timeout == :infinity, do: :infinity, else: now() + timeout), idle_timeout}

    # A host with a colon is an IPv6 address, which Mint reaches only with inet6.
    options = [
      mode: :passive,
      optional_responses: [:status_reason],
      transport_opts: [
        send_timeout: min(idle_timeout, timeout),
        send_timeout_close: true,
        inet6: String.contains?(uri.host, ":")
      ]
    ]

    call = %{
      method: method,
      uri: uri,
      headers: headers,
      body: body,
      options: options,
      statuses: statuses
    }

    retry(fn -> attempt(call, limits) end, limits, retries, 0)
  end

  @doc """
  Sends a call and returns its 2xx reply read to its end, which gives its connection back.

  A reply that breaks off is a `"connection_error"`, or a `"timeout"`, with its request id.
  """
  @spec fetch(String.t(), URI.t(), headers(), binary() | nil, settings(), [400..499]) ::
          {:ok, %{body: binary(), headers: headers(), request_id: String.t() | nil}}
          | {:error, Error.t()}
  def fetch(method, uri, headers, body, settings, statuses) do
    with {:ok, reply} <- open(method, uri, headers, body, settings, statuses),
         do: read(reply, [])
  end

  defp read(reply, parts) do
    case await_part(reply, reply.limits) do
      {:part, part, reply} ->
        read(reply, [parts | part])

      {:end, reply} ->
        Pool.checkin(reply.origin, Mint.HTTP1.put_private(reply.conn, :idle_since, now()))
        body = IO.iodata_to_binary(parts)
        {:ok, %{body: body, headers: reply.headers, request_id: reply.request_id}}

      {{:failed, reason}, reply} ->
        Mint.HTTP1.close(reply.conn)
        {:error, %{broken(reason, reply.limits) | request_id: reply.request_id}}
    end
  end

  defp broken(%Mint.TransportError{reason: :timeout}, limits), do: timeout_error(limits)

  defp broken(reason, _limits) do
    %Error{
      type: "connection_error",
      message: "The gateway's reply broke off: #{Exception.message(reason)}"
    }
  end

  # Sends the call again while retries are left and the wait ends before the deadline.
  # A wait is the reply's Retry-After up to 60 s, else 0.5 s doubled per retry up to 8 s, less up to 25%.
  defp retry(attempt, {deadline, _idle} = limits, retries, count) do
    with {:retry, error} <- attempt.() do
      wait =
        if error.retry_after in 0..60_000,
          do: error.retry_after,
          else: round(min(500 * 2 ** count, 8_000) * (1 - :rand.uniform() / 4))

      if count < retries and wait < remaining(deadline) do
        Process.sleep(wait)
        retry(attempt, limits, retries, count + 1)
      else
        {:error, error}
      end
    end
  end

  # The reply, or `{:retry, error}` for a failure the call may be sent again after.
  # A timeout while connecting is one, and its error has type "timeout" like any other timeout.
  defp attempt(call, limits) do
    with {:ok, conn} <- connection(call.uri, call.options, limits) do
      case request(conn, call) do
        {:ok, conn} -> await_start(conn, call, limits, [])
        {:error, conn, reason} -> await_start(conn, call, limits, [{:failed, reason}])
      end
    else
      {:error, %Mint.TransportError{reason: :timeout}} -> {:retry, timeout_error()}
      {:error, reason} -> failed(reason)
    end
  end

  # A connection that fails before the reply's headers may be retried.
  defp failed(%Mint.TransportError{} = reason), do: {:retry, unreachable(reason)}
  defp failed(reason), do: {:error, unreachable(reason)}

  # An idle connection the gateway has not closed, else a new one.
  #
  # A pooled connection is checked before anything is written to it,
  # so replacing a closed one never sends the call twice. Over TLS the check
  # sees only what the ssl process already read, and the pool catches a close while idle.
  # One that comes back after the call ran out of time goes back unused, and the call times out.
  defp connection(uri, options, {deadline, _idle} = limits) do
    case Pool.checkout(origin(uri), connect_time(limits), deadline) do
      nil ->
        connect(uri, options, limits)

      conn ->
        cond do
          remaining(deadline) == 0 ->
            Pool.checkin(origin(uri), conn)
            {:error, %Mint.TransportError{reason: :timeout}}

          open?(conn, uri, options[:transport_opts][:send_timeout]) ->
            {:ok, conn}

          true ->
            Mint.HTTP1.close(conn)
            connect(uri, options, limits)
        end
    end
  end

  # A call with no time left times out before it connects.
  defp connect(uri, options, limits) do
    case connect_time(limits) do
      0 ->
        {:error, %Mint.TransportError{reason: :timeout}}

      time ->
        options = put_in(options, [:transport_opts, :timeout], time)
        Mint.HTTP1.connect(scheme(uri), uri.host, uri.port, options)
    end
  end

  # How long a checkout or a new connection may take:
  # the call's time left, within the idle limit and @connect_timeout.
  defp connect_time({deadline, idle}), do: Enum.min([@connect_timeout, remaining(deadline), idle])

  # A read that times out at once found no close and no stray bytes.
  defp open?(conn, uri, send_timeout) do
    case Mint.HTTP1.recv(conn, 0, 0) do
      {:error, _conn, %Mint.TransportError{reason: :timeout}, []} ->
        setopts(uri, Mint.HTTP1.get_socket(conn), send_timeout: send_timeout) == :ok

      _closed_or_stray_bytes ->
        false
    end
  end

  defp setopts(%URI{scheme: "https"}, socket, opts), do: :ssl.setopts(socket, opts)
  defp setopts(_uri, socket, opts), do: :inet.setopts(socket, opts)

  defp origin(uri), do: {scheme(uri), uri.host, uri.port}

  # A POST without a body says so, since a proxy may refuse one without a length.
  defp request(conn, %{body: nil} = call) do
    headers =
      if call.method == "POST",
        do: [{"content-length", "0"} | call.headers],
        else: call.headers

    with {:ok, conn, _ref} <- Mint.HTTP1.request(conn, call.method, call.uri.path, headers, nil),
         do: {:ok, conn}
  end

  # Sends the body in parts, since send_timeout only limits a send that waits behind another.
  defp request(conn, %{body: body} = call) do
    headers = [{"content-length", Integer.to_string(byte_size(body))} | call.headers]

    with {:ok, conn, ref} <-
           Mint.HTTP1.request(conn, call.method, call.uri.path, headers, :stream),
         do: send_body(conn, ref, body)
  end

  defp send_body(conn, ref, <<part::binary-size(@body_part), rest::binary>>) when rest != "" do
    with {:ok, conn} <- Mint.HTTP1.stream_request_body(conn, ref, part),
         do: send_body(conn, ref, rest)
  end

  defp send_body(conn, ref, body) do
    with {:ok, conn} <- Mint.HTTP1.stream_request_body(conn, ref, body),
         do: Mint.HTTP1.stream_request_body(conn, ref, :eof)
  end

  defp scheme(%URI{scheme: "https"}), do: :https
  defp scheme(_uri), do: :http

  defp await_start(conn, call, limits, received) do
    case Enum.split_while(received, &(elem(&1, 0) not in [:headers, :failed])) do
      {head, [{:headers, _ref, headers} | rest]} ->
        if informational?(head),
          do: await_start(conn, call, limits, rest),
          else:
            start(
              %{conn: conn, received: rest, origin: origin(call.uri)},
              call,
              limits,
              head,
              headers
            )

      {_head, [{:failed, %Mint.TransportError{reason: :timeout}} | _]} ->
        Mint.HTTP1.close(conn)
        {:error, timeout_error(limits)}

      {_head, [{:failed, reason} | _]} ->
        Mint.HTTP1.close(conn)
        failed(reason)

      {_head, []} ->
        {conn, more} = recv(conn, limits)
        await_start(conn, call, limits, received ++ more)
    end
  end

  # A reply such as 103 Early Hints, which comes before the final one.
  defp informational?(head) do
    match?(
      {:status, _ref, status} when status in 100..199 and status != 101,
      List.keyfind(head, :status, 0)
    )
  end

  defp start(state, call, limits, head, headers) do
    {:status, _ref, status} = List.keyfind(head, :status, 0)

    if status in 200..299 do
      fields = %{limits: limits, headers: headers, request_id: request_id(headers)}
      {:ok, Map.merge(state, fields)}
    else
      {ending, body, state} = read_body(state, limits, "")
      Mint.HTTP1.close(state.conn)
      {deadline, _idle} = limits

      error =
        if match?({:failed, %Mint.TransportError{reason: :timeout}}, ending) or
             remaining(deadline) == 0 do
          timeout_error(limits)
        else
          phrase = for {:status_reason, _ref, phrase} <- head, into: "", do: phrase
          status_error(status, phrase, body)
        end

      error = %{error | request_id: request_id(headers), retry_after: retry_after(headers)}
      {if(retry?(error, headers, call.statuses), do: :retry, else: :error), error}
    end
  end

  # An error reply's x-should-retry header wins over its status.
  defp retry?(%Error{status: nil}, _headers, _statuses), do: false

  defp retry?(%Error{status: status}, headers, statuses) do
    case List.keyfind(headers, "x-should-retry", 0) do
      {_name, "false"} -> false
      {_name, "true"} -> true
      _none -> status in statuses or status >= 500
    end
  end

  defp request_id(headers) do
    case List.keyfind(headers, "x-moss-request-id", 0) do
      {_name, id} when id != "" -> id
      _none -> nil
    end
  end

  # An error reply's Retry-After in ms, when it holds whole seconds.
  defp retry_after(headers) do
    case List.keyfind(headers, "retry-after", 0) do
      {_name, seconds} -> if seconds =~ ~r/\A[0-9]+\z/, do: String.to_integer(seconds) * 1000
      nil -> nil
    end
  end

  # How reading an error reply's body ended, and the first 64 KiB of it.
  defp read_body(state, limits, acc) do
    case await_part(state, limits) do
      {:part, part, state} when byte_size(acc) + byte_size(part) < @error_body ->
        read_body(state, limits, acc <> part)

      {:part, part, state} ->
        {:full, binary_part(acc <> part, 0, @error_body), state}

      {ending, state} ->
        {ending, acc, state}
    end
  end

  defp status_error(status, phrase, body) do
    {type, message, code} =
      case Jason.decode(body) do
        {:ok, %{"error" => %{} = error}} -> {error["type"], error["message"], code(error)}
        {:ok, %{"detail" => detail}} when is_binary(detail) -> {nil, detail, nil}
        {:ok, %{"detail" => detail}} when detail != nil -> {nil, Jason.encode!(detail), nil}
        {:ok, _other} -> {nil, nil, nil}
        {:error, _not_json} -> {nil, excerpt(body), nil}
      end

    %Error{
      status: status,
      type: if(is_binary(type), do: type, else: status_type(status)),
      message: if(is_binary(message), do: message, else: String.trim("HTTP #{status} #{phrase}")),
      code: code
    }
  end

  @doc "The gateway's `error.code` as text: a string as it is, an integer in decimal."
  @spec code(map()) :: String.t() | nil
  def code(%{"code" => code}) when is_binary(code), do: code
  def code(%{"code" => code}) when is_integer(code), do: Integer.to_string(code)
  def code(_error), do: nil

  # A body that is not JSON, such as a proxy's error page, on one line and at most 300 characters.
  defp excerpt(body) do
    text =
      body
      |> String.chunk(:valid)
      |> Enum.map_join(&if(String.valid?(&1), do: &1, else: "�"))
      |> String.split()
      |> Enum.join(" ")

    cond do
      text == "" -> nil
      String.length(text) > 300 -> String.slice(text, 0, 297) <> "..."
      true -> text
    end
  end

  defp status_type(401), do: "authentication_error"
  defp status_type(403), do: "permission_error"
  defp status_type(404), do: "not_found_error"
  defp status_type(429), do: "rate_limit_error"
  defp status_type(status) when status in 400..499, do: "invalid_request_error"
  defp status_type(_status), do: "server_error"

  defp unreachable(reason) do
    detail =
      case reason do
        # Mint's reason holds the header value, which may be a key.
        %Mint.HTTPError{reason: {:invalid_header_value, name, _value}} ->
          "invalid value for header #{name}"

        reason ->
          Exception.message(reason)
      end

    %Error{type: "connection_error", message: "Could not reach the gateway: #{detail}"}
  end

  @doc "The next body part, or the end of the body, or why it broke off."
  @spec await_part(map(), limits()) ::
          {:part, binary(), map()} | {:end, map()} | {{:failed, term()}, map()}
  def await_part(%{received: [response | rest]} = state, limits) do
    state = %{state | received: rest}

    case response do
      {:data, _ref, part} -> {:part, part, state}
      {:done, _ref} -> {:end, state}
      {:failed, _reason} = failed -> {failed, state}
      _trailers -> await_part(state, limits)
    end
  end

  def await_part(%{received: []} = state, limits) do
    {conn, received} = recv(state.conn, limits)
    await_part(%{state | conn: conn, received: received}, limits)
  end

  # Each read waits for any bytes, so the idle limit restarts whenever some arrive.
  # Mint returns what it read before a failure along with it, so no byte that arrived is lost.
  defp recv(conn, {deadline, idle}) do
    case Mint.HTTP1.recv(conn, 0, min(remaining(deadline), idle)) do
      {:ok, conn, responses} -> {conn, responses}
      {:error, conn, reason, responses} -> {conn, responses ++ [{:failed, reason}]}
    end
  end

  @doc "The error of a call that ran out of time, or of a gateway silent past the idle limit."
  @spec timeout_error(limits()) :: Error.t()
  def timeout_error({deadline, idle}) do
    if remaining(deadline) > 0 and idle != :infinity,
      do: %Error{type: "timeout", message: "The gateway sent nothing for #{idle} ms."},
      else: timeout_error()
  end

  defp timeout_error, do: %Error{type: "timeout", message: "The request timed out."}

  defp remaining(:infinity), do: :infinity
  defp remaining(deadline), do: max(deadline - now(), 0)

  defp now, do: System.monotonic_time(:millisecond)
end
