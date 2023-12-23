.DEFAULT_GOAL := help

SHELL=/bin/bash
VENV = venv

# Detect the operating system and set the virtualenv bin directory
ifeq ($(OS),Windows_NT)
	VENV_BIN=$(VENV)/Scripts
else
	VENV_BIN=$(VENV)/bin
endif

setup: ## Set up the Python development environment
	python3 -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements/dev-requirements.txt
	$(VENV_BIN)/pip install -r requirements/lint-requirements.txt

testenv: setup ## Set up the Python test environment
	$(VENV_BIN)/pip install -e ".[simple_framework]"

.PHONY: fmt
fmt: setup ## Format Python code
	# TODO: Use isort to sort Python imports.
	# https://github.com/PyCQA/isort
	# $(VENV_BIN)/isort .
	# https://github.com/psf/black
	$(VENV_BIN)/black .
	# TODO: Use blackdoc to format Python doctests.
	# https://blackdoc.readthedocs.io/en/latest/
	# $(VENV_BIN)/blackdoc .
	# TODO: Type checking of Python code.
	# https://github.com/python/mypy
	# $(VENV_BIN)/mypy dbgpt
	# TODO: uUse flake8 to enforce Python style guide.
	# https://flake8.pycqa.org/en/latest/
	# $(VENV_BIN)/flake8 dbgpt

.PHONY: pre-commit
pre-commit: fmt test ## Run formatting and unit tests before committing

.PHONY: test
test: testenv ## Run unit tests
	$(VENV_BIN)/pytest dbgpt

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

.PHONY: help
help:  ## Display this help screen
	@echo "Available commands:"
	@grep -E '^[a-z.A-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' | sort
