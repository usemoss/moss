# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2026-04-06

### Added

- Initial release of `gemma-moss` integration.
- `MossRetriever` for reusable Moss semantic retrieval.
- `GemmaMossSession` for conversational RAG with Gemma via Ollama.
- `DefaultContextFormatter` for formatting retrieved documents.
- `make_ollama_query_rewriter` convenience helper.
- CLI chatbot demo in `examples/moss-gemma-demo.py`.
