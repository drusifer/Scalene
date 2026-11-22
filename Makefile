.DEFAULT_GOAL := help

# Scalene project targets. Bob Protocol tooling (chat, tldr, trace-annotate,
# install/update/pull/clean/diff) lives in the `bobp` CLI, not here. Run any
# target through `bobp make <target>` for captured output (build/build.out)
# and a CHAT.md status post, or plain `make <target>` to see output directly.

.PHONY: help install setup clean distclean build check-dist release-check publish \
	install-system install-hooks install-gitleaks install-scalene-hooks secrets \
	test test-q test-one test-uat screenshots demo via_index

help: ## Show available make targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

install: ## Create .venv (if absent) and install scalene-guard + [monitor,dev] extras (idempotent)
	@if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
	@./.venv/bin/pip install -q --upgrade pip
	@./.venv/bin/pip install -q -e ".[monitor,dev]"

setup: install install-gitleaks install-hooks ## Full local contributor setup: venv, deps, pinned gitleaks, and git hooks
	@echo "venv ready at .venv (make test/run use it automatically)"

clean: ## Remove packaging artifacts (dist/, *.egg-info) — leaves .venv and build/ alone
	@rm -rf dist src/*.egg-info *.egg-info
	@echo "Removed dist/ and egg-info."

distclean: clean ## Remove packaging artifacts AND the local .venv
	@rm -rf .venv
	@echo "Removed .venv."

build: ## Build sdist + wheel into dist/ for distribution (run 'make install' first)
	@if [ ! -x .venv/bin/python ]; then echo "No .venv found — run 'make install' first" >&2; exit 1; fi
	@rm -rf dist
	@.venv/bin/python -m build

check-dist: ## Validate dist/* metadata with twine, check sdist hygiene, and smoke-test the wheel in a clean venv
	@if [ ! -d dist ]; then echo "No dist/ found — run 'make build' first" >&2; exit 1; fi
	@if [ ! -x .venv/bin/python ]; then echo "No .venv found — run 'make install' first" >&2; exit 1; fi
	@.venv/bin/python -m twine check --strict dist/*
	@.venv/bin/python -c 'import glob, sys, tarfile; \
		sdists = glob.glob("dist/*.tar.gz"); \
		assert len(sdists) == 1, f"expected 1 sdist, got {sdists}"; \
		bad = [m for m in tarfile.open(sdists[0]).getnames() if "/.scalene" in m or "/agents/" in m or "/.venv" in m]; \
		assert not bad, f"unwanted files in sdist: {bad}"; \
		print(f"sdist hygiene OK ({sdists[0]})")'
	@tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
		python3 -m venv "$$tmp/venv" && \
		"$$tmp/venv/bin/pip" install -q dist/*.whl && \
		"$$tmp/venv/bin/scalene-guard" --help >/dev/null && \
		"$$tmp/venv/bin/scg" --help >/dev/null && \
		"$$tmp/venv/bin/scg" onboard --help >/dev/null && \
		"$$tmp/venv/bin/scg" install-hooks --help >/dev/null && \
		"$$tmp/venv/bin/scg" monitor --help >/dev/null && \
		(cd "$$tmp" && echo '{"hook_event_name":"PreToolUse","session_id":"smoke","tool_name":"Read","tool_input":{"file_path":"README.md"}}' | "$$tmp/venv/bin/scalene-guard" | grep -q '"permissionDecision": "allow"') && \
		echo "wheel smoke test OK (scalene-guard + scg)"

release-check: ## Verify TAG (e.g. TAG=v0.1.0) matches [project].version in pyproject.toml
	@if [ -z "$(TAG)" ]; then echo "usage: make release-check TAG=vX.Y.Z" >&2; exit 2; fi
	@python3 -c 'import sys, tomllib; \
		ver = tomllib.load(open("pyproject.toml", "rb"))["project"]["version"]; \
		tag = sys.argv[1]; \
		expected = f"v{ver}"; \
		assert tag == expected, f"Tag {tag!r} does not match pyproject.toml version {ver!r} (expected {expected!r})"; \
		print(f"Tag {tag} matches pyproject.toml version {ver}")' "$(TAG)"

install-system: ## Install scg/scalene-guard system-wide via pipx, incl. the monitor TUI (usage: make install-system)
	@command -v pipx >/dev/null 2>&1 || { echo "pipx not found — install it first (e.g. 'apt install pipx' or 'python3 -m pip install --user pipx')" >&2; exit 1; }
	@pipx install --force ".[monitor]"

publish: ## Manual fallback: upload dist/* to PyPI interactively (official releases publish via v* tag push OIDC)
	@if [ ! -d dist ]; then echo "No dist/ found — run 'make build' first" >&2; exit 1; fi
	@if [ ! -x .venv/bin/python ]; then echo "No .venv found — run 'make install' first" >&2; exit 1; fi
	@.venv/bin/python -m twine upload dist/*

secrets: ## Scan git history for leaked secrets using gitleaks (git-aware; requires make install-gitleaks)
	@if [ -x .venv/bin/gitleaks ]; then gl=".venv/bin/gitleaks"; \
	elif command -v gitleaks >/dev/null 2>&1; then gl="$$(command -v gitleaks)"; \
	else echo "gitleaks not found — run 'make install-gitleaks' first" >&2; exit 1; fi; \
	"$$gl" detect --source . --redact

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
