# Development Setup

Guide for developing and contributing to `moss-cli`.

## Prerequisites

- Python 3.10+
- The `moss` SDK installed (either from PyPI or local editable install)
- `pip` with virtual environment support

## Quick Setup

```bash
# 1. Clone the repo and navigate to the CLI package
cd packages/moss-cli

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install the moss SDK
pip install moss

# 4. Install moss-cli in editable mode with dev dependencies
pip install -e ".[dev]"

# 5. Set up credentials for testing
export MOSS_PROJECT_ID="your-project-id"
export MOSS_PROJECT_KEY="your-project-key"
# Or run: moss init

# 6. Verify the install
moss --help
moss version
```

## Project Structure

```
moss-cli/
├── pyproject.toml              # Package metadata, dependencies, entry point
├── README.md                   # User-facing documentation
├── SETUP.md                    # This file
├── CHANGELOG.md                # Release history
├── LICENSE                     # BSD 2-Clause License
└── src/moss_cli/
    ├── __init__.py             # Package version
    ├── main.py                 # Typer app, global options, subgroup registration
    ├── config.py               # Auth resolution (flags > env > config file)
    ├── output.py               # Rich tables, JSON serialization
    ├── documents.py            # JSON/CSV/stdin document parsing
    ├── job_waiter.py           # Job polling with progress display
    └── commands/
        ├── init_cmd.py         # moss init
        ├── index.py            # moss index {create,list,get,delete}
        ├── doc.py              # moss doc {add,delete,get}
        ├── search.py           # moss query
        ├── job.py              # moss job status
        └── version.py          # moss version
```

## Running Tests

Tests are not yet included in this package. For now, use the manual testing workflow below.

<!-- TODO: add pytest suite
pytest tests/ -v
pytest tests/ --cov=src/moss_cli --cov-report=html
-->

## Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint
flake8 src/ tests/

# Type check
mypy src/moss_cli/
```

## Manual Testing

Create a test document file:

```bash
cat > /tmp/test-docs.json << 'EOF'
[
  {"id": "1", "text": "Machine learning is a subset of artificial intelligence"},
  {"id": "2", "text": "Deep learning uses neural networks with many layers"},
  {"id": "3", "text": "Natural language processing handles human language"}
]
EOF
```

Run through the full workflow:

```bash
# Create index
moss index create test-cli -f /tmp/test-docs.json --wait

# Verify
moss index list
moss index get test-cli

# Search (downloads index locally by default)
moss query test-cli "what is AI"
moss query test-cli "neural networks" --top-k 2 --json

# Search via cloud API (skips download)
moss query test-cli "what is AI" --cloud

# Document operations
moss doc get test-cli
moss doc get test-cli --ids 1,2

# Cleanup
moss index delete test-cli --confirm
```

## Building for Distribution

```bash
# Build wheel and source distribution
python3 -m build

# Output in dist/
ls dist/
# moss_cli-0.1.0-py3-none-any.whl
# moss_cli-0.1.0.tar.gz
```

## Release Process

1. Update version in `src/moss_cli/__init__.py` and `pyproject.toml`
2. Update `CHANGELOG.md` with release notes
3. Run code quality checks: `black`, `isort`, `flake8`, `mypy`
4. Run the full test suite
5. Build the package: `python3 -m build`
6. Publish to PyPI: `twine upload dist/*`
7. Tag the release: `git tag v0.1.0 && git push --tags`

## Troubleshooting

- **`moss` command not found after install**: Make sure your virtual environment is activated and `pip install -e .` completed successfully. Check `which moss`.
- **Import errors for `moss` SDK**: Ensure the SDK is installed in the same virtual environment. Run `pip list | grep moss`.
- **Auth errors**: Verify credentials with `moss init` or check `MOSS_PROJECT_ID`/`MOSS_PROJECT_KEY` env vars.
- **Rust core errors**: The `moss` SDK depends on `inferedge-moss-core` (Rust bindings). If it fails to install, ensure you have a compatible platform (macOS, Linux). See the SDK's SETUP.md for Rust build prerequisites.
