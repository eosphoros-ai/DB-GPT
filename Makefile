.DEFAULT_GOAL := help

SHELL=/bin/bash
VENV = .venv.make

# Detect the operating system and set the virtualenv bin directory
ifeq ($(OS),Windows_NT)
	VENV_BIN=$(VENV)/Scripts
else
	VENV_BIN=$(VENV)/bin
endif

setup: $(VENV)/bin/activate

$(VENV)/bin/activate: $(VENV)/.venv-timestamp

$(VENV)/.venv-timestamp: uv.lock
	# Create new virtual environment if setup.py has changed
	uv venv --python 3.11 $(VENV)
	uv pip install --prefix $(VENV) ruff
	uv pip install --prefix $(VENV) mypy
	uv pip install --prefix $(VENV) pytest
	touch $(VENV)/.venv-timestamp

testenv: $(VENV)/.testenv

$(VENV)/.testenv: $(VENV)/bin/activate
	# check uv version and use appropriate parameters
	if . $(VENV_BIN)/activate && uv sync --help | grep -q -- "--active"; then \
		. $(VENV_BIN)/activate && uv sync --active --all-packages \
			--extra "base" \
			--extra "proxy_openai" \
			--extra "rag" \
			--extra "storage_chromadb" \
			--extra "dbgpts" \
			--link-mode=copy; \
	else \
		. $(VENV_BIN)/activate && uv sync --all-packages \
			--extra "base" \
			--extra "proxy_openai" \
			--extra "rag" \
			--extra "storage_chromadb" \
			--extra "dbgpts" \
			--link-mode=copy; \
	fi
	cp .devcontainer/dbgpt.pth $(VENV)/lib/python3.11/site-packages
	touch $(VENV)/.testenv


.PHONY: fmt
fmt: setup ## Format Python code
	# Format code
	$(VENV_BIN)/ruff format packages
	$(VENV_BIN)/ruff format --exclude="examples/notebook" examples
	$(VENV_BIN)/ruff format i18n
	$(VENV_BIN)/ruff format scripts/update_version_all.py
	$(VENV_BIN)/ruff format install_help.py
	# Sort imports
	$(VENV_BIN)/ruff check --select I --fix packages
	$(VENV_BIN)/ruff check --select I --fix --exclude="examples/notebook" examples
	$(VENV_BIN)/ruff check --select I --fix i18n
	$(VENV_BIN)/ruff check --select I --fix update_version_all.py
	$(VENV_BIN)/ruff check --select I --fix install_help.py

	$(VENV_BIN)/ruff check --fix packages \
		--exclude="packages/dbgpt-serve/src/**"

	$(VENV_BIN)/ruff check --fix packages/dbgpt-serve --ignore F811,F841

	# Not need to check examples/notebook
	#$(VENV_BIN)/ruff check --fix --exclude="examples/notebook" examples

.PHONY: fmt-check
fmt-check: setup ## Check Python code formatting and style without making changes
	$(VENV_BIN)/ruff format --check packages
	$(VENV_BIN)/ruff format --check --exclude="examples/notebook" examples
	$(VENV_BIN)/ruff check --select I packages
	$(VENV_BIN)/ruff check --select I --exclude="examples/notebook" examples
	$(VENV_BIN)/ruff check --fix packages \
		--exclude="packages/dbgpt-serve/src/**"

	$(VENV_BIN)/ruff check --fix packages/dbgpt-serve --ignore F811,F841


.PHONY: pre-commit
pre-commit: fmt-check test test-doc mypy ## Run formatting and unit tests before committing

test: $(VENV)/.testenv ## Run unit tests
	$(VENV_BIN)/pytest --pyargs dbgpt

.PHONY: test-doc
test-doc: $(VENV)/.testenv ## Run doctests
	# -k "not test_" skips tests that are not doctests.
	$(VENV_BIN)/pytest --doctest-modules -k "not test_" packages

.PHONY: mypy
mypy: $(VENV)/.testenv ## Run mypy checks
	# https://github.com/python/mypy
	$(VENV_BIN)/mypy --config-file .mypy.ini --ignore-missing-imports packages/dbgpt-core/
	# $(VENV_BIN)/mypy --config-file .mypy.ini dbgpt/rag/ dbgpt/datasource/ dbgpt/client/ dbgpt/agent/ dbgpt/vis/ dbgpt/experimental/
	# rag depends on core and storage, so we not need to check it again.
	# $(VENV_BIN)/mypy --config-file .mypy.ini dbgpt/storage/
	# $(VENV_BIN)/mypy --config-file .mypy.ini dbgpt/core/
	# TODO: More package checks with mypy.

.PHONY: coverage
coverage: setup ## Run tests and report coverage
	$(VENV_BIN)/pytest --pyargs dbgpt --cov=dbgpt

.PHONY: clean
clean: ## Clean up the environment
	rm -rf $(VENV)
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	# find . -type d -name '.pytest_cache' -delete
	find . -type d -name '.coverage' -delete

.PHONY: clean-dist
clean-dist: ## Clean up the distribution
	rm -rf dist/ *.egg-info build/

.PHONY: build 
build: clean-dist ## Package the project for distribution
	uv build --all-packages
	rm -rf dist/dbgpt_app-*
	rm -rf dist/dbgpt_serve-*

.PHONY: publish
publish: build ## Upload the package to PyPI
	uv publish

.PHONY: publish-test
publish-test: build ## Upload the package to PyPI
	uv publish --index testpypi

.PHONY: help
help:  ## Display this help screen
	@echo "Available commands:"
	@grep -E '^[a-z.A-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' | sort