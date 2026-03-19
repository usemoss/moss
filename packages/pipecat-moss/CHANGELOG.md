# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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