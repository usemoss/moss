# TODOs

## CI/CD pipeline for integration packages

**What:** Add GitHub Actions workflows to build, test, and publish `strands-agents-moss` and `semantic-kernel-moss` to PyPI.

**Why:** Neither integration package has a CI/CD pipeline. Code without distribution is code nobody can use. Users currently have no way to `pip install` these packages from PyPI.

**Context:** Both packages use setuptools with `pyproject.toml`. Tests use pytest + pytest-asyncio. Linting uses ruff. A single reusable workflow could cover both packages since they share the same build system and test tooling. Consider matrix strategy for Python 3.10-3.13.

**Depends on:** Nothing. Can be done independently.

## .NET Semantic Kernel plugin design doc

**What:** Write a design document for a .NET version of the Moss Semantic Kernel plugin.

**Why:** The GitHub issue (#82) lists .NET as a stretch goal. Semantic Kernel has strong .NET adoption in enterprise shops. A design doc captures the approach (NuGet package, IKernelPlugin interface, C# async patterns) without committing to implementation.

**Context:** The Python plugin (`semantic-kernel-moss`) is the reference implementation. The .NET version would follow the same pattern: single `Search` kernel function, constructor-configured `MossClient`, pre-loaded index. Key decisions: whether to use the .NET Moss SDK (if it exists) or wrap the Python SDK, and how to handle the async index loading lifecycle in C#.

**Depends on:** Python plugin shipped and validated by users.
