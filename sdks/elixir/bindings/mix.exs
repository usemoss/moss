defmodule MossCore.MixProject do
  use Mix.Project

  def project do
    [
      app: :moss_core,
      version: "0.9.0",
      elixir: "~> 1.15",
      start_permanent: Mix.env() == :prod,
      package: package(),
      deps: deps()
    ]
  end

  defp package do
    [
      description: "Precompiled Rust NIF powering the Moss Elixir SDK",
      licenses: ["BSD-2-Clause"],
      links: %{
        "GitHub" => "https://github.com/usemoss/moss",
        "Docs" => "https://docs.moss.dev"
      },
      files: [
        "lib",
        "checksum-Elixir.MossCore.Nif.exs",
        "mix.exs"
      ]
    ]
  end

  def application do
    [extra_applications: [:logger]]
  end

  defp deps do
    [
      {:rustler, "~> 0.37", runtime: false},
      {:rustler_precompiled, "~> 0.8"},
      {:ex_doc, "~> 0.34", only: :dev, runtime: false}
    ]
  end
end
