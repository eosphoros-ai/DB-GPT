.DEFAULT_GOAL := help

SHELL=/bin/bash
VENV = venv

# Detect the operating system and set the virtualenv bin directory
ifeq ($(OS),Windows_NT)
	VENV_BIN=$(VENV)/Scripts
else
	VENV_BIN=$(VENV)/bin
endif

setup: $(VENV)/bin/activate

$(VENV)/bin/activate: $(VENV)/.venv-timestamp

$(VENV)/.venv-timestamp: setup.py requirements
	# Create new virtual environment if setup.py has changed
	python3 -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements/dev-requirements.txt
	$(VENV_BIN)/pip install -r requirements/lint-requirements.txt
	touch $(VENV)/.venv-timestamp

testenv: $(VENV)/.testenv

$(VENV)/.testenv: $(VENV)/bin/activate
	# $(VENV_BIN)/pip install -e ".[framework]"
	# $(VENV_BIN)/pip install -e ".[knowledge]"
	# the openai optional dependency is include framework and knowledge dependencies
	$(VENV_BIN)/pip install -e ".[openai]"
	touch $(VENV)/.testenv


.PHONY: fmt
fmt: setup ## Format Python code
	# TODO: Use isort to sort Python imports.
	# https://github.com/PyCQA/isort
	# $(VENV_BIN)/isort .
	$(VENV_BIN)/isort dbgpt/
	$(VENV_BIN)/isort --extend-skip="examples/notebook" examples
	# https://github.com/psf/black
	$(VENV_BIN)/black --extend-exclude="examples/notebook" .
	# TODO: Use blackdoc to format Python doctests.
	# https://blackdoc.readthedocs.io/en/latest/
	# $(VENV_BIN)/blackdoc .
	$(VENV_BIN)/blackdoc dbgpt
	$(VENV_BIN)/blackdoc examples
	# TODO: Use flake8 to enforce Python style guide.
	# https://flake8.pycqa.org/en/latest/
	$(VENV_BIN)/flake8 dbgpt/core/
	$(VENV_BIN)/flake8 dbgpt/rag/
	# TODO: More package checks with flake8.

.PHONY: fmt-check
fmt-check: setup ## Check Python code formatting and style without making changes
	$(VENV_BIN)/isort --check-only dbgpt/
	$(VENV_BIN)/isort --check-only --extend-skip="examples/notebook" examples
	$(VENV_BIN)/black --check --extend-exclude="examples/notebook" .
	$(VENV_BIN)/blackdoc --check dbgpt examples
	$(VENV_BIN)/flake8 dbgpt/core/
	$(VENV_BIN)/flake8 dbgpt/rag/
    # $(VENV_BIN)/blackdoc --check dbgpt examples
    # $(VENV_BIN)/flake8 dbgpt/core/

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
	$(VENV_BIN)/mypy --config-file .mypy.ini dbgpt/core/
	$(VENV_BIN)/mypy --config-file .mypy.ini dbgpt/rag/
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
upload: package ## Upload the package to PyPI
	# upload to testpypi: twine upload --repository testpypi dist/*
	twine upload dist/*

.PHONY: help
help:  ## Display this help screen
	@echo "Available commands:"
	@grep -E '^[a-z.A-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' | sort
