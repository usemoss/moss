defmodule Moss.Inference.Task do
  @moduledoc """
  A browser task, as the calls of `Moss.Inference.Tasks` return it.

  An agent works toward `goal` in a browser on Moss, within the task's `limits`.
  `status` is `"queued"`, `"running"`, `"completed"`, `"failed"` or `"cancelled"`,
  and may take other values later. A task ends `completed`, `failed` or `cancelled`.
  `raw` is the task as the gateway sent it, with string keys, for the fields these types leave out.
  `inspect/2` leaves `raw` out.
  """

  alias Moss.Inference.Task.{FileList, Result, Usage, Verification}

  @derive {Inspect, except: [:raw]}
  defstruct id: "",
            object: "task",
            status: "",
            goal: "",
            environment: %{},
            output_schema: nil,
            limits: %{},
            model: nil,
            effort: nil,
            metadata: nil,
            result: nil,
            verification: nil,
            usage: nil,
            error: nil,
            trace_available: false,
            live_url: nil,
            cancel_requested: false,
            created_at: nil,
            started_at: nil,
            finished_at: nil,
            files_expire_at: nil,
            raw: %{}

  @typedoc """
  A task whose `result.output` is an `output`, the JSON that `output_schema` asks for.

  The SDK does not check `output`: `verification` says whether it matched `output_schema`.

    - `id` - such as `"task_..."`
    - `environment` - where it runs, such as `%{"type" => "browser", "start_url" => url}`
    - `limits` - `"max_runtime_seconds"` and `"max_cost_usd"`, the gateway's own where the
      request left one out
    - `result` - the answer once the task ends. A failed or cancelled task can have one too.
    - `error` - why it failed, else `nil`
    - `trace_available` - whether `Moss.Inference.Tasks.trace/3` has the agent's record
    - `live_url` - a link to watch the browser while it runs, with `live_view`
    - `cancel_requested` - whether a cancel waits for the running task to stop
    - `created_at`, `started_at` and `finished_at` - ISO 8601 text, or `nil` before it happens
    - `files_expire_at` - ISO 8601 text, when the gateway removes the trace and files,
      7 days after the task ends, or `nil` before it ends
  """
  @type t(output) :: %__MODULE__{
          id: String.t(),
          object: String.t(),
          status: String.t(),
          goal: String.t(),
          environment: map(),
          output_schema: map() | nil,
          limits: map(),
          model: String.t() | nil,
          effort: String.t() | nil,
          metadata: map() | nil,
          result: Result.t(output) | nil,
          verification: Verification.t() | nil,
          usage: Usage.t() | nil,
          error: Moss.Inference.Task.Error.t() | nil,
          trace_available: boolean(),
          live_url: String.t() | nil,
          cancel_requested: boolean(),
          created_at: String.t() | nil,
          started_at: String.t() | nil,
          finished_at: String.t() | nil,
          files_expire_at: String.t() | nil,
          raw: map()
        }

  @typedoc "A task whose `result.output` is any decoded JSON."
  @type t :: t(term())

  # A task from its decoded JSON object.
  @doc false
  @spec parse(map()) :: t()
  def parse(data) do
    build(__MODULE__, data,
      result: build(Result, data["result"]),
      verification: build(Verification, data["verification"]),
      usage: build(Usage, data["usage"], raw: data["usage"]),
      error: build(Moss.Inference.Task.Error, data["error"]),
      raw: data
    )
  end

  # A file list from its decoded JSON object, without the entries that are not objects.
  @doc false
  @spec parse_files(map()) :: FileList.t()
  def parse_files(data) do
    files = if is_list(data["data"]), do: data["data"], else: []

    build(FileList, data,
      data: for(%{} = file <- files, do: build(Moss.Inference.Task.File, file))
    )
  end

  # A `module` struct from `given` and the fields `data` has, or nil when `data` is not a map.
  # A null is left out, so its field keeps its default, as when the key is missing.
  defp build(module, data, given \\ [])

  defp build(module, %{} = data, given) do
    names = Map.keys(module.__struct__()) -- [:__struct__ | Keyword.keys(given)]

    known =
      Enum.flat_map(names, fn name ->
        case Map.get(data, Atom.to_string(name)) do
          nil -> []
          value -> [{name, value}]
        end
      end)

    struct(module, known ++ given)
  end

  defp build(_module, _data, _given), do: nil
end

defmodule Moss.Inference.Task.Result do
  @moduledoc "The agent's answer. `output` is the JSON that `output_schema` asked for."

  defstruct output_text: "", output: nil

  @type t(output) :: %__MODULE__{output_text: String.t(), output: output | nil}
  @type t :: t(term())
end

defmodule Moss.Inference.Task.Verification do
  @moduledoc """
  How the answer was checked: `"agent_reported"` or `"output_schema"`.

  `passed` is `nil` when only the agent checked it,
  and `false` with `problems` when the answer does not match `output_schema`.
  """

  defstruct method: "", passed: nil, problems: nil

  @type t :: %__MODULE__{
          method: String.t(),
          passed: boolean() | nil,
          problems: [String.t()] | nil
        }
end

defmodule Moss.Inference.Task.Usage do
  @moduledoc """
  What a task used. `raw` holds every field the gateway sent, such as `"browser_minutes"`.

  `inspect/2` leaves `raw` out.
  """

  @derive {Inspect, except: [:raw]}
  defstruct model_calls: 0,
            input_tokens: 0,
            cached_input_tokens: 0,
            output_tokens: 0,
            cost_usd: 0,
            raw: %{}

  @type t :: %__MODULE__{
          model_calls: non_neg_integer(),
          input_tokens: non_neg_integer(),
          cached_input_tokens: non_neg_integer(),
          output_tokens: non_neg_integer(),
          cost_usd: number(),
          raw: map()
        }
end

defmodule Moss.Inference.Task.Error do
  @moduledoc """
  Why a task failed, with a code such as `"time_limit"` or `"budget_exceeded"`.

  It is part of a task, not an exception. A call that fails returns `Moss.Inference.Error`.
  """

  defstruct code: "", message: ""

  @type t :: %__MODULE__{code: String.t(), message: String.t()}
end

defmodule Moss.Inference.Task.File do
  @moduledoc "A file of a task, such as a screenshot, with its `path` and its size in `bytes`."

  defstruct path: "", bytes: 0

  @type t :: %__MODULE__{path: String.t(), bytes: non_neg_integer()}
end

defmodule Moss.Inference.Task.FileList do
  @moduledoc "The files of a task."

  defstruct object: "list", data: []

  @type t :: %__MODULE__{object: String.t(), data: [Moss.Inference.Task.File.t()]}
end

defmodule Moss.Inference.Task.FileContent do
  @moduledoc """
  The bytes of a task's file, and the `Content-Type` the gateway sent with them.

  `content_type` is `"application/octet-stream"` when it sent none. The SDK never opens a file.
  """

  defstruct data: "", content_type: "application/octet-stream"

  @type t :: %__MODULE__{data: binary(), content_type: String.t()}
end
