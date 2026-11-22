# Scalene (`scalene-guard`)

Provenance-based DLP tool-call hooks that thwart the MCP triangle of death (untrusted input + sensitive data + external egress in one agent session) using rule-driven access control.

Scalene tracks trust and sensitivity during an AI coding agent session and blocks tool calls outright once the session has touched anything unrecognized, unless the specific destination has been explicitly verified (a real scan) and explicitly cleared (a rule in `scalene_policy.yaml`) — or vetted on the spot in opt-in [OLOY mode](https://github.com/drusifer/Scalene/blob/main/docs/USER_GUIDE.md#oloy-mode-automatic-vetting-no-review-queue).

## Install

Requires Python 3.13+.

```bash
# Core hook (`scalene-guard`) and CLI (`scg`)
pip install scalene-guard

# Include the live approval-queue TUI (`scg monitor`)
pip install "scalene-guard[monitor]"
```

This installs two commands:

- `scalene-guard` — the `PreToolUse`/`PostToolUse` hook invoked automatically by Claude Code (not run by hand in normal use).
- `scg` — the developer-facing CLI (`scg install-hooks`, `scg onboard`, `scg monitor`).

> **Why `scalene-guard` / `scg`?** The `scalene` package name and command already belong to the Python CPU/GPU/memory profiler; using `scalene-guard` and `scg` avoids colliding if both are installed in the same environment.

## Quick start

Wire Scalene into a Claude Code project in one command:

```bash
cd /path/to/your-project
scg install-hooks
```

Then run `scg monitor` in a separate terminal (requires `scalene-guard[monitor]`) to review, verify, and approve or deny blocked calls live — or walk through a 5-minute hands-on demo without touching a real project in [Getting Started](https://github.com/drusifer/Scalene/blob/main/docs/GETTING_STARTED.md).

## Documentation

| Doc | Purpose |
|---|---|
| [Getting Started](https://github.com/drusifer/Scalene/blob/main/docs/GETTING_STARTED.md) | 5-minute walkthrough — watch Scalene block, then explicitly clear, a real tool call |
| [Setup](https://github.com/drusifer/Scalene/blob/main/docs/SETUP.md) | Installation, `.claude/settings.json` hook registration, and state files |
| [User Guide](https://github.com/drusifer/Scalene/blob/main/docs/USER_GUIDE.md) | Full CLI reference, access-control model, OLOY mode, policy config, troubleshooting |
| [Monitor Guide](https://github.com/drusifer/Scalene/blob/main/docs/MONITOR_GUIDE.md) | `scg monitor` interactive TUI walkthrough with screenshots |
| [Architecture](https://github.com/drusifer/Scalene/blob/main/docs/ARCHITECTURE.md) | System architecture, security model, and design decisions |
| [SDLC & Release](https://github.com/drusifer/Scalene/blob/main/docs/SDLC.md) | Toolchain, quality gates, CI, and PyPI Trusted Publishing release process |
| [BRD](https://github.com/drusifer/Scalene/blob/main/docs/BRD.md) / [PRD](https://github.com/drusifer/Scalene/blob/main/docs/PRD.md) / [User Stories](https://github.com/drusifer/Scalene/blob/main/docs/USER_STORIES.md) | Requirements and acceptance criteria |

## Developing on this repo

```bash
make setup       # create .venv, install scalene-guard[monitor,dev], pinned gitleaks, and git hooks
make test        # run the unit test suite
make build       # build sdist + wheel into dist/
make check-dist  # validate metadata (twine check), sdist hygiene, and clean-venv wheel smoke test
```

`make setup` also wires up this repo's tracked git hooks (`.githooks/`, via `core.hooksPath`), including a pre-commit [gitleaks](https://github.com/gitleaks/gitleaks) scan that blocks commits containing secrets. It installs a pinned, checksum-verified gitleaks into `.venv/bin` (`make install-gitleaks`, no `sudo` required). See [docs/SDLC.md](https://github.com/drusifer/Scalene/blob/main/docs/SDLC.md) for all targets, quality gates, and the PyPI release workflow.

## License

[MIT](https://github.com/drusifer/Scalene/blob/main/LICENSE)
