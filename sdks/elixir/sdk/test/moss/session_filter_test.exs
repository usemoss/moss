defmodule Moss.SessionFilterTest do
  @moduledoc """
  Filter parity tests for Moss.Session.query/3.
  Counterpart to test_session_filter.py in the Python SDK.

  Uses model_id: "custom" with pre-computed embeddings — no ONNX runtime needed.
  Requires cloud credentials (MOSS_TEST_PROJECT_ID / MOSS_TEST_PROJECT_KEY or .env)
  because session construction validates credentials at the Rust core level.
  All filter and query logic runs fully locally after construction.
  """

  use ExUnit.Case, async: false
  @moduletag :session

  import Moss.TestHelpers

  # ---------------------------------------------------------------------------
  # Fixtures
  # ---------------------------------------------------------------------------

  defp start_session_with(name, doc_emb_pairs) do
    {:ok, pid} =
      Moss.Session.start_link(
        name: name,
        model_id: "custom",
        project_id: test_project_id(),
        project_key: test_project_key()
      )

    docs = Enum.map(doc_emb_pairs, fn {doc, emb} -> %{doc | embedding: emb} end)
    {:ok, _} = Moss.Session.add_docs(pid, docs)
    pid
  end

  defp query_ids(pid, filter) do
    {:ok, result} = Moss.Session.query(pid, "test", embedding: query_emb(), top_k: 10, filter: filter)
    Enum.map(result.docs, & &1.id) |> Enum.sort()
  end

  # ---------------------------------------------------------------------------
  # Filter conditions
  # ---------------------------------------------------------------------------

  describe "filter conditions" do
    setup do
      pid = start_session_with("test-filter-cond-#{System.unique_integer([:positive])}", filter_docs())
      %{pid: pid}
    end

    test "$eq", %{pid: pid} do
      assert query_ids(pid, %{"field" => "city", "condition" => %{"$eq" => "NYC"}}) == ["1", "3"]
    end

    test "$ne", %{pid: pid} do
      assert query_ids(pid, %{"field" => "city", "condition" => %{"$ne" => "NYC"}}) == ["2", "4", "5"]
    end

    test "$gt string", %{pid: pid} do
      assert query_ids(pid, %{"field" => "price", "condition" => %{"$gt" => "10"}}) == ["1", "2", "4"]
    end

    test "$gt integer coercion", %{pid: pid} do
      assert query_ids(pid, %{"field" => "price", "condition" => %{"$gt" => 10}}) == ["1", "2", "4"]
    end

    test "$gt float coercion", %{pid: pid} do
      assert query_ids(pid, %{"field" => "price", "condition" => %{"$gt" => 10.0}}) == ["1", "2", "4"]
    end

    test "$lt", %{pid: pid} do
      assert query_ids(pid, %{"field" => "price", "condition" => %{"$lt" => "15"}}) == ["1", "3", "5"]
    end

    test "$gte", %{pid: pid} do
      assert query_ids(pid, %{"field" => "price", "condition" => %{"$gte" => "20"}}) == ["2", "4"]
    end

    test "$lte", %{pid: pid} do
      assert query_ids(pid, %{"field" => "price", "condition" => %{"$lte" => "8"}}) == ["3", "5"]
    end

    test "$in", %{pid: pid} do
      assert query_ids(pid, %{"field" => "city", "condition" => %{"$in" => ["NYC", "Paris"]}}) == ["1", "3", "4"]
    end

    test "$in integer coercion", %{pid: pid} do
      assert query_ids(pid, %{"field" => "price", "condition" => %{"$in" => [12, 20]}}) == ["1", "4"]
    end

    test "$nin", %{pid: pid} do
      assert query_ids(pid, %{"field" => "city", "condition" => %{"$nin" => ["NYC"]}}) == ["2", "4", "5"]
    end
  end

  # ---------------------------------------------------------------------------
  # Composite filters
  # ---------------------------------------------------------------------------

  describe "composite filters" do
    setup do
      pid = start_session_with("test-filter-comp-#{System.unique_integer([:positive])}", filter_docs())
      %{pid: pid}
    end

    test "$and", %{pid: pid} do
      filt = %{
        "$and" => [
          %{"field" => "city",     "condition" => %{"$eq" => "NYC"}},
          %{"field" => "category", "condition" => %{"$eq" => "food"}}
        ]
      }
      assert query_ids(pid, filt) == ["1"]
    end

    test "$or", %{pid: pid} do
      filt = %{
        "$or" => [
          %{"field" => "city",     "condition" => %{"$eq" => "Paris"}},
          %{"field" => "category", "condition" => %{"$eq" => "tech"}}
        ]
      }
      assert query_ids(pid, filt) == ["3", "4"]
    end

    test "nested $and inside $or", %{pid: pid} do
      filt = %{
        "$and" => [
          %{
            "$or" => [
              %{"field" => "city", "condition" => %{"$eq" => "NYC"}},
              %{"field" => "city", "condition" => %{"$eq" => "Tokyo"}}
            ]
          },
          %{"field" => "category", "condition" => %{"$eq" => "food"}}
        ]
      }
      assert query_ids(pid, filt) == ["1", "2", "5"]
    end
  end

  # ---------------------------------------------------------------------------
  # Edge cases
  # ---------------------------------------------------------------------------

  describe "edge cases" do
    setup do
      pid = start_session_with("test-filter-edge-#{System.unique_integer([:positive])}", filter_docs())
      %{pid: pid}
    end

    test "no matches returns empty list", %{pid: pid} do
      assert query_ids(pid, %{"field" => "city", "condition" => %{"$eq" => "Berlin"}}) == []
    end

    test "docs without the filtered field are skipped", %{pid: pid} do
      # doc "6" has no metadata — should not appear even with $ne
      ids = query_ids(pid, %{"field" => "city", "condition" => %{"$ne" => "nonexistent"}})
      refute "6" in ids
    end

    test "nil filter returns all docs", %{pid: pid} do
      {:ok, result} = Moss.Session.query(pid, "test", embedding: query_emb(), top_k: 10)
      assert length(result.docs) == 6
    end
  end

  # ---------------------------------------------------------------------------
  # $near geo filter
  # ---------------------------------------------------------------------------

  describe "$near geo filter" do
    setup do
      pid = start_session_with("test-geo-#{System.unique_integer([:positive])}", geo_docs())
      %{pid: pid}
    end

    test "within range matches ts and sol", %{pid: pid} do
      # 10km around Times Square — ts (~0km) and sol (~8.7km) match, par does not
      filt = %{"field" => "location", "condition" => %{"$near" => "40.7580,-73.9855,10000"}}
      {:ok, result} = Moss.Session.query(pid, "test", embedding: query_emb(), top_k: 10, filter: filt)
      ids = Enum.map(result.docs, & &1.id)
      assert "ts"  in ids
      assert "sol" in ids
      refute "par" in ids
    end

    test "5km radius excludes sol (~8.7km away)", %{pid: pid} do
      filt = %{"field" => "location", "condition" => %{"$near" => "40.7580,-73.9855,5000"}}
      {:ok, result} = Moss.Session.query(pid, "test", embedding: query_emb(), top_k: 10, filter: filt)
      ids = Enum.map(result.docs, & &1.id)
      assert "ts"  in ids
      refute "sol" in ids
    end

    test "doc without location field is skipped", %{pid: pid} do
      filt = %{"field" => "location", "condition" => %{"$near" => "40.7580,-73.9855,100000"}}
      {:ok, result} = Moss.Session.query(pid, "test", embedding: query_emb(), top_k: 10, filter: filt)
      ids = Enum.map(result.docs, & &1.id)
      refute "nol" in ids
    end

    test "huge radius matches all docs with location", %{pid: pid} do
      filt = %{"field" => "location", "condition" => %{"$near" => "40.7580,-73.9855,10000000"}}
      {:ok, result} = Moss.Session.query(pid, "test", embedding: query_emb(), top_k: 10, filter: filt)
      ids = Enum.map(result.docs, & &1.id) |> Enum.sort()
      assert ids == ["par", "sol", "ts"]
    end
  end

  # ---------------------------------------------------------------------------
  # Hybrid search + filter interaction
  # ---------------------------------------------------------------------------

  describe "hybrid search + filter" do
    setup do
      pid = start_session_with("test-hybrid-#{System.unique_integer([:positive])}", hybrid_docs())
      %{pid: pid}
    end

    test "cross-signal doc surfaces with hybrid fusion", %{pid: pid} do
      {:ok, result} = Moss.Session.query(pid, "focusterm", embedding: query_emb(), top_k: 2, alpha: 0.5)
      ids = Enum.map(result.docs, & &1.id)
      assert "cross" in ids
    end

    test "filter is enforced even with hybrid scoring", %{pid: pid} do
      filt = %{"field" => "group", "condition" => %{"$eq" => "keep"}}
      {:ok, result} = Moss.Session.query(pid, "focusterm", embedding: query_emb(), top_k: 4, alpha: 0.5, filter: filt)
      ids = Enum.map(result.docs, & &1.id)
      refute "drop" in ids
    end
  end
end
