# Building an Intelligent E-Commerce Support Team with AutoGen and Moss

This cookbook demonstrates how to build a collaborative multi-agent e-commerce support system using [AutoGen](https://github.com/microsoft/autogen) (v0.4.x) and [Moss](https://moss.dev) as a real-time semantic search runtime. 

When building production support systems, answering customer inquiries often requires pulling data from several different departments. In this cookbook, we will build a **dynamic, multi-agent AI customer support team** designed to resolve complex, multi-step customer issues autonomously by leaning on Intelligent Routing and specialized tools.

## Prerequisites

Install the required libraries:

```bash
uv pip install autogen-agentchat "autogen-ext[openai]" inferedge-moss python-dotenv
```

You will need:
- A Moss **Project ID** and **Project Key** (Get them from your Moss dashboard).
- An **OpenAI API Key**.

Set these up in a `.env` file within this directory (see `.env.example`).

---

## Cookbook Walkthrough

The notebook (`moss_autogen.ipynb`) breaks the application build into 5 distinct steps. Here is what you will learn:

### 1. Instrumenting Moss
We wrap the standard `MossClient` in a custom `InstrumentedMossSearch` class. 
This allows us to track exactly how many times agents query the database and measure the high-resolution execution time (`time.perf_counter`) of every search. Measuring latency is critical for agentic loops, as slow tools compound exponentially when multiple agents collaborate.

### 2. Loading Agent Datasets
To ensure high accuracy, we load three separate JSON datasets into three distinct Moss indices (`product_catalog_index`, `shipping_policies_index`, `returns_index`). This prevents "context noise", ensuring the shipping agent doesn't pull product specifications by mistake when generating its answer.

### 3. Creating Agent Tools
We convert our instrumented Moss queries into asynchronous Python functions (`product_search`, `shipping_search`, `returns_search`). These act as the explicit tools our agents will call when they need external knowledge.

### 4. Setting up the Intelligent Routing
We use `SelectorGroupChat` configured for **Intelligent LLM Routing**. We provide the `model_client` directly to the `SelectorGroupChat` without a hardcoded selection function, allowing the LLM to act as the "Manager". The manager dynamically reads the `system_message` of each agent to logically deduce who should speak next.

### 5. Running the Multi-Agent Flows
We test the system against three different queries, culminating in a complex broken item report. The LLM Manager dynamically analyzes the query, hands it to Returns, analyzes the result, hands it to Shipping, and finally invokes the Summary agent to deliver the final response.

---

## Why use Moss for Agents?

**Real-Time Retrieval**: Traditional vector databases can add 200-500ms of latency per query. In a multi-agent system where 3 agents might search 2 times each, that's nearly 2-3 seconds of pure retrieval waiting. Moss's internal search executes in sub-10ms, drastically cutting down agent downtime.


 
> **Hosted Cloud vs. Local Execution Latency**  
> If you run this cookbook using the **hosted Moss cloud API**, your total `moss.query()` benchmarking latency will hover around **~1.2 seconds**. This is normal; it accounts for internet transit and remote embedding generation. 
> To achieve true **sub-10ms** end-to-end execution times, deploy a **self-hosted local instance** of Moss where the search runtime sits directly next to your agents!
