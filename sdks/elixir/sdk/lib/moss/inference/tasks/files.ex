defmodule Moss.Inference.Tasks.Files do
  @moduledoc """
  The screenshots and output files of a browser task.

      {:ok, %{data: files}} = Moss.Inference.Tasks.Files.list(client, task.id)

      for file <- files do
        {:ok, content} = Moss.Inference.Tasks.Files.content(client, task.id, file.path)
        File.write!(Path.basename(file.path), content.data)
      end

  The SDK never writes, opens or renders a file. Both calls take
  the options of every call of `Moss.Inference.Tasks`, and return like them.
  While the task is queued or running they return an error with status 409
  and code `"task_not_finished"`, which the SDK does not retry. The gateway removes
  a task's trace and files 7 days after it finishes, at the task's `files_expire_at`,
  and from then on returns an error with status 410 and code `"files_expired"`.
  """

  alias Moss.Inference.{Error, Tasks}
  alias Moss.Inference.Task.{FileContent, FileList}

  @doc "Lists the files of a task, each with the `path` that `content/4` takes."
  @spec list(Moss.Inference.t(), String.t(), keyword()) ::
          {:ok, FileList.t()} | {:error, Error.t()}
  def list(client, task_id, opts \\ []) do
    with {:ok, reply} <- Tasks.call(client, "GET", task_id, "/files", opts),
         {:ok, data} <- Tasks.decode(reply),
         do: {:ok, Moss.Inference.Task.parse_files(data)}
  end

  @doc """
  Downloads one file, by a `path` that `list/3` gave, such as `"screenshots/step-1.png"`,
  and returns its bytes and `Content-Type`.

  A path with an empty, `.` or `..` part returns an `invalid_request_error` before any request.
  """
  @spec content(Moss.Inference.t(), String.t(), String.t(), keyword()) ::
          {:ok, FileContent.t()} | {:error, Error.t()}
  def content(client, task_id, path, opts \\ []) do
    with {:ok, where} <- file_path(path),
         {:ok, reply} <- Tasks.call(client, "GET", task_id, "/files/" <> where, opts, "*/*"),
         do: {:ok, %FileContent{data: reply.body, content_type: content_type(reply.headers)}}
  end

  # The URL path of a file, each part encoded, since an empty, . or .. part would change the URL.
  defp file_path(path) when is_binary(path) do
    parts = String.split(path, "/")

    if Enum.any?(parts, &(&1 in ["", ".", ".."])),
      do: invalid(),
      else: {:ok, Enum.map_join(parts, "/", &encode/1)}
  end

  defp file_path(_path), do: invalid()

  defp encode(part), do: URI.encode(part, &URI.char_unreserved?/1)

  defp invalid,
    do:
      {:error,
       Error.invalid("The path must be a path that list/3 gave, such as screenshots/step-1.png.")}

  defp content_type(headers) do
    case List.keyfind(headers, "content-type", 0) do
      {_name, type} -> type
      nil -> "application/octet-stream"
    end
  end
end
