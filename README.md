# Scalene

Tool call hooks that thwart the MCP triangle of death using provenance-based context labeling.

Scalene is a provenance-based DLP layer for AI coding agents. It tracks where data came from during an agent session and structurally masks payloads before tainted-sensitive data would flow to an untrusted destination — without blocking the agent's workflow.

## Documentation

| Doc | Purpose |
|---|---|
| [docs/BRD.md](docs/BRD.md) | Business requirements (source of truth for scope) |
| [docs/PRD.md](docs/PRD.md) | Product requirements |
| [docs/USER_STORIES.md](docs/USER_STORIES.md) | User stories + acceptance criteria (9 stories) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, class/sequence diagrams |
| [docs/SETUP.md](docs/SETUP.md) | Install + `.claude/settings.json` hook registration |
| [docs/STORY_TRACEABILITY.md](docs/STORY_TRACEABILITY.md) | AC-to-test traceability (Sprint 1 close) |
| [docs/URL_MALWARE_CHECKING.md](docs/URL_MALWARE_CHECKING.md) | Research notes: URL/malware reputation API options |
| [task.md](task.md) | Sprint task board (current status) |

## Getting started

```bash
make setup   # create venv, install scalene-guard + dev dependencies, install git hooks
make test    # run the test suite
```

`make setup` also wires up this repo's tracked git hooks (`.githooks/`, via `core.hooksPath`), including a pre-commit [gitleaks](https://github.com/gitleaks/gitleaks) scan that blocks commits containing secrets. Install `gitleaks` (e.g. `apt install gitleaks`) for it to take effect — if it's missing, the hook warns and allows the commit rather than blocking all commits repo-wide.

See [docs/SETUP.md](docs/SETUP.md) for hook registration and onboarding CLI usage.

## Project coordination

This repo uses [Bob Protocol](agents/DOCUMENTATION_INDEX.md) for multi-persona AI coordination (Neo, Trin, Morpheus, Mouse, Cypher, Oracle, Smith, Bob). See `agents/DOCUMENTATION_INDEX.md` for the full persona/tooling index and `agents/CHAT.md` for the team communication log.
