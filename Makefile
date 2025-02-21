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
	#python3 -m venv $(VENV)
	uv venv --python 3.10 $(VENV)
	uv pip install --prefix $(VENV) ruff
	touch $(VENV)/.venv-timestamp

testenv: $(VENV)/.testenv

$(VENV)/.testenv: $(VENV)/bin/activate
	# $(VENV_BIN)/pip install -e ".[framework]"
	# the openai optional dependency is include framework and rag dependencies
	$(VENV_BIN)/pip install -e ".[openai]"
	touch $(VENV)/.testenv


.PHONY: fmt
fmt: setup ## Format Python code
	# Format code
	$(VENV_BIN)/ruff format packages
	$(VENV_BIN)/ruff format --exclude="examples/notebook" examples
	# Sort imports
	$(VENV_BIN)/ruff check --select I --fix packages
	$(VENV_BIN)/ruff check --select I --fix --exclude="examples/notebook" examples

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
	$(VENV_BIN)/pytest dbgpt

.PHONY: test-doc
test-doc: $(VENV)/.testenv ## Run doctests
	# -k "not test_" skips tests that are not doctests.
	$(VENV_BIN)/pytest --doctest-modules -k "not test_" dbgpt/core

.PHONY: mypy
mypy: $(VENV)/.testenv ## Run mypy checks
	# https://github.com/python/mypy
	$(VENV_BIN)/mypy --config-file .mypy.ini dbgpt/rag/ dbgpt/datasource/ dbgpt/client/ dbgpt/agent/ dbgpt/vis/ dbgpt/experimental/
	# rag depends on core and storage, so we not need to check it again.
	# $(VENV_BIN)/mypy --config-file .mypy.ini dbgpt/storage/
	# $(VENV_BIN)/mypy --config-file .mypy.ini dbgpt/core/
	# TODO: More package checks with mypy.

.PHONY: coverage
coverage: setup ## Run tests and report coverage
	$(VENV_BIN)/pytest dbgpt --cov=dbgpt

.PHONY: clean
clean: ## Clean up the environment
	rm -rf $(VENV)
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '.pytest_cache' -delete
	find . -type d -name '.coverage' -delete

.PHONY: clean-dist
clean-dist: ## Clean up the distribution
	rm -rf dist/ *.egg-info build/

.PHONY: package
package: clean-dist ## Package the project for distribution
	IS_DEV_MODE=false python setup.py sdist bdist_wheel

.PHONY: upload
upload: ## Upload the package to PyPI
	# upload to testpypi: twine upload --repository testpypi dist/*
	twine upload dist/*

.PHONY: help
help:  ## Display this help screen
	@echo "Available commands:"
	@grep -E '^[a-z.A-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' | sort