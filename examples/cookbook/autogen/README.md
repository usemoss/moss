# Building a Multi-Agent E-Commerce Support System with AutoGen and Moss

This cookbook demonstrates how to orchestrate a collaborative, multi-agent e-commerce support system using **AutoGen** for intelligent routing, and **Moss** for blazing-fast, sub-10ms context retrieval.

When building production support systems, answering customer inquiries often requires pulling data from several different departments. If your AI agents take 1-2 seconds to retrieve context from the cloud, your multi-agent architecture will bottleneck and become unacceptably slow.

## System Architecture

1. **Intelligent Orchestration**: A `SelectorGroupChat` managed by a routing LLM autonomously delegates tasks to specialized agents (e.g., Shipping, Returns, Product).
2. **Domain Isolation**: Independent vector knowledge bases deployed into local memory via Moss, preventing agents from hallucinating cross-domain context.
3. **Latency Benchmarking**: Real-time metrics proving how in-memory semantic search eliminates the compounding backend latency bottlenecks typical of AutoGen workflows.

## Prerequisites

1. Install the required libraries:
```bash
uv pip install autogen-agentchat "autogen-ext[openai]" moss python-dotenv
```

2. You will need:
- An **OpenAI API Key**.
- A Moss **Project ID** and **Project Key** (Get a free tier at [moss.dev](https://www.moss.dev/)).

Set these up in a `.env` file within this directory (see `.env.example`).

## Cookbook Walkthrough

The `moss_autogen.ipynb` notebook breaks the application build into 5 distinct architectural steps:

1. **Setup & Core Clients**: We wire up our `OpenAIChatCompletionClient` and our `MossClient`.
2. **Creating Isolated Knowledge Domains**: We load three separate JSON databases (Products, Shipping, Returns) into Moss. We explicitly call `moss_client.load_index()` to securely cache the vector data into local memory.
3. **Defining the Agent Tools**: We wrap Moss semantic queries into asynchronous Python tools. By natively extracting `SearchResult.time_taken_ms`, we prove that the database traversal overhead consistently evaluates to `< 1 ms`.
4. **Orchestrating the AutoGen Team**: We deploy a `SelectorGroupChat` where the LLM Manager reads the `system_message` of the Shipping, Returns, and Product agents to autonomously route inquiries.
5. **Execution & Benchmarking**: We run the system through several complex test flows, aggregating total retrieval metrics to showcase how Moss local logic naturally prevents compounding system lag.

## Why AutoGen + Moss?

**Zero-Latency Agent Flow**: Traditional vector databases can add 200-500ms of latency per query via HTTP. In a multi-agent system where 3 agents might search 2 times each, that is nearly 2-3 seconds of pure retrieval waiting!

By running `moss_client.load_index()`, we bypass the cloud layer entirely. Your semantic indices are pushed directly into your server's RAM, allowing Moss's native Rust execution to perform semantic searches organically in `< 10ms`. This eliminates database downtime, keeping your LLM context windows feeding instantly.
