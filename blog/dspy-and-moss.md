# Building Real-Time RAG with DSPy and Moss

Retrieval Augmented Generation is the backbone of most production AI systems today. You have a knowledge base, a user asks something, you fetch the relevant context, and an LLM synthesizes an answer. Simple in theory. Painful in practice.

The two most common failure modes are slow retrieval and fragile prompts. Vector databases built for analytics workloads introduce 400–900 ms round-trips fine for batch jobs, catastrophic for real-time conversation. And the prompts that wire everything together? They're hand-crafted strings that break whenever your LLM, your documents, or your task changes.

[DSPy](https://github.com/stanfordnlp/dspy) solves the prompt problem. [Moss](https://moss.dev) solves the retrieval speed problem. Together, they give you a RAG pipeline that is both systematically optimized and fast enough for real-time agents.

This post walks through exactly how to combine them.

---

## What Is DSPy?

DSPy is a framework from Stanford NLP for programming language models rather than prompting them. The distinction matters more than it sounds.

When you write a traditional RAG pipeline, you're stringing together a retrieval call and a handwritten prompt. If something breaks the retrieval returns weak context, the LLM ignores instructions, the output format is wrong you tweak the prompt manually. It works, until it doesn't. And it definitely doesn't generalize when you swap models or change the task.

DSPy replaces hand-written prompts with **signatures** (declarative input/output specifications) and **modules** (composable logic units). It then uses **optimizers** (called teleprompters) that automatically compile your program into effective prompts for any LLM by running your pipeline against examples and measuring what works.

### Core Concepts

**Signatures** define the contract of a computation:

```python
# A signature: given a question and context, produce an answer
class GenerateAnswer(dspy.Signature):
    """Answer questions based on retrieved context."""
    context = dspy.InputField(desc="relevant passages")
    question = dspy.InputField()
    answer = dspy.OutputField(desc="concise answer based on context")
```

**Modules** implement that contract with a specific strategy. `dspy.Predict` is the simplest; `dspy.ChainOfThought` adds reasoning steps; `dspy.ReAct` implements the Reason + Act loop for agentic tool use.

**Optimizers** like `BootstrapFewShot` and `MIPROv2` take your pipeline and a set of labeled examples, then search for the best prompts, demonstrations, and instructions automatically.

This means your RAG pipeline becomes a compiled program, not a pile of f-strings.

---

## What Is Moss?

Moss is a semantic search runtime built specifically for AI agents. It lives alongside your application and handles embedding + vector search end-to-end, returning results in under 10 ms.

That number is not a benchmark cherry-pick. Here's end-to-end query latency (embedding included) on 100,000 documents, 750 measured queries, top-k=5:

| System | P50 | P95 | P99 | Mean |
|--------|-----|-----|-----|------|
| **Moss** | **3.1 ms** | **4.3 ms** | **5.4 ms** | **3.3 ms** |
| Pinecone | 432.6 ms | 732.1 ms | 934.2 ms | 485.8 ms |
| Qdrant | 597.8 ms | 775.0 ms | 1120.2 ms | 637.6 ms |
| ChromaDB | 351.8 ms | 423.5 ms | 538.5 ms | 358.0 ms |

The key architectural difference: Moss is a **search runtime**, not a database. You load your index into the runtime once, and queries run in-process — no network hop to a cloud cluster, no HNSW tuning, no sharding decisions. Moss competitors measure search latency separately from embedding; Moss includes both in its P50 of 3.1 ms.

For conversational AI — voice bots, copilots, live customer support — the latency difference between 3 ms and 500 ms is the difference between retrieval that's invisible and retrieval that makes the experience feel broken.

### The Moss API

Moss has Python and TypeScript SDKs. The Python interface is async-first:

```python
from inferedge_moss import MossClient, DocumentInfo, QueryOptions

client = MossClient("your_project_id", "your_project_key")

# Index documents once
await client.create_index("support-docs", [
    DocumentInfo(id="1", text="Refunds are processed within 3–5 business days."),
    DocumentInfo(id="2", text="Orders can be cancelled within 1 hour of placement."),
])

# Load into the runtime, then query
await client.load_index("support-docs")
results = await client.query("support-docs", "how long do refunds take?", QueryOptions(top_k=3))

for doc in results.docs:
    print(f"[{doc.score:.3f}] {doc.text}")  # Returned in {results.time_taken_ms} ms
```

`DocumentInfo` objects carry an `id`, `text`, and optional `metadata` dict. Metadata supports filtering operators (`$eq`, `$and`, `$in`, `$near`) for narrowing results by category, date, or any other field you store.

---

## Why DSPy + Moss?

Both frameworks target the same problem from different angles.

DSPy asks: *how do we make LLM pipelines systematic and robust?* It answers by replacing hand-written prompts with compiled programs and replacing manual tuning with optimization against metrics.

Moss asks: *how do we make retrieval fast enough for real-time AI?* It answers by running the search runtime in-process with sub-10 ms latency.

When you combine them, you get a RAG pipeline where the retrieval is real-time and the reasoning is optimized. The `MossRM` class is the bridge — a DSPy retrieval module that delegates to Moss for search.

---

## The MossRM Module

DSPy's retrieval interface expects a class that extends `dspy.Retrieve` and implements a `forward` method. Here is a complete `MossRM` implementation:

```python
import asyncio
import dspy
from dspy.dsp.utils import dotdict
from dspy.primitives.prediction import Prediction
from dspy.retrievers.retrieve import Retrieve
from inferedge_moss import MossClient, QueryOptions

class MossRM(Retrieve):
    """
    A DSPy retrieval module backed by Moss.

    Args:
        index_name: The name of the Moss index to query.
        moss_client: An initialized MossClient instance.
        k: Default number of top passages to retrieve.
        alpha: Hybrid search blend (0 = keyword, 1 = semantic). Default 0.5.
    """

    def __init__(self, index_name: str, moss_client: MossClient, k: int = 3, alpha: float = 0.5):
        self._index_name = index_name
        self._moss_client = moss_client
        self._alpha = alpha
        super().__init__(k=k)

    def forward(self, query_or_queries: str | list[str], k: int | None = None, **kwargs) -> Prediction:
        k = k if k is not None else self.k
        queries = [query_or_queries] if isinstance(query_or_queries, str) else query_or_queries
        queries = [q for q in queries if q]
        passages = []

        for query in queries:
            options = QueryOptions(top_k=k, alpha=self._alpha, **kwargs)
            result = asyncio.run(self._moss_client.query(self._index_name, query, options=options))
            for doc in result.docs:
                passages.append(
                    dotdict({"long_text": doc.text, "id": doc.id, "metadata": doc.metadata, "score": doc.score})
                )

        return passages
```

A few design notes worth understanding:

**`alpha` controls hybrid search.** Moss supports blending keyword and semantic retrieval. `alpha=0` is pure keyword (BM25-style), `alpha=1` is pure semantic (vector cosine), and values in between blend both signals. For FAQ-style knowledge bases where exact phrasing matters, lower alpha values can improve precision. For open-ended queries, higher alpha is usually better.

**The async bridge.** `MossClient` methods are async, but DSPy's `forward` calls are synchronous. The `asyncio.run()` call bridges them. In a notebook, you'll need `nest_asyncio` applied first to avoid event loop conflicts.

**`dotdict` for DSPy compatibility.** DSPy's pipeline internals expect retrieved passages as `dotdict` objects with a `long_text` field. The module maps Moss's `doc.text` to `long_text` and preserves `id`, `metadata`, and `score` for downstream use.

---

## Building a RAG Pipeline

Let's build a complete customer support bot using DSPy + Moss. The knowledge base covers shipping, returns, payments, and account management.

### Step 1: Index Your Documents

```python
from inferedge_moss import MossClient, DocumentInfo
import os

client = MossClient(
    os.environ["MOSS_PROJECT_ID"],
    os.environ["MOSS_PROJECT_KEY"]
)

documents = [
    DocumentInfo(
        id="faq-shipping-001",
        text=(
            "How can I change my shipping address? Contact our customer service team at support@store.com "
            "or call 1-800-555-0100 before your order is processed. Once the order has shipped, address "
            "changes are no longer possible."
        ),
        metadata={"category": "shipping", "type": "faq"},
    ),
    DocumentInfo(
        id="faq-returns-001",
        text=(
            "What is the return policy? Items can be returned within 30 days of delivery for a full refund "
            "to your original payment method. Products must be unused and in original packaging."
        ),
        metadata={"category": "returns", "type": "faq"},
    ),
    DocumentInfo(
        id="faq-payment-001",
        text=(
            "Which payment methods are accepted? We accept Visa, Mastercard, American Express, Discover, "
            "PayPal, Apple Pay, and Google Pay. We also offer buy-now-pay-later through Affirm."
        ),
        metadata={"category": "payment", "type": "faq"},
    ),
    # ... add more documents
]

await client.create_index("support-faq", documents)
await client.load_index("support-faq")
```

### Step 2: Configure DSPy with MossRM

```python
import dspy
from dspy.retrieve.retrieve import Retrieve

# Set up the LM
llm = dspy.LM(model="gpt-4.1-mini", api_key=os.environ["OPENAI_API_KEY"])

# Set up the retriever
retriever = MossRM("support-faq", moss_client=client, k=3, alpha=0.5)

# Configure DSPy globally
dspy.configure(lm=llm, rm=retriever)
```

### Step 3: Define Your RAG Module

```python
class SupportRAG(dspy.Module):
    def __init__(self):
        super().__init__()
        self.retrieve = dspy.Retrieve(k=3)
        self.generate = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question: str) -> dspy.Prediction:
        # Retrieve relevant passages from Moss (sub-10 ms)
        passages = self.retrieve(question).passages

        # Synthesize answer with chain-of-thought reasoning
        context = "\n".join(passages)
        prediction = self.generate(context=context, question=question)

        return dspy.Prediction(answer=prediction.answer, context=passages)
```

### Step 4: Run It

```python
rag = SupportRAG()

result = rag(question="Can I return a product I bought last week?")
print(result.answer)
# → "Yes, items can be returned within 30 days of delivery for a full refund
#    to your original payment method, as long as they are unused and in
#    original packaging."
```

### Step 5: Optimize with DSPy

This is where DSPy separates itself from a plain retrieval chain. Given labeled examples, you can automatically optimize the pipeline's prompts using one of DSPy's **optimizers** (called teleprompters).

The typical workflow involves:

1. Defining a simple accuracy metric that measures whether your pipeline produces correct answers
2. Providing a small set of labeled examples (10–20 are usually sufficient)
3. Using an optimizer like `BootstrapFewShot` or `MIPROv2` to compile your module

The optimizer evaluates different few-shot examples for the `ChainOfThought` module, selecting the ones that maximize your accuracy metric. It searches over demonstration options, prompt variations, and other parameters to find what works best for your task. You're no longer guessing which examples to include in your prompt — the framework searches for you.

This optimization is particularly powerful for RAG pipelines because it discovers not just better prompts, but better retrieval queries and demonstration selection strategies.

---

## Using Moss as a ReAct Tool

For more complex queries that require multi-step reasoning — or when you want to let the agent decide *when* to search — you can wrap Moss as a plain Python function and hand it to `dspy.ReAct`:

```python
from inferedge_moss import QueryOptions

def moss_search(query: str) -> str:
    """Searches the knowledge base for relevant information."""
    options = QueryOptions(top_k=5, alpha=0)
    results = asyncio.run(client.query("support-faq", query, options=options))

    if not results.docs:
        return "No relevant information found."

    return "\n".join([f"- {doc.text}" for doc in results.docs])


# Build the ReAct agent
react_agent = dspy.ReAct(
    signature="question -> answer",
    tools=[moss_search],
    max_iters=5
)

question = "Which payment modes are accepted?"
result = react_agent(question=question)

print(result.answer)
# → "The accepted payment modes are Visa, Mastercard, American Express,
#    Discover, PayPal, Apple Pay, Google Pay, Affirm (buy-now-pay-later),
#    and store-issued gift cards."
```

The `ReAct` module implements the Reason-Act-Observe loop from the original [ReAct paper](https://arxiv.org/abs/2210.03629). The agent reasons about whether it needs to search, calls `moss_search` if so, observes the result, and continues until it can produce a final answer. The entire trajectory is available for debugging:

```
thought_0:   I need to find what payment methods are accepted.
tool_name_0: moss_search
tool_args_0: {"query": "payment methods accepted"}
observation_0: - Which payment methods are accepted? We accept Visa, Mastercard...
thought_1:   I have the information needed to answer the question.
tool_name_1: finish
answer:      Visa, Mastercard, American Express, Discover, PayPal, Apple Pay...
```

This pattern is particularly valuable for agents where the user's query may require multiple lookups — for example, a query that spans both shipping and payment information. The agent decides dynamically how many searches to run.

---

## Metadata Filtering

One underused feature is combining semantic search with metadata filters. Moss supports filtering on any field in your `DocumentInfo.metadata`:

```python
from inferedge_moss import QueryOptions

# Only retrieve documents in the "shipping" category
options = QueryOptions(
    top_k=5,
    alpha=0.5,
    filter={"category": {"$eq": "shipping"}}
)
results = await client.query("support-faq", "how long does delivery take?", options=options)
```

In a DSPy context, you can pass filters through the `forward` kwargs:

```python
# In your DSPy module, when calling the retriever directly:
passages = self.retrieve(question, filter={"category": {"$eq": "shipping"}}).passages
```

This is powerful when building multi-tenant applications or category-specific assistants — a billing bot that only ever retrieves from payment documents, or a shipping assistant that never surfaces return policy text.

---

## Choosing Between MossRM and the Tool Pattern

Both approaches work well; they suit different pipeline architectures:

| | MossRM (Retrieve module) | moss_search tool (ReAct) |
|---|---|---|
| **Best for** | Standard RAG pipelines | Agentic, multi-step reasoning |
| **Retrieval timing** | Always retrieves before generating | Agent decides when to retrieve |
| **DSPy optimization** | Fully optimizable via teleprompters | Tool call behavior can be optimized |
| **Transparency** | Context is explicit in the pipeline | Trajectory shows reasoning steps |
| **Complexity** | Lower | Higher |

Start with `MossRM` for a straightforward Q&A system. Move to `dspy.ReAct` with a tool when your queries are open-ended, require disambiguation, or span multiple topics.

---

## Setup

Install the dependencies:

```bash
pip install "inferedge_moss>=1.0.0b15" dspy nest_asyncio python-dotenv
```

Create a `.env` file:

```env
MOSS_PROJECT_ID=your_project_id
MOSS_PROJECT_KEY=your_project_key
OPENAI_API_KEY=your_openai_api_key
```

Get your Moss credentials at [moss.dev](https://moss.dev) — a free tier is available.

The complete working example is in the repo at [`examples/cookbook/dspy/dspy.ipynb`](https://github.com/usemoss/moss/tree/main/examples/cookbook/dspy).

---

## What You've Built

By the end of this setup, you have:

- A Moss index with sub-10 ms semantic search, no cluster to manage
- A DSPy pipeline with signatures and modules instead of handwritten prompts
- An optimizer that selects the best few-shot examples automatically
- An optional ReAct agent that decides when and how to search
- Metadata filtering to scope retrieval to specific document categories

The combination addresses the two root causes of unreliable RAG: slow retrieval that breaks real-time experiences, and brittle prompts that break when anything changes. DSPy handles the second problem systematically; Moss handles the first one at the hardware level.

---

## What's Next

- [Moss documentation](https://docs.moss.dev) — full SDK reference, metadata filtering operators, custom embedding models
- [DSPy documentation](https://dspy.ai) — optimizers, assertions, multi-hop retrieval patterns
- [LangChain + Moss cookbook](https://github.com/usemoss/moss/tree/main/examples/cookbook/langchain) — if your team is already on LangChain
- [Pipecat + Moss](https://github.com/usemoss/moss/tree/main/apps/pipecat-moss) — Moss in a real-time voice pipeline
- [Discord](https://moss.link/discord) — ask questions, share what you're building

---

*Moss is open source under the BSD 2-Clause license and backed by Y Combinator. The SDKs, examples, and integrations in the repo are free to use and modify.*
