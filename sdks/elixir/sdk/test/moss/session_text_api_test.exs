defmodule Moss.SessionApiTest do
  @moduledoc """
  Tests for the unified Session add_docs/3 and query/3 APIs.

  Requires cloud credentials (MOSS_TEST_PROJECT_ID / MOSS_TEST_PROJECT_KEY or .env)
  because session construction now validates credentials at the Rust core level.

  The custom-model cases only make the credential check at creation time; all
  subsequent operations are fully local. Built-in-model cases are tagged as
  `:embedding` because the first run may download the local embedding model.
  """

  use ExUnit.Case, async: false
  @moduletag :session

  import Moss.TestHelpers

  defp start_session(model_id) do
    {:ok, pid} =
      Moss.Session.start_link(
        name: generate_unique_session_name("api"),
        model_id: model_id,
        project_id: test_project_id(),
        project_key: test_project_key()
      )

    on_exit(fn ->
      if Process.alive?(pid) do
        GenServer.stop(pid)
      end
    end)

    pid
  end

  defp text_docs do
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

  describe "custom model error guidance" do
    test "add_docs returns error when docs are missing .embedding" do
      pid = start_session("custom")

      assert {:error, reason} = Moss.Session.add_docs(pid, text_docs())
      assert reason =~ "missing .embedding"
      assert reason =~ "billing"
      assert reason =~ "garden"
    end

    test "query returns error when embedding: opt is not provided" do
      pid = start_session("custom")

      docs = [
        %Moss.DocumentInfo{id: "custom-doc", text: "Custom embedding document", embedding: [1.0, 0.0]}
      ]

      {:ok, _} = Moss.Session.add_docs(pid, docs)

      assert {:error, reason} = Moss.Session.query(pid, "billing question")
      assert reason =~ "embedding"
    end
  end

  describe "built-in model workflows" do
    @tag :embedding
    test "add_docs and query work without explicit embeddings" do
      pid = start_session("moss-minilm")

      assert {:ok, {2, 0}} = Moss.Session.add_docs(pid, text_docs())
      assert Moss.Session.doc_count(pid) == 2

      assert {:ok, result} =
               Moss.Session.query(pid, "refund for a billing issue", top_k: 1)

      assert length(result.docs) == 1
      assert hd(result.docs).id == "billing"
    end
  end
end
