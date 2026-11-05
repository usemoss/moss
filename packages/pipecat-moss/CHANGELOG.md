# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-03

### Added
- `MossRetrievalService(cache_path=...)` keeps downloaded indexes on disk, so a load in a new process reads an unchanged index from disk instead of downloading it.
- `load_index(index_name, auto_refresh=...)`.
- The package declares its BSD-2-Clause license in its metadata.

### Changed
- `MossIndexProcessor` replaces the passages it added for the last query instead of keeping every turn's passages in the context, so token use no longer grows with each turn. A turn with no results, or whose query fails, removes them. A speculative turn gets its passages in its own copy of the context.
- Depends on `pipecat-ai` without the `runner` extra, which only the examples use.

### Fixed
- `MossIndexProcessor` forwards the `LLMContextFrame` it received after a failed retrieval too.
- Missing credentials raise `ValueError`.

## [0.1.0] - 2026-10-22

### Changed

- Depend on `moss>=1.20.0` instead of `inferedge-moss`; import from `moss`.
- Require `pipecat-ai>=1.8,<2` and Python 3.11+.
- `MossIndexProcessor` handles `LLMContextFrame` only and forwards the original frame, keeping fields such as `speculation`.
- Queries pass `QueryOptions(top_k, alpha)`.
- `MossRetrievalService` falls back to `MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY` env vars.

### Removed

- `LLMMessagesFrame` and `OpenAILLMContextFrame` handling (removed in pipecat 1.8).
- `AddDocumentsOptions` re-export (gone from the Moss SDK; use `MutationOptions`).

## [0.0.3] - 2026-03-24

### Added
- Supports latest version of moss

## [0.0.2] - 2026-01-18

### Added

- Support for Pipecat v0.0.99.
- Support for LLMContext and LLMContextAggregatorPair
- removed deprecated OpenAILLMContext and OpenAILLMContextAggregatorPair

## [0.0.1] - 2025-12-29

### Added

- Initial release of `pipecat-moss` integration.
- `MossRetrievalService` for augmenting Pipecat LLM contexts with retrieved documents
- Example `moss-retrieval-demo.py` demonstrating a full voice pipeline with retrieval.
- `moss-create-index-demo.py` for creating and populating a Moss index.