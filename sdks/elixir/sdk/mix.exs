defmodule Moss.MixProject do
  use Mix.Project

  def project do
    [
      app: :moss,
      version: "1.0.1",
      elixir: "~> 1.15",
      start_permanent: Mix.env() == :prod,
      elixirc_paths: elixirc_paths(Mix.env()),
      deps: deps(),
      package: package()
    ]
  end

  defp package do
    [
      description: "Elixir SDK for semantic search with on-device AI capabilities",
      licenses: ["BSD-2-Clause"],
      links: %{
        "GitHub" => "https://github.com/usemoss/moss",
        "Docs" => "https://docs.moss.dev"
      }
    ]
  end

  defp elixirc_paths(:test), do: ["lib", "test/support"]
  defp elixirc_paths(_), do: ["lib"]

  def application do
    [extra_applications: [:logger]]
  end

  defp deps do
    [
      {:moss_core, path: "../bindings"},
      {:req, "~> 0.5"},
      {:uniq, "~> 0.6"},
      {:ex_doc, "~> 0.34", only: :dev, runtime: false}
    ]
  end
end
