defmodule Moss.ManageClientTest do
  @moduledoc """
  Integration tests for Moss.Client cloud CRUD operations.
  Counterpart to test_moss_client.py in the Python SDK.

  Requires real credentials:
    MOSS_TEST_PROJECT_ID
    MOSS_TEST_PROJECT_KEY

  Run with:
    MOSS_TEST_PROJECT_ID=... MOSS_TEST_PROJECT_KEY=... mix test --include integration
  """

  use ExUnit.Case, async: false

  import Moss.TestHelpers

  setup_all do
    unless has_real_cloud_creds?() do
      raise "Set MOSS_TEST_PROJECT_ID and MOSS_TEST_PROJECT_KEY to run integration tests"
    end

    {:ok, client} = Moss.Client.new(test_project_id(), test_project_key())
    %{client: client}
  end

  # ---------------------------------------------------------------------------
  # Index lifecycle
  # ---------------------------------------------------------------------------

  describe "index lifecycle" do
    @describetag :integration

    test "list_indexes returns a list", %{client: client} do
      {:ok, indexes} = Moss.Client.list_indexes(client)
      assert is_list(indexes)
      if length(indexes) > 0 do
        first = hd(indexes)
        assert Map.has_key?(first, :name) or is_struct(first, Moss.IndexInfo)
      end
    end

    test "create and retrieve index", %{client: client} do
      index_name = generate_unique_index_name("test-create")

      try do
        {:ok, result} = Moss.Client.create_index(client, index_name, test_documents(), "moss-minilm")
        assert result.job_id != ""
        assert result.index_name == index_name
        assert result.doc_count == length(test_documents())

        {:ok, info} = Moss.Client.get_index(client, index_name)
        assert info.name == index_name
        assert info.doc_count == length(test_documents())
      after
        Moss.Client.delete_index(client, index_name)
      end
    end

    test "get non-existent index returns error", %{client: client} do
      assert {:error, _} = Moss.Client.get_index(client, "non-existent-index-#{System.os_time()}")
    end
  end

  # ---------------------------------------------------------------------------
  # Document operations
  # ---------------------------------------------------------------------------

  describe "document operations" do
    @describetag :integration

    setup %{client: client} do
      index_name = generate_unique_index_name("test-docs")
      {:ok, _} = Moss.Client.create_index(client, index_name, test_documents(), "moss-minilm")
      on_exit(fn -> Moss.Client.delete_index(client, index_name) end)
      %{index_name: index_name}
    end

    test "get_docs returns all documents", %{client: client, index_name: index_name} do
      {:ok, docs} = Moss.Client.get_docs(client, index_name)
      assert length(docs) == length(test_documents())
      ids = Enum.map(docs, & &1.id)
      for doc <- test_documents(), do: assert doc.id in ids
    end

    test "get_docs with specific ids", %{client: client, index_name: index_name} do
      target_ids = ["doc-1", "doc-3"]
      {:ok, docs} = Moss.Client.get_docs(client, index_name, doc_ids: target_ids)
      assert length(docs) == 2
      ids = Enum.map(docs, & &1.id)
      for id <- target_ids, do: assert id in ids
    end

    test "add_docs appends new documents", %{client: client, index_name: index_name} do
      {:ok, result} = Moss.Client.add_docs(client, index_name, additional_test_documents())
      assert result.doc_count == length(additional_test_documents())

      {:ok, info} = Moss.Client.get_index(client, index_name)
      assert info.doc_count == length(test_documents()) + length(additional_test_documents())
    end

    test "add_docs with upsert updates existing doc", %{client: client, index_name: index_name} do
      updated = %Moss.DocumentInfo{
        id: "doc-1",
        text: "Updated: Machine learning has many modern applications."
      }
      {:ok, result} = Moss.Client.add_docs(client, index_name, [updated], upsert: true)
      assert result.doc_count == 1

      {:ok, docs} = Moss.Client.get_docs(client, index_name, doc_ids: ["doc-1"])
      assert hd(docs).text == updated.text
    end

    test "delete_docs removes documents", %{client: client, index_name: index_name} do
      {:ok, _} = Moss.Client.add_docs(client, index_name, additional_test_documents())

      {:ok, result} = Moss.Client.delete_docs(client, index_name, ["doc-6", "doc-7"])
      assert result.doc_count == 2

      {:ok, remaining} = Moss.Client.get_docs(client, index_name)
      remaining_ids = Enum.map(remaining, & &1.id)
      refute "doc-6" in remaining_ids
      refute "doc-7" in remaining_ids
    end
  end

  # ---------------------------------------------------------------------------
  # Error handling
  # ---------------------------------------------------------------------------

  describe "error handling" do
    @describetag :integration

    test "operations on non-existent index return errors", %{client: client} do
      ghost = "does-not-exist-#{System.os_time()}"

      assert {:error, _} = Moss.Client.get_docs(client, ghost)
      assert {:error, _} = Moss.Client.add_docs(client, ghost, [%Moss.DocumentInfo{id: "x", text: "x"}])
      assert {:error, _} = Moss.Client.delete_docs(client, ghost, ["x"])
    end
  end

  # ---------------------------------------------------------------------------
  # Credentials validation
  # ---------------------------------------------------------------------------

  describe "validate_credentials" do
    @describetag :session

    test "session/3 succeeds with valid credentials", %{client: client} do
      {:ok, pid} = Moss.Client.session(client, "creds-check-#{System.os_time()}")
      assert is_pid(pid)
      GenServer.stop(pid)
    end

    test "session/3 returns error with invalid credentials" do
      {:ok, bad_client} = Moss.Client.new("bad-id", "bad-key")
      assert {:error, _} = Moss.Client.session(bad_client, "creds-check")
    end
  end
end
