# Repository Guidelines

## Project Structure & Modules
- `src/dbjavagenix/` — Python source (core, database, generator, server[MCP], utils, templates/java).
- `tests/` — Pytest suite; unit tests in `tests/unit/`, selected runners in `tests/run_tests.py`.
- `docs/` — How‑tos and development notes; `config/` holds `config.example.yaml` and test configs.
- Node wrapper: `index.js` starts the MCP server via Python; helper scripts `start-mcp.ps1/.bat`.

## Build, Test & Dev Commands
- Setup (Python): `pip install -r requirements-dev.txt` (or `requirements.txt` for runtime only).
- Lint/format/type: `black src tests && flake8 src tests && mypy src`.
- Tests (with coverage): `pytest -v` (configured via `pyproject.toml`). Unit only: `pytest tests/unit -q`. Runner: `python tests/run_tests.py`.
- CLI help: `python -m dbjavagenix.cli --help`.
- Start MCP (Python): `python -m dbjavagenix.server.mcp_server` or installed entry `dbjavagenix-server`.
- Start MCP (Node): `npm install && npm start` or `node index.js`.

## Coding Style & Naming
- Python: Black (88 cols), Flake8 (E203/E501/W503 ignored), MyPy strict. Use type hints and 4‑space indents.
- Naming: modules `snake_case`, classes `PascalCase`, functions/vars `snake_case`, constants `UPPER_SNAKE_CASE`.
- Templates live under `src/dbjavagenix/templates/java/{Default,MybatisPlus,MybatisPlus-Mixed}` with consistent filenames (e.g., `serviceImpl.mustache`).

## Testing Guidelines
- Framework: Pytest (`test_*.py`, classes `Test*`, functions `test_*`).
- Coverage: maintained via `--cov=src/dbjavagenix` (see `pyproject.toml`).
- Prefer fast, isolated unit tests. Integration/database tests may require a live DB—run selectively: `pytest -k "not database"` or `pytest tests/unit`.

## Commit & PR Guidelines
- Use Conventional Commits. Example: `feat(generator): add MybatisPlus-Mixed controller`.
- Before PR: run `black`, `flake8`, `mypy`, and `pytest`. Ensure descriptions, linked issues, and test evidence (logs/screenshots for CLI) are included.
- Keep changes focused and documented (update `docs/` when behavior or templates change).

## Security & Config Tips
- Copy `config/config.example.yaml` to your local config; never commit secrets or real DB credentials.
- For local dev, Node wrapper sets `PYTHONPATH=src`; ensure Python 3.9+ and Node 14+ are available.

