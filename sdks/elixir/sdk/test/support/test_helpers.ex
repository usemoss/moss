defmodule Moss.TestHelpers do
  @moduledoc """
  Shared test constants and helpers.
  Counterpart to tests/constants.py in both Python SDKs.
  """

  def test_project_id, do: System.get_env("MOSS_TEST_PROJECT_ID", "test-project-id")
  def test_project_key, do: System.get_env("MOSS_TEST_PROJECT_KEY", "test-project-key")

  def has_real_cloud_creds? do
    System.get_env("MOSS_TEST_PROJECT_ID") != nil and
      System.get_env("MOSS_TEST_PROJECT_KEY") != nil
  end

  def generate_unique_index_name(prefix \\ "test") do
    ts = System.os_time(:millisecond)
    "#{prefix}-#{ts}"
  end

  def generate_unique_session_name(prefix \\ "test-session") do
    ts = System.os_time(:millisecond)
    "#{prefix}-#{ts}"
  end

  # Shared test documents (AI/ML topics) — used in manage_client tests
  def test_documents do
    [
      %Moss.DocumentInfo{
        id: "doc-1",
        text: "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed.",
        metadata: %{"category" => "ai", "topic" => "machine_learning", "difficulty" => "intermediate"}
      },
      %Moss.DocumentInfo{
        id: "doc-2",
        text: "Deep learning uses neural networks with multiple layers to model and understand complex patterns in data.",
        metadata: %{"category" => "ai", "topic" => "deep_learning", "difficulty" => "advanced"}
      },
      %Moss.DocumentInfo{
        id: "doc-3",
        text: "Natural language processing enables computers to interpret and manipulate human language for various applications.",
        metadata: %{"category" => "ai", "topic" => "nlp", "difficulty" => "intermediate"}
      },
      %Moss.DocumentInfo{
        id: "doc-4",
        text: "Computer vision enables machines to interpret and understand visual information from the world around them.",
        metadata: %{"category" => "ai", "topic" => "computer_vision", "difficulty" => "intermediate"}
      },
      %Moss.DocumentInfo{
        id: "doc-5",
        text: "Reinforcement learning is a type of machine learning where an agent learns to make decisions by performing actions and receiving rewards.",
        metadata: %{"category" => "ai", "topic" => "reinforcement_learning", "difficulty" => "advanced"}
      }
    ]
  end

  def additional_test_documents do
    [
      %Moss.DocumentInfo{
        id: "doc-6",
        text: "Data science combines statistics, programming, and domain expertise to extract insights from data.",
        metadata: %{"category" => "data_science", "topic" => "analytics", "difficulty" => "intermediate"}
      },
      %Moss.DocumentInfo{
        id: "doc-7",
        text: "Cloud computing provides on-demand access to computing resources over the internet.",
        metadata: %{"category" => "infrastructure", "topic" => "cloud", "difficulty" => "beginner"}
      }
    ]
  end

  # Filter test data — exact parity with test_session_filter.py / test_index_filter.py
  def filter_docs do
    [
      {%Moss.DocumentInfo{id: "1", text: "coffee shop in NYC",   metadata: %{"city" => "NYC",   "price" => "12", "category" => "food"}},   [1.0, 0.0, 0.0, 0.0]},
      {%Moss.DocumentInfo{id: "2", text: "sushi bar in Tokyo",   metadata: %{"city" => "Tokyo", "price" => "45", "category" => "food"}},   [0.0, 1.0, 0.0, 0.0]},
      {%Moss.DocumentInfo{id: "3", text: "tech meetup in NYC",   metadata: %{"city" => "NYC",   "price" => "0",  "category" => "tech"}},   [0.0, 0.0, 1.0, 0.0]},
      {%Moss.DocumentInfo{id: "4", text: "museum in Paris",      metadata: %{"city" => "Paris", "price" => "20", "category" => "culture"}}, [0.0, 0.0, 0.0, 1.0]},
      {%Moss.DocumentInfo{id: "5", text: "street food in Tokyo", metadata: %{"city" => "Tokyo", "price" => "8",  "category" => "food"}},   [0.5, 0.5, 0.0, 0.0]},
      {%Moss.DocumentInfo{id: "6", text: "no metadata doc"},                                                                                [0.1, 0.1, 0.1, 0.1]}
    ]
  end

  def geo_docs do
    [
      {%Moss.DocumentInfo{id: "ts",  text: "times square NYC",     metadata: %{"location" => "40.7580,-73.9855"}}, [1.0, 0.0, 0.0, 0.0]},
      {%Moss.DocumentInfo{id: "sol", text: "statue of liberty",    metadata: %{"location" => "40.6892,-74.0445"}}, [0.0, 1.0, 0.0, 0.0]},
      {%Moss.DocumentInfo{id: "par", text: "eiffel tower paris",   metadata: %{"location" => "48.8566,2.3522"}},   [0.0, 0.0, 1.0, 0.0]},
      {%Moss.DocumentInfo{id: "nol", text: "doc without location", metadata: %{"city" => "NYC"}},                  [0.0, 0.0, 0.0, 1.0]}
    ]
  end

  def hybrid_docs do
    [
      {%Moss.DocumentInfo{id: "emb1",  text: "noise text",                                        metadata: %{"group" => "keep"}}, [1.00, 0.0, 0.0, 0.0]},
      {%Moss.DocumentInfo{id: "emb2",  text: "noise text",                                        metadata: %{"group" => "keep"}}, [0.90, 0.0, 0.0, 0.0]},
      {%Moss.DocumentInfo{id: "cross", text: "focusterm focusterm focusterm",                     metadata: %{"group" => "keep"}}, [0.80, 0.0, 0.0, 0.0]},
      {%Moss.DocumentInfo{id: "kw1",   text: "focusterm focusterm focusterm focusterm focusterm", metadata: %{"group" => "keep"}}, [0.10, 0.0, 0.0, 0.0]},
      {%Moss.DocumentInfo{id: "kw2",   text: "focusterm focusterm focusterm focusterm",           metadata: %{"group" => "keep"}}, [0.05, 0.0, 0.0, 0.0]},
      {%Moss.DocumentInfo{id: "drop",  text: "irrelevant text",                                   metadata: %{"group" => "drop"}}, [0.01, 0.0, 0.0, 0.0]}
    ]
  end

  @query_emb [1.0, 0.0, 0.0, 0.0]
  def query_emb, do: @query_emb
end
