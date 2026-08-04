# moss-chunking

Pluggable text chunking for Moss. Splitters are swappable; the shape of what they
emit is not.

## Why this exists

Chunking isn't in any Moss SDK, so every app rolls its own. Two of them, in this
repo, both already wrap chunks in the SDK's `DocumentInfo` — and still can't be
treated uniformly, because they agree on nothing inside it:

| | `examples/moss-pikachu` | `apps/moss-llamaindex` |
| --- | --- | --- |
| id | `{path}#chunk-0001` | `{filename}-p{page}-c{idx}` |
| metadata | `path`, `filename`, `chunk`, `extension`, `modified_at` | `source`, `page` |
| split | 1800 chars / 300 overlap | 400 words / 2-sentence overlap |

Zero metadata keys in common. The envelope is shared; the contract is missing.

Splitting strategy is genuinely contested and content-dependent — code, markdown
and transcripts all want different cuts — which is why it stays pluggable, and
why this is a standalone package rather than something frozen into five language
runtimes. But the *output* isn't contested. Nobody wants a bespoke ID scheme;
they wrote one because none was written down.

So this package pins the output and leaves the cutting open.

## Install

```bash
uv pip install -e ".[dev]"   # from packages/moss-chunking
```

Depends only on `moss`. Sentence detection is regex-based rather than nltk-backed
so there is no model download or corpus to provision.

## Use

```python
from moss_chunking import SentenceSplitter, chunk_document, ingest

docs = chunk_document(text, source="notes.md", strategy=SentenceSplitter())
await ingest(docs, project_id, project_key, "my-index")
```

`docs` are ordinary `DocumentInfo`s — they go anywhere the SDK takes documents;
`ingest` is just the connector template's one-call shortcut into a fresh index.

## The contract

Every chunk, from every strategy, carries:

| key | meaning |
| --- | --- |
| `source` | what was chunked — path, URL, document name |
| `chunk_index` | position in the sequence, from `0` |
| `locator_type` | `char`, `line` or `page` |
| `locator_start` / `locator_end` | position, in that unit |

IDs are `{source}#chunk-{index:04d}` — zero-padded so they sort in cut order, and
stable across runs so re-chunking an unchanged document replaces its chunks
rather than duplicating them. Values are all strings, because Moss types metadata
as `Dict[str, str]`.

That stability is only worth something if you keep it on the way in, which is why
`ingest` drops the one option the connector template it mirrors does offer:
`auto_id`. Random UUIDs defeat the contract — re-indexing an unchanged document
appends a second copy of every chunk instead of replacing what is already there.

**Position is not a fixed field list.** Plain text is located by character offset,
PDFs by page, code by line; character offsets are meaningless for a PDF and page
numbers are meaningless for a source file. So a chunk declares its unit instead of
assuming one. That's the one real design call in the package.

Pass source-level facts a splitter can't know via `extra`:

```python
chunk_document(text, "notes.md", CharSplitter(), extra={"extension": "md"})
```

`extra` cannot shadow the reserved keys above — that's an error, not a silent
overwrite.

## Strategies

| | cuts on | ceiling | notes |
| --- | --- | --- | --- |
| `CharSplitter` | fixed character windows | hard | pikachu's 1800/300 are the defaults |
| `SentenceSplitter` | sentence boundaries | soft | llamaindex's 400 words / 2 sentences are the defaults |
| `ParagraphSplitter` | blank lines | soft | never breaks a paragraph, even an oversized one |
| `RecursiveSplitter` | paragraphs → lines → sentences → words | hard | falls back to a hard cut if nothing fits |

Soft ceiling means a single unit larger than the budget is emitted whole rather
than cut. `RecursiveSplitter` is the one to reach for when the ceiling must hold.

Write your own by implementing `split(text) -> Iterable[Chunk]`:

```python
class MyStrategy:
    def split(self, text: str) -> Iterator[Chunk]:
        yield Chunk(text=..., index=..., locator_type="line", locator_start=..., locator_end=...)
```

A strategy never builds a `DocumentInfo` — that's the contract's job, and handing
it to callers is exactly how pikachu and llamaindex drifted apart.

The invariant the tests enforce for every strategy:
`text[chunk.locator_start:chunk.locator_end] == chunk.text`. Offsets point into
the original string, never a normalized copy. Break it and position metadata
becomes decorative — you can address a chunk but not find it again.

Semantic chunking is not here yet: it needs embeddings, which makes it a
different shape of dependency. It's the obvious next strategy.

## Enrichment

Moss scores BM25 over chunk text, so facts that live only in metadata — the
filename, the folder — are invisible to the keyword half of a hybrid query.
Restating them in the text makes them matchable. Pikachu already does this by
hand; here it's a composable post-step that works with any strategy:

```python
from moss_chunking import prepend_source_context

doc = prepend_source_context(doc, filename="notes.md", path="/docs/notes.md")
```

ID and metadata are untouched, so an enriched chunk stays addressable.

## Tests

```bash
.venv/bin/python -m pytest -q
```
