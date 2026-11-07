defmodule Moss.Inference.Tasks do
  @moduledoc """
  Browser tasks: an agent works toward a goal in a browser on Moss,
  within time and dollar limits, and you poll for the result.

  `run/3` queues a task and returns it once it is `completed`, `failed` or `cancelled`.
  A task runs for minutes, so `create/3` returns it `queued` at once, and `wait/3`
  polls it until it ends. `retrieve/3`, `cancel/3`, `trace/3` and
  `Moss.Inference.Tasks.Files` read or stop it.

      client = Moss.Inference.new("project-id", "project-key")

      {:ok, task} =
        Moss.Inference.Tasks.run(
          client,
          %{
            goal: "Find the price of the cheapest nonstop flight from SFO to JFK next Friday.",
            environment: %{type: "browser", start_url: "https://www.google.com/travel/flights"},
            limits: %{max_runtime_seconds: 360, max_cost_usd: 0.25}
          },
          timeout: 600_000
        )

  Each call returns `{:ok, value}`, or `{:error, %Moss.Inference.Error{}}` for a refused
  argument, an error reply or a failed connection. Task calls use the client's credentials,
  gateway URL, timeouts and retries, and never send its `:api_key`.
  A `client` that is not a `Moss.Inference`, or an unknown option, raises `ArgumentError`.

  Options of every call:
    - `:timeout` - milliseconds for the whole call, else the client's
    - `:idle_timeout` - milliseconds Moss may stay silent, else the client's
    - `:max_retries` - how many times a failed call is sent again, else the client's.
      A call goes again like `Moss.Inference.Responses.create/3`, but never after a 409.
  """

  alias Moss.Inference
  alias Moss.Inference.{Error, Request, Task}

  @options [:timeout, :idle_timeout, :max_retries]
  # The 4xx statuses a task call goes again after. A 409 says the task has not finished.
  @retried [408, 429]
  @poll_interval 2_000
  # The longest pause `receive ... after` takes, in ms.
  @longest_pause 4_294_967_295
  @waiting ["queued", "running"]

  @typedoc """
  The body of a task, with atom or string keys, sent as it is:

    - `goal` - what the agent should do, in plain words
    - `environment` - where it runs, `%{type: "browser"}` with an optional `start_url`,
      the page it opens first, and `live_view: true`, which asks for a `live_url`
    - `output_schema` - a JSON Schema for `result.output`, which the gateway checks the answer against
    - `limits` - `max_runtime_seconds` and `max_cost_usd`
    - `model` - a model name of the Moss catalog
    - `effort` - `"low"`, `"medium"` or `"high"`
    - `metadata` - your own data, sent back with the task

  The gateway picks what you leave out, such as the model and the limits,
  and refuses a field it does not know with `invalid_request_error`.
  """
  @type params :: %{optional(atom() | String.t()) => term()}

  @doc """
  Queues a task and returns it, `queued`.

  Only the fields in `params` are sent. Each create sends an `Idempotency-Key`,
  a new one per call or the `:idempotency_key` option, and the same one on every retry.
  The gateway answers a repeated key with the same body, within 24 hours, with the task it created,
  so a retried create never starts a second task. To retry a create yourself, pass your own key.
  `params` that are not a map raise `ArgumentError`, and `params` JSON cannot carry,
  or that give a key twice, return an `invalid_request_error`.

  Options: `:idempotency_key`, a non-empty string of printable ASCII, and the options of every call.
  """
  @spec create(Inference.t(), params(), keyword()) :: {:ok, Task.t()} | {:error, Error.t()}
  def create(client, params, opts \\ []) do
    check_arguments!(client, params)
    Inference.check_options!(opts, [:idempotency_key | @options])

    with {:ok, json} <- Inference.encode(params),
         {:ok, reply} <- fetch(client, "POST", "/tasks", opts, json, "application/json"),
         do: parse_task(reply)
  end

  @doc "Fetches a task by its id."
  @spec retrieve(Inference.t(), String.t(), keyword()) :: {:ok, Task.t()} | {:error, Error.t()}
  def retrieve(client, task_id, opts \\ []), do: call_task(client, "GET", task_id, "", opts)

  @doc """
  Stops a task. A queued task comes back `cancelled`.
  A running one comes back with `cancel_requested` and ends `cancelled` soon after.
  """
  @spec cancel(Inference.t(), String.t(), keyword()) :: {:ok, Task.t()} | {:error, Error.t()}
  def cancel(client, task_id, opts \\ []), do: call_task(client, "POST", task_id, "/cancel", opts)

  @doc """
  Polls a task every `:poll_interval` until it is neither `queued` nor `running`, and returns it.

  A `failed` or `cancelled` task returns `{:ok, task}` too, so read its `status` and `error`.
  Each poll is a `retrieve/3` that ends by the wait's `:timeout`, or sooner with the client's.
  Every error of a wait, a poll's or its own timeout, has the task's id in `task_id`.
  Stop a wait by stopping its process, for example with `Task.shutdown/2`.
  The task goes on either way.

  Options:
    - `:timeout` - milliseconds the whole wait may take (default `:infinity`).
      Past it, the wait returns an error with type `"timeout"`, even while a poll waits
      for its reply, and the task goes on: wait again or cancel it.
    - `:poll_interval` - milliseconds between polls (default `2_000`)
    - `:idle_timeout` and `:max_retries` - for each poll, else the client's

  A `:timeout` or `:poll_interval` that is not a positive integer
  returns an `invalid_request_error` before any request.
  """
  @spec wait(Inference.t(), String.t(), keyword()) :: {:ok, Task.t()} | {:error, Error.t()}
  def wait(client, task_id, opts \\ []) do
    Inference.check_client!(client)
    Inference.check_options!(opts, [:poll_interval | @options])
    {wait, opts} = Keyword.split(opts, [:timeout, :poll_interval])

    with {:ok, wait} <- waiting(wait),
         {:ok, _path} <- task_path(task_id),
         do: poll(client, task_id, opts, wait)
  end

  @doc """
  Queues a task and waits for it, as `create/3` and then `wait/3` do.

  `:timeout` and `:poll_interval` are the wait's, and checked before the task is queued.
  `:idle_timeout` and `:max_retries` apply to every request, and `:idempotency_key` to the create.
  Once the task is queued, every error has its id in `task_id`, so you can wait on or cancel it.
  """
  @spec run(Inference.t(), params(), keyword()) :: {:ok, Task.t()} | {:error, Error.t()}
  def run(client, params, opts \\ []) do
    check_arguments!(client, params)
    Inference.check_options!(opts, [:poll_interval, :idempotency_key | @options])
    {wait, opts} = Keyword.split(opts, [:timeout, :poll_interval])

    with {:ok, wait} <- waiting(wait),
         {:ok, task} <- create(client, params, opts),
         do: poll(client, task.id, Keyword.delete(opts, :idempotency_key), wait)
  end

  @doc """
  The agent's step-by-step record, the JSON the gateway sent, decoded.

  It returns a `not_found_error` until the task's `trace_available` is `true`.
  The gateway removes a task's trace and files 7 days after it finishes, at `files_expire_at`,
  and from then on returns an error with status 410 and code `"files_expired"`.
  """
  @spec trace(Inference.t(), String.t(), keyword()) :: {:ok, term()} | {:error, Error.t()}
  def trace(client, task_id, opts \\ []) do
    with {:ok, reply} <- call(client, "GET", task_id, "/trace", opts), do: decode(reply, false)
  end

  # A Tasks API call on the task `task_id`, at `path` under it, after its id is checked.
  @doc false
  @spec call(Inference.t(), String.t(), term(), String.t(), keyword(), String.t()) ::
          {:ok, map()} | {:error, Error.t()}
  def call(client, method, task_id, path, opts, accept \\ "application/json") do
    Inference.check_client!(client)
    Inference.check_options!(opts, @options)

    with {:ok, where} <- task_path(task_id),
         do: fetch(client, method, where <> path, opts, nil, accept)
  end

  # The JSON of a reply, which must be an object when `object?` is true.
  @doc false
  @spec decode(map(), boolean()) :: {:ok, term()} | {:error, Error.t()}
  def decode(reply, object? \\ true) do
    case Jason.decode(reply.body) do
      {:ok, value} when is_map(value) or not object? ->
        {:ok, value}

      _other ->
        what = if object?, do: "a JSON object", else: "JSON"
        message = "The gateway sent a reply that is not #{what}."
        {:error, %Error{type: "server_error", message: message, request_id: reply.request_id}}
    end
  end

  # Checks the client and params in the body, since a clause that does not match
  # prints the call's arguments, and with them any key in `opts`.
  defp check_arguments!(client, params) do
    Inference.check_client!(client)
    unless is_map(params), do: raise(ArgumentError, "the params must be a map")
  end

  defp call_task(client, method, task_id, path, opts) do
    with {:ok, reply} <- call(client, method, task_id, path, opts), do: parse_task(reply)
  end

  defp parse_task(reply), do: with({:ok, data} <- decode(reply), do: {:ok, Task.parse(data)})

  # Sends a call to `path` under the base URL.
  # Only a create has a `body`, which goes with one Idempotency-Key on every attempt.
  defp fetch(client, method, path, opts, body, accept) do
    with {:ok, settings} <- Inference.settings(client, opts),
         {:ok, headers} <- headers(client, body, opts[:idempotency_key], accept),
         do: Request.fetch(method, url(client, path), headers, body, settings, @retried)
  end

  # The client's credentials without its provider key, which task calls never send.
  defp headers(client, body, key, accept) do
    credentials = List.keydelete(client.headers, "x-moss-provider-key", 0)
    headers = credentials ++ [{"accept", accept}]

    cond do
      body == nil ->
        {:ok, headers}

      key == nil ->
        {:ok, headers ++ create_headers(Uniq.UUID.uuid4())}

      is_binary(key) and key != "" and Inference.header_safe?(key) ->
        {:ok, headers ++ create_headers(key)}

      true ->
        {:error,
         Error.invalid(
           ":idempotency_key must be a non-empty string of printable ASCII " <>
             "without surrounding spaces."
         )}
    end
  end

  defp create_headers(key), do: [{"content-type", "application/json"}, {"idempotency-key", key}]

  # The client's URL holds the base URL with /responses after it.
  defp url(client, path) do
    base = String.replace_suffix(client.endpoint.path, "/responses", "")
    %{client.endpoint | path: base <> path}
  end

  # The URL path of a task, after its id is checked and encoded as one segment.
  defp task_path(task_id) when is_binary(task_id) and task_id not in ["", ".", ".."],
    do: {:ok, "/tasks/" <> URI.encode(task_id, &URI.char_unreserved?/1)}

  defp task_path(_task_id),
    do: {:error, Error.invalid("The task id must be the id of a task, such as task_...")}

  # The limit and the interval of a wait, checked before any request.
  defp waiting(opts) do
    limit = Keyword.get(opts, :timeout, :infinity)
    interval = Keyword.get(opts, :poll_interval, @poll_interval)

    with {:ok, limit} <- Inference.check_timeout(limit, :timeout),
         :ok <- check_interval(interval),
         do: {:ok, %{limit: limit, interval: min(interval, @longest_pause)}}
  end

  defp check_interval(ms) when is_integer(ms) and ms > 0, do: :ok

  defp check_interval(_ms),
    do: {:error, Error.invalid(":poll_interval must be a positive integer of milliseconds.")}

  # Polls from now until the task ends or the wait's limit passes.
  # An error names the task, so the caller can still wait on, cancel or read it.
  defp poll(client, task_id, opts, %{limit: limit} = wait) do
    deadline = if limit == :infinity, do: :infinity, else: now() + limit

    with {:error, error} <- poll(client, task_id, opts, wait, {deadline, "unfinished"}),
         do: {:error, %{error | task_id: task_id}}
  end

  # Each poll ends by the deadline, or sooner with the client's own timeout.
  # `status` is the last one a poll read, for the error past the deadline.
  defp poll(client, task_id, opts, wait, {deadline, status}) do
    timeout = max(min(client.timeout, remaining(deadline)), 1)

    case retrieve(client, task_id, [{:timeout, timeout} | opts]) do
      {:ok, %Task{status: status}} when status in @waiting ->
        pause(client, task_id, opts, wait, {deadline, status})

      {:error, %Error{type: "timeout"}} = error ->
        if remaining(deadline) == 0, do: late(task_id, status, wait.limit), else: error

      done ->
        done
    end
  end

  defp pause(client, task_id, opts, wait, {deadline, status} = last) do
    case remaining(deadline) do
      0 ->
        late(task_id, status, wait.limit)

      left ->
        Process.sleep(min(wait.interval, left))
        poll(client, task_id, opts, wait, last)
    end
  end

  defp late(task_id, status, limit) do
    message =
      "Task #{task_id} is still #{status} after #{limit} ms. It goes on: wait again or cancel it."

    {:error, %Error{type: "timeout", message: message}}
  end

  defp remaining(:infinity), do: :infinity
  defp remaining(deadline), do: max(deadline - now(), 0)

  defp now, do: System.monotonic_time(:millisecond)
end
