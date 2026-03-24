---
name: moss-search
description: |
  Sub-10ms semantic search for Zo via Moss. Create indexes, add documents, and query them
  with semantic and keyword search. Use when users want to search through documents,
  knowledge bases, or any text content.
metadata:
  author: Moss
  category: Community
---

# Moss Search

Sub-10ms semantic search. Run from anywhere:

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh load-index support-docs
bash /home/workspace/Skills/moss-search/scripts/moss.sh search support-docs "how long do refunds take?"
bash /home/workspace/Skills/moss-search/scripts/moss.sh create-index my-docs '[{"id":"1","text":"Refunds take 3-5 days."}]'
```

## Commands

### load-index

Download an index into memory for sub-10ms local queries. Always call this before searching an index for the first time.

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh load-index <index-name>
```

Examples:

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh load-index support-docs
bash /home/workspace/Skills/moss-search/scripts/moss.sh load-index code-docs
```

### search

Search a loaded index. Sub-10ms after `load-index`.

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh search <index-name> "<query>" [top_k]
```

Examples:

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh search support-docs "how do I get a refund"
bash /home/workspace/Skills/moss-search/scripts/moss.sh search code-docs "authentication middleware" 10
```

### create-index

Create a new index with initial documents.

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh create-index <index-name> '<json-docs-array>'
```

Example:

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh create-index faq '[{"id":"1","text":"Refunds take 3-5 business days."},{"id":"2","text":"Contact support@example.com for help."}]'
```

### list-indexes

List all available indexes.

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh list-indexes
```

### add-docs

Add documents to an existing index.

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh add-docs <index-name> '<json-docs-array>'
```

Example:

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh add-docs faq '[{"id":"3","text":"Free shipping on orders over $50."}]'
```

### delete-docs

Delete documents by ID.

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh delete-docs <index-name> '["id1","id2"]'
```

### get-docs

Retrieve documents from an index.

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh get-docs <index-name>
bash /home/workspace/Skills/moss-search/scripts/moss.sh get-docs <index-name> '["id1","id2"]'
```

### delete-index

Delete an entire index.

```bash
bash /home/workspace/Skills/moss-search/scripts/moss.sh delete-index <index-name>
```

## For Zo

### On every new conversation

1. Run `moss.sh list-indexes` to see what indexes are available.
2. Run `moss.sh load-index <index>` for each index the user is likely to need.
3. Run `moss.sh search <index> "<keywords>"` to surface relevant context from the user's first message.
4. Weave relevant results into your response naturally.

Skip the startup load for vague openers like "hey" or "what's up".

### When to search

- User asks about information that might be in an indexed collection
- User references prior documents, notes, or knowledge base content
- You are about to give advice and relevant indexed context may exist
- Earlier search results were weak — try 2-3 alternate keyword queries

### When to create/update indexes

- User explicitly asks: "index this", "add this to search", "create an index"
- User provides documents, notes, or data they want searchable
- User wants to build a knowledge base or FAQ

### Using search results

- Use relevant results naturally — cite them inline
- If a result conflicts with what the user says, mention it: "The indexed docs say X — has that changed?"
- If no relevant results are found, proceed normally

## Behavior summary

| User signal | Action |
|---|---|
| New conversation starts | `moss.sh list-indexes` then `moss.sh load-index` + `moss.sh search` relevant indexes |
| "Search for..." / "Find..." / "Look up..." | `moss.sh search <index> "<query>"` (load-index first if not loaded) |
| "Index this" / "Add to search" | `moss.sh add-docs <index> '<docs>'` |
| "Create an index" / "New collection" | `moss.sh create-index <name> '<docs>'` |
| "Delete this document" | `moss.sh delete-docs <index> '["id"]'` |
| "Remove this index" | `moss.sh delete-index <index>` |
| "What indexes do I have?" | `moss.sh list-indexes` |
| "Show me the documents in..." | `moss.sh get-docs <index>` |
