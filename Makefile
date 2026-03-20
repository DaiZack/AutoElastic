PYTHON = python3

.PHONY: fmt lint typecheck test test-integration ci

# Format source and test files with ruff
fmt:
	$(PYTHON) -m ruff format src tests

# Lint source and test files with ruff
lint:
	$(PYTHON) -m ruff check src tests

# Type-check source with mypy (strict mode configured in pyproject.toml)
typecheck:
	$(PYTHON) -m mypy src

# Run unit tests only (no live Elasticsearch required)
test:
	$(PYTHON) -m pytest tests/unit -v

# Run integration tests only (requires a running Elasticsearch instance)
test-integration:
	$(PYTHON) -m pytest tests/integration -v -m integration

# Full CI pipeline: format → lint → typecheck → unit tests
ci: fmt lint typecheck test
