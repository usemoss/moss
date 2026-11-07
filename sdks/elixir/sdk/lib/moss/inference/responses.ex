defmodule Moss.Inference.Responses do
  @moduledoc """
  OpenAI's Responses call, answered by Moss inference.

  Moss searches the named indexes, adds what it finds to the prompt
  and streams the model's response. `params` is the OpenAI request body as a map,
  so code written for OpenAI's API keeps working once it adds `:indexes`.

      client = Moss.Inference.new("project-id", "project-key")

      {:ok, response} =
        Moss.Inference.Responses.create(client, %{input: "Do you ship to Canada?"}, indexes: ["faq"])

      response["output_text"]
  """

  alias Moss.Inference
  alias Moss.Inference.{Error, ResponseStream}

  @options [:indexes, :retrieve, :cache, :api_key, :timeout, :idle_timeout, :max_retries]

  # Keys of params that belong in opts, each with the option it names.
  @misplaced Enum.map(@options, &{&1, &1}) ++ [apiKey: :api_key]

  @typedoc """
  The OpenAI request body, with atom or string keys, sent as it is. Among them:

    - `input` - a string, or the conversation so far as a list of items: input messages
      such as `%{role: "user", content: "Hi"}`, the `"output"` items of earlier responses
      as they came, and a `%{type: "function_call_output", call_id: id, output: text}` per tool call
    - `instructions` - a system message for this response
    - `max_output_tokens` - the most tokens the response may hold
    - `tools` - what the model may call: flat function tools such as
      `%{type: "function", name: "lookup", parameters: schema}`,
      `Moss.Inference.McpServer` structs, or any other map
    - `tool_choice` - `"none"`, `"auto"`, `"required"`, or a map such as
      `%{type: "function", name: "lookup"}`
    - `parallel_tool_calls` - `false` limits the model to one tool call per response

  Other keys, such as `temperature`, `text` or `reasoning`, reach the model unchanged.
  """
  @type params :: %{optional(atom() | String.t()) => term()}

  @doc """
  Sends a Responses request with the credentials of `client`.

  `params` is the OpenAI body, with atom or string keys. Every key goes to
  Moss unchanged, except `stream`: with `stream: true` the call returns
  `{:ok, %Moss.Inference.ResponseStream{}}` once the response starts, and
  without it `{:ok, response}`, the `"response"` map of the stream's last event,
  with OpenAI's field names as string keys. Its `"output"` items keep every field the model sent,
  so they go back in `input` as they are. `"output_text"` joins the text of its messages,
  and `"request_id"` is the response's `X-Moss-Request-Id` header, else `nil`.
  A response cut by `max_output_tokens` has `"status"` `"incomplete"` and `"incomplete_details"`.
  Moss stores nothing, so send the whole conversation each time.
  Without `model`, the call sends `"model" => "moss"`, Moss's own model.
  `params` that hold an option below, or `apiKey`, as an atom or string key, return
  an `invalid_request_error` that names the option, so a provider key never goes in the body.
  A key given twice in one map, such as `:content` and `"content"`, returns one too.
  A failure returns `{:error, %Moss.Inference.Error{}}`, except one after a
  stream starts, which raises `Moss.Inference.Error` while the stream is read.
  A call whose connection fails, or that gets a 408, 409, 429 or 5xx reply, is sent again
  up to `:max_retries` times, after the reply's `Retry-After` seconds when they are 60 or fewer,
  else after 0.5 s doubled each time up to 8 s, less up to 25%. The waits count against `:timeout`,
  and a wait that would pass it returns the error instead. A reply's `x-should-retry` header of
  `false` forbids a retry and `true` forces one. A stream that started is never sent again.
  A `client` that is not a `Moss.Inference`, `params` that are not a map
  or an unknown option raises `ArgumentError`, which holds no key.

  Options:
    - `:indexes` - names of the Moss indexes to search, `[]` for none,
      else every index in the project
    - `:retrieve` - `false` skips the search and adds no facts (default `true`)
    - `:cache` - `false` always asks the model, never Moss's reply cache (default `true`)
    - `:api_key` - your own OpenAI, Anthropic or Google key for this call, else the client's.
      A vendor model such as `gpt-4o-mini` needs one, and `moss` ignores it.
    - `:timeout` - milliseconds for the whole call, stream included, else the client's
    - `:idle_timeout` - milliseconds Moss may stay silent, else the client's
    - `:max_retries` - how many times a failed call is sent again, else the client's
  """
  @spec create(Inference.t(), params(), keyword()) ::
          {:ok, ResponseStream.t() | map()} | {:error, Error.t()}
  def create(client, params, opts \\ []) do
    check_arguments!(client, params)
    Inference.check_options!(opts, @options)
    stream? = Map.get(params, :stream, Map.get(params, "stream")) == true
    body = params |> Map.drop([:stream, "stream"]) |> Map.put("stream", true) |> put_model()

    with :ok <- misplaced(params),
         {:ok, headers} <- headers(client, opts),
         {:ok, settings} <- Inference.settings(client, opts),
         {:ok, json} <- Inference.encode(body),
         {:ok, stream} <- ResponseStream.open(client.endpoint, headers, json, settings) do
      if stream?, do: {:ok, stream}, else: collect(stream)
    end
  end

  # Checks the client and params of create/3 in its body, since a clause
  # that does not match prints the call's arguments, and with them any key in `opts`.
  defp check_arguments!(client, params) do
    Inference.check_client!(client)
    unless is_map(params), do: raise(ArgumentError, "the params must be a map")
  end

  defp misplaced(params) do
    Enum.find_value(@misplaced, :ok, fn {key, option} ->
      if Map.has_key?(params, key) or Map.has_key?(params, Atom.to_string(key)),
        do: invalid("Pass #{inspect(option)} in the options of create, not in params.")
    end)
  end

  # Moss's own model, for params that name none.
  defp put_model(body) do
    if Map.has_key?(body, :model) or Map.has_key?(body, "model"),
      do: body,
      else: Map.put(body, "model", "moss")
  end

  # A call's own provider key replaces the client's.
  defp headers(client, opts) do
    with {:ok, indexes} <- indexes(opts[:indexes]),
         {:ok, provider} <- Inference.provider_key(opts[:api_key]) do
      credentials =
        if provider == [],
          do: client.headers,
          else: List.keydelete(client.headers, "x-moss-provider-key", 0) ++ provider

      retrieve? = opts[:retrieve] != false and opts[:indexes] != []
      retrieve = if retrieve?, do: [], else: [{"x-moss-retrieve", "off"}]
      cache = if opts[:cache] == false, do: [{"x-moss-cache", "off"}], else: []
      {:ok, credentials ++ [{"accept", "text/event-stream"} | indexes] ++ retrieve ++ cache}
    end
  end

  defp indexes(nil), do: {:ok, []}
  defp indexes([]), do: {:ok, []}

  defp indexes(names) when is_list(names) do
    if Enum.all?(names, &index_name?/1),
      do: {:ok, [{"x-moss-indexes", Enum.join(names, ",")}]},
      else:
        invalid(
          "Index names must be non-empty printable ASCII, without commas or surrounding spaces."
        )
  end

  defp indexes(_names), do: invalid(":indexes must be a list of index names.")

  defp index_name?(name) do
    is_binary(name) and name != "" and not String.contains?(name, ",") and
      Inference.header_safe?(name)
  end

  defp invalid(message), do: {:error, Error.invalid(message)}

  # The stream ends after its last event, so the last one it gives holds the whole response.
  defp collect(stream) do
    response =
      case Enum.reduce(stream, nil, fn event, _last -> event end) do
        %{"response" => %{} = response} -> response
        _other -> %{}
      end

    {:ok,
     Map.merge(response, %{"output_text" => text(response), "request_id" => stream.request_id})}
  rescue
    error in Error -> {:error, error}
  end

  # The text of every output_text part of every message, joined.
  defp text(%{"output" => output}) when is_list(output) do
    for %{"type" => "message", "content" => content} when is_list(content) <- output,
        %{"type" => "output_text", "text" => text} when is_binary(text) <- content,
        into: "",
        do: text
  end

  defp text(_response), do: ""
end
