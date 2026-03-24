# Contributing

Thanks for your interest in improving Pipecat Moss! This document captures the
workflow for working from the source repository.

## Development Environment

1. Clone the repository and `cd` into it.
2. Install dependencies using [uv](https://github.com/astral-sh/uv):

   ```bash
   uv sync
   ```

3. Activate the virtual environment so local scripts (examples, tests) run
   against the checked-out code:

   ```bash
   source .venv/bin/activate
   ```

## Running Examples

With the environment active you can run the sample pipelines shipped in the
[examples](examples) directory. Please refer to the [README](README.md) for detailed instructions on running the examples.

## Code Style

Follow the existing formatting and logging patterns in the codebase.

## Submitting Changes

1. Open a pull request that describes the motivation, highlights user-facing
   changes, and includes validation steps.
2. Be responsive to review feedback so the change can merge smoothly.

We appreciate your contributions!
