.PHONY: help install test fmt fmt-check run clean

QUERY ?=

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	uv sync

test: ## Run the full test suite
	uv run pytest -v

fmt: ## Format code with black
	uv run black sherpa tests

fmt-check: ## Check formatting without modifying
	uv run black --check sherpa tests

run: ## Run the agent (usage: make run QUERY="quantum computing")
	uv run python -m sherpa.main "$(QUERY)"

clean: ## Remove build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
