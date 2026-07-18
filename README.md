# Scalene

Tool call hooks that thwart the MCP triangle of death using rule-driven access control.

Scalene tracks trust and sensitivity during an agent session and blocks a tool call outright once the session has touched anything unrecognized, unless the specific destination has been explicitly verified (a real scan) and explicitly cleared (a hand-authored rule). Nothing is trusted by default; trust decisions are always explicit and validated, never automatic.

## Documentation

| Doc | Purpose |
|---|---|
| [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) | Clean-clone walkthrough — see Scalene block, then explicitly clear, a real call in under 5 minutes |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Full CLI reference, policy config, onboarding workflow, troubleshooting |
| [docs/BRD.md](docs/BRD.md) | Business requirements (source of truth for scope) |
| [docs/PRD.md](docs/PRD.md) | Product requirements |
| [docs/USER_STORIES.md](docs/USER_STORIES.md) | User stories + acceptance criteria |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, class/sequence diagrams |
| [docs/SETUP.md](docs/SETUP.md) | Install + `.claude/settings.json` hook registration |
| [docs/STORY_TRACEABILITY.md](docs/STORY_TRACEABILITY.md) | AC-to-test traceability (Sprint 1 close) |
| [docs/URL_MALWARE_CHECKING.md](docs/URL_MALWARE_CHECKING.md) | Research notes: URL/malware reputation API options |
| [task.md](task.md) | Sprint task board (current status) |

## Getting started

New to Scalene? Start with [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) — a clean-clone walkthrough that ends with you watching a real call get blocked, then explicitly cleared.

Working on this repo itself:

```bash
make setup   # create venv, install scalene-guard + dev dependencies, install git hooks
make test    # run the test suite
```

`make setup` also wires up this repo's tracked git hooks (`.githooks/`, via `core.hooksPath`), including a pre-commit [gitleaks](https://github.com/gitleaks/gitleaks) scan that blocks commits containing secrets. Install `gitleaks` (e.g. `apt install gitleaks`) for it to take effect — if it's missing, the hook warns and allows the commit rather than blocking all commits repo-wide.

See [docs/SETUP.md](docs/SETUP.md) for hook registration and onboarding CLI usage.

## Project coordination

This repo uses [Bob Protocol](agents/DOCUMENTATION_INDEX.md) for multi-persona AI coordination (Neo, Trin, Morpheus, Mouse, Cypher, Oracle, Smith, Bob). See `agents/DOCUMENTATION_INDEX.md` for the full persona/tooling index and `agents/CHAT.md` for the team communication log.
