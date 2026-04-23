defmodule Moss.IndexManagerApiTest do
  @moduledoc """
  Integration tests for the unified Client query/4 API (local loaded indexes).

  These tests require real cloud credentials because local querying only works
  after loading a real cloud index.
  """

  use ExUnit.Case, async: false

  import Moss.TestHelpers

  @moduletag :integration

  setup_all do
    unless has_real_cloud_creds?() do
      raise "Set MOSS_TEST_PROJECT_ID and MOSS_TEST_PROJECT_KEY to run integration tests"
    end

    {:ok, client} = Moss.Client.new(test_project_id(), test_project_key())

    %{client: client}
  end

  defp built_in_docs do
    [
      %Moss.DocumentInfo{
        id: "billing",
        text: "Customer requested a billing refund and invoice review."
      },
      %Moss.DocumentInfo{
        id: "garden",
        text: "How to prune tomato plants in a home garden."
      }
    ]
  end

  defp custom_docs do
    [
      %Moss.DocumentInfo{
        id: "billing",
        text: "Customer requested a billing refund and invoice review.",
        embedding: [1.0, 0.0, 0.0, 0.0]
      },
      %Moss.DocumentInfo{
        id: "garden",
        text: "How to prune tomato plants in a home garden.",
        embedding: [0.0, 1.0, 0.0, 0.0]
      }
    ]
  end

  test "query returns local results for built-in loaded indexes", %{client: client} do
    index_name = generate_unique_index_name("manager-text")

    try do
      assert {:ok, _} = Moss.Client.create_index(client, index_name, built_in_docs(), "moss-minilm")
      assert {:ok, _info} = Moss.Client.load_index(client, index_name)

      assert {:ok, result} =
               Moss.Client.query(client, index_name, "refund for a billing issue", top_k: 1)

      assert length(result.docs) == 1
      assert hd(result.docs).id == "billing"
    after
      Moss.Client.delete_index(client, index_name)
    end
  end

  test "query without embedding: returns error for custom loaded indexes", %{client: client} do
    index_name = generate_unique_index_name("manager-custom")

    try do
      assert {:ok, _} = Moss.Client.create_index(client, index_name, custom_docs(), "custom")
      assert {:ok, _info} = Moss.Client.load_index(client, index_name)

      assert {:error, reason} =
               Moss.Client.query(client, index_name, "billing question", top_k: 1)

      assert reason =~ "requires explicit query embeddings"
      assert reason =~ "Pass embedding:"
    after
      Moss.Client.delete_index(client, index_name)
    end
  end
end
