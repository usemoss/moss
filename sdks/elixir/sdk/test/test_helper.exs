# Load .env from the SDK root (sdk/.env) if present (local development credentials).
# Lines starting with # are ignored; blank lines are skipped.
env_path = Path.join(__DIR__, "../.env")

if File.exists?(env_path) do
  env_path
  |> File.read!()
  |> String.split("\n", trim: true)
  |> Enum.reject(&(String.starts_with?(&1, "#") or &1 == ""))
  |> Enum.each(fn line ->
    case String.split(line, "=", parts: 2) do
      [key, value] -> System.put_env(String.trim(key), String.trim(value))
      _ -> :ok
    end
  end)
end

ExUnit.start(exclude: [:integration, :embedding, :session])
