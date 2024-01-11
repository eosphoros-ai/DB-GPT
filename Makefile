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

$(VENV)/.venv-timestamp: setup.py
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
	$(VENV_BIN)/isort dbgpt/agent/
	$(VENV_BIN)/isort dbgpt/app/
	$(VENV_BIN)/isort dbgpt/cli/
	$(VENV_BIN)/isort dbgpt/configs/
	$(VENV_BIN)/isort dbgpt/core/
	$(VENV_BIN)/isort dbgpt/datasource/
	$(VENV_BIN)/isort dbgpt/model/
	# TODO: $(VENV_BIN)/isort dbgpt/serve
	$(VENV_BIN)/isort dbgpt/serve/core/
	$(VENV_BIN)/isort dbgpt/serve/agent/
	$(VENV_BIN)/isort dbgpt/serve/conversation/
	$(VENV_BIN)/isort dbgpt/serve/utils/_template_files
	$(VENV_BIN)/isort dbgpt/storage/
	$(VENV_BIN)/isort dbgpt/train/
	$(VENV_BIN)/isort dbgpt/util/
	$(VENV_BIN)/isort dbgpt/vis/
	$(VENV_BIN)/isort dbgpt/__init__.py
	$(VENV_BIN)/isort dbgpt/component.py
	$(VENV_BIN)/isort --extend-skip="examples/notebook" examples
	# https://github.com/psf/black
	$(VENV_BIN)/black --extend-exclude="examples/notebook" .
	# TODO: Use blackdoc to format Python doctests.
	# https://blackdoc.readthedocs.io/en/latest/
	# $(VENV_BIN)/blackdoc .
	$(VENV_BIN)/blackdoc dbgpt/agent/
	$(VENV_BIN)/blackdoc dbgpt/app/
	$(VENV_BIN)/blackdoc dbgpt/cli/
	$(VENV_BIN)/blackdoc dbgpt/configs/
	$(VENV_BIN)/blackdoc dbgpt/core/
	$(VENV_BIN)/blackdoc dbgpt/datasource/
	$(VENV_BIN)/blackdoc dbgpt/model/
	$(VENV_BIN)/blackdoc dbgpt/serve/
	# TODO: $(VENV_BIN)/blackdoc dbgpt/storage/
	$(VENV_BIN)/blackdoc dbgpt/train/
	$(VENV_BIN)/blackdoc dbgpt/util/
	$(VENV_BIN)/blackdoc dbgpt/vis/
	$(VENV_BIN)/blackdoc examples
	# TODO: Type checking of Python code.
	# https://github.com/python/mypy
	# $(VENV_BIN)/mypy dbgpt
	# TODO: uUse flake8 to enforce Python style guide.
	# https://flake8.pycqa.org/en/latest/
	# $(VENV_BIN)/flake8 dbgpt

.PHONY: pre-commit
pre-commit: fmt test ## Run formatting and unit tests before committing

test: $(VENV)/.testenv ## Run unit tests
	$(VENV_BIN)/pytest dbgpt

.PHONY: test-doc
test-doc: $(VENV)/.testenv ## Run doctests
	# -k "not test_" skips tests that are not doctests.
	$(VENV_BIN)/pytest --doctest-modules -k "not test_" dbgpt/core

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
