.DEFAULT_GOAL := help

# Scalene project targets. Bob Protocol tooling (chat, tldr, trace-annotate,
# install/update/pull/clean/diff) lives in the `bobp` CLI, not here. Run any
# target through `bobp make <target>` for captured output (build/build.out)
# and a CHAT.md status post, or plain `make <target>` to see output directly.

.PHONY: help setup clean build install-system publish install-hooks install-gitleaks install-scalene-hooks \
	test test-q test-one test-uat screenshots demo via_index

help: ## Show available make targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

setup: ## Create project venv and install dependencies (editable install)
	@python3 -m venv .venv
	@./.venv/bin/pip install -q --upgrade pip
	@./.venv/bin/pip install -q -e ".[monitor,dev]"
	@$(MAKE) --no-print-directory install-gitleaks
	@$(MAKE) --no-print-directory install-hooks
	@echo "venv ready at .venv (make test/run use it automatically)"

clean: ## Remove the venv and packaging artifacts (.venv, dist/, *.egg-info) — leaves build/ alone
	@rm -rf .venv dist src/*.egg-info *.egg-info
	@echo "Removed .venv, dist/, and egg-info."

build: ## Build sdist + wheel into dist/ for distribution (usage: make setup first)
	@if [ ! -x .venv/bin/python ]; then echo "No .venv found — run 'make setup' first" >&2; exit 1; fi
	@.venv/bin/pip install -q build
	@rm -rf dist
	@.venv/bin/python -m build

install-system: ## Install scg/scalene-guard system-wide via pipx, incl. the monitor TUI (usage: make install-system)
	@command -v pipx >/dev/null 2>&1 || { echo "pipx not found — install it first (e.g. 'apt install pipx' or 'python3 -m pip install --user pipx')" >&2; exit 1; }
	@pipx install --force ".[monitor]"

publish: ## Upload dist/* to PyPI (run 'make build' first; needs your own PyPI credentials/token) — interactive, run with plain make
	@if [ ! -d dist ]; then echo "No dist/ found — run 'make build' first" >&2; exit 1; fi
	@.venv/bin/pip install -q twine
	@.venv/bin/python -m twine upload dist/*

install-gitleaks: ## Install a pinned, checksum-verified gitleaks into .venv/bin for the pre-commit secret scan (no sudo; GITLEAKS_VERSION=x.y.z to override)
	@./scripts/install-gitleaks.sh .venv/bin

install-hooks: ## Wire up tracked git hooks (.githooks/), incl. gitleaks pre-commit secret scan
	@chmod +x .githooks/*
	@git config core.hooksPath .githooks
	@if [ -x .venv/bin/gitleaks ] || command -v gitleaks >/dev/null 2>&1; then \
		echo "git hooks installed (core.hooksPath=.githooks); gitleaks found."; \
	else \
		echo "git hooks installed (core.hooksPath=.githooks); WARNING: gitleaks not found — pre-commit secret scan will be skipped until you run 'make install-gitleaks'."; \
	fi

install-scalene-hooks: ## Wire scalene-guard into TARGET's .claude/settings.json PreToolUse/PostToolUse hooks (default TARGET=.)
	@if [ ! -x .venv/bin/scg ]; then echo "No .venv found — run 'make setup' first" >&2; exit 1; fi
	@.venv/bin/scg install-hooks --settings-path "$(or $(TARGET),.)/.claude/settings.json"

test: ## Run unit tests
	@if [ -x .venv/bin/python ]; then .venv/bin/python -m unittest discover -s tests; \
	else echo "No .venv found — run 'make setup' first" >&2; exit 1; fi

test-q: ## Run unit tests with quiet, concise output (E12/STORY-1202) — same suite as 'test', reduces logging/asyncio noise, not perfectly silent
	@if [ -x .venv/bin/python ]; then .venv/bin/python -m unittest discover -s tests -b; \
	else echo "No .venv found — run 'make setup' first" >&2; exit 1; fi

test-one: ## Run one test module only, for validating a focused change (usage: make test-one T=test_oloy)
	@if [ -z "$(T)" ]; then echo "usage: make test-one T=<module, e.g. test_oloy>" >&2; exit 2; fi
	@if [ -x .venv/bin/python ]; then .venv/bin/python -m unittest discover -s tests -p '$(T).py'; \
	else echo "No .venv found — run 'make setup' first" >&2; exit 1; fi

test-uat: ## Run the full suite PLUS the full end-to-end sprint-close journey tests (tests/uat_test_*.py, named so 'test'/'test-q' never collect them for routine dev iteration) -- use for *qa uat / sprint-close sign-off only
	@if [ -x .venv/bin/python ]; then \
		.venv/bin/python -m unittest discover -s tests && \
		.venv/bin/python -m unittest discover -s tests -p 'uat_test*.py'; \
	else echo "No .venv found — run 'make setup' first" >&2; exit 1; fi

screenshots: ## Regenerate scg monitor's real TUI screenshots for docs/MONITOR_GUIDE.md (docs/generate_monitor_screenshots.py)
	@if [ -x .venv/bin/python ]; then .venv/bin/python docs/generate_monitor_screenshots.py; \
	else echo "No .venv found — run 'make setup' first" >&2; exit 1; fi

demo: ## Run the Scalene demo - watch it mask a real exfiltration attempt (STORY-903)
	@if [ -x .venv/bin/python ]; then .venv/bin/python demo/run_demo.py; \
	else echo "No .venv found — run 'make setup' first" >&2; exit 1; fi

via_index: ## Build the via index required by the via MCP server
	@via index "$(CURDIR)"
