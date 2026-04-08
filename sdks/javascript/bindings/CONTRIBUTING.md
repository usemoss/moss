# Contributing to @moss-dev/moss-core

We welcome improvements to the JavaScript Moss-Core binding. This guide outlines the local setup and expectations before opening a pull request.

## Prerequisites

- Node.js 20+
- npm 8+
- Rust toolchain (stable channel)

Install dependencies with:

```bash
npm install
```

## Development Workflow

1. Create a feature branch off the latest `main`.
2. Make your changes.
3. Run the quality gates:
	- `npm run build:debug`
4. Commit with clear messages referencing issues when possible.
5. Ensure `CHANGELOG.md` and version numbers are updated if the change affects the public API.
6. Open a pull request and describe the motivation, approach, and testing performed.

## Commit Message Guidelines

- Use the imperative mood (e.g., "Add index create helper").
- Prefix breaking changes with `!` (e.g., `feat!: drop support for Node 16`).
- Reference related issues using GitHub shorthand (`#123`).

## Code Style

- Rust code is formatted with `cargo fmt`.
- Follow existing patterns for module exports and error handling.

## Reporting Issues

Include the following information when filing bugs:

- Node.js and npm versions
- Operating system and architecture
- Reproduction steps (ideally with a minimal example)
- Relevant logs or stack traces

Thank you for helping us improve Moss!
