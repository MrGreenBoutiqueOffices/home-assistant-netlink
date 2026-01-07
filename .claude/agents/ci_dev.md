# ci_dev agent

Focus: developer workflow + CI parity.

## Commands (match CI)
- Install deps: `uv sync --frozen --dev`
- Lint: `uv run ruff check .`
- Format check: `uv run ruff format --check .`
- Pre-commit (repo-configured): `pre-commit run -a`

## CI workflows
- Ruff: `.github/workflows/linting.yaml`
- Hassfest: `.github/workflows/hassfest.yaml`
- HACS: `.github/workflows/hacs.yaml`

## Repo notes
- `tests/` is currently empty; don’t invent a test framework unless requested.
