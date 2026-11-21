# Workflow: Release a new version to PyPI

## Objective
Publish a new version of `stack-scout-mcp` so `uvx stack-scout-mcp` users get it.
Publishing is automatic from GitHub (`.github/workflows/publish.yml`) using PyPI Trusted Publishing:
no passwords or API tokens exist anywhere.

## Required inputs
- The new version number, e.g. `0.2.0` (semantic versioning: fixes 0.1.1, features 0.2.0)
- The owner's OK. A published version can be yanked but never replaced, so always ask first.

## Steps
1. Make sure everything passes locally:
   ```
   python -m unittest discover tests
   .venv\Scripts\python.exe tests\live_mcp_smoke.py
   ```
2. Build and test the package in a throwaway environment (catches missing files):
   ```
   uv build
   uv venv <scratch>\venv && uv pip install --python <scratch>\venv dist\stack_scout_mcp-<version>-py3-none-any.whl
   <scratch>\venv\Scripts\python.exe tests\live_mcp_smoke.py   # or call the stack-scout-mcp command via an MCP client
   ```
3. Set `__version__` in `stack_scout_mcp/__init__.py` (pyproject reads it from there).
4. Commit, then tag with the same version and push both:
   ```
   git commit -am "Release v0.2.0"
   git tag v0.2.0
   git push origin main v0.2.0
   ```
5. Watch the `publish` run in GitHub Actions. It runs the tests, checks that the tag matches `__version__`,
   builds, and uploads to PyPI.
6. Check https://pypi.org/project/stack-scout-mcp/ and run `uvx stack-scout-mcp@<version>` to confirm.

## Edge cases
- **Tag doesn't match `__version__`:** the build job fails on purpose. Fix the version, delete the tag
  (`git tag -d v0.2.0 && git push origin :refs/tags/v0.2.0`), and tag again.
- **"invalid-publisher" from PyPI:** the trusted publisher on PyPI must match exactly: owner
  `mhassaan0806-jpg`, repo `stack-scout-mcp`, workflow `publish.yml`, environment `pypi`.
- **Version already exists on PyPI:** PyPI never accepts the same version twice. Bump the version.
- **README changes:** the PyPI page shows the README from the release, so relative links break there.
  Keep links in README.md absolute (https://github.com/...).

## Learnings log
- 2026-11-22: First release prepared as 0.1.0. Package moved from top-level `tools/` to `stack_scout_mcp/`,
  because a top-level `tools` package would clash with other installs.
