# dspy-moss

Moss semantic search retrieval module for [DSPy](https://dspy.ai).

Provides `MossRM` — a `dspy.Retrieve` subclass that plugs into DSPy's RM interface for sub-10ms knowledge retrieval with no external embedder.

## Installation

```bash
pip install dspy-moss
# or
uv add dspy-moss
```

## Quickstart

```python
import dspy
from dspy_moss import MossRM

# Reads MOSS_PROJECT_ID and MOSS_PROJECT_KEY from environment
rm = MossRM(index_name="my-index")
rm.load_index()  # load into this process's memory before querying
dspy.configure(lm=dspy.LM("openai/gpt-4o"), rm=rm)

retrieve = dspy.Retrieve(k=3)
result = retrieve("What is the refund policy?")
for passage in result.passages:
    print(f"[{passage['score']:.3f}] {passage['long_text']}")
```

## Usage patterns

### As a configured retriever

Set `MossRM` as the default retriever for all `dspy.Retrieve` calls in your program:

```python
import dspy
from dspy_moss import MossRM

rm = MossRM(
    index_name="support-kb",
    k=5,
    alpha=0.8,  # 1.0 = semantic only, 0.0 = keyword only
)
dspy.configure(lm=dspy.LM("openai/gpt-4o"), rm=rm)

# Any dspy.Retrieve() now uses Moss
class RAG(dspy.Module):
    def __init__(self):
        self.retrieve = dspy.Retrieve(k=3)
        self.generate = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question):
        context = self.retrieve(question).passages
        return self.generate(context=context, question=question)

rag = RAG()
print(rag("How long do refunds take?").answer)
```

### As a ReAct tool

`MossRM.forward()` is already sync, so pass the instance directly — no wrapper needed:

```python
import dspy
from dspy_moss import MossRM

rm = MossRM(index_name="support-kb", k=5)
rm.load_index()
agent = dspy.ReAct(signature="question -> answer", tools=[rm])
print(agent(question="What payment methods do you accept?").answer)
```

### With an explicit client

```python
from moss import MossClient
from dspy_moss import MossRM

client = MossClient("proj-id", "proj-key")
rm = MossRM(index_name="my-index", moss_client=client, k=5)
```

## Configuration

### MossRM

| Parameter | Default | Description |
| --- | --- | --- |
| `index_name` | (required) | Name of the Moss index to query |
| `moss_client` | `None` | Existing `MossClient`. When omitted, one is created from credentials |
| `project_id` | `MOSS_PROJECT_ID` env var | Moss project ID |
| `project_key` | `MOSS_PROJECT_KEY` env var | Moss project key |
| `k` | `3` | Default number of passages per query |
| `alpha` | `0.8` | Search blend: 1.0 = semantic only, 0.0 = keyword only |

### Passage format

Each entry in `result.passages` is a dict with:

| Key | Type | Description |
| --- | --- | --- |
| `long_text` | `str` | Document text (DSPy's standard passage field) |
| `id` | `str` | Document ID |
| `score` | `float` | Relevance score |
| `metadata` | `dict` | Key-value metadata stored with the document |

### Mutable index helpers

`MossRM` also exposes two optional helpers for agents that write to the knowledge base:

```python
# Read documents
objects = rm.get_objects(num_samples=10)

# Add / upsert documents
rm.insert([{"id": "doc-1", "text": "New fact.", "metadata": {"source": "agent"}}])
```

## License

BSD 2-Clause — see [LICENSE](LICENSE).

## Support

- [Moss Docs](https://docs.moss.dev)
- [Moss Discord](https://discord.gg/eMXExuafBR)
- [DSPy Docs](https://dspy.ai)
