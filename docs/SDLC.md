# Scalene — SDLC

How this project is built, tested, changed, and released — the source of truth for change management across the whole project. **Owned by Tank**; to change anything here, ask `@Tank *devops sdlc <what and why>` — the mechanism and this document change together.

## 1. Toolchain

| | Python |
|---|---|
| Runtime version | Python 3.13+ (tested on 3.13 and 3.15) — pinned in `pyproject.toml` (`requires-python = ">=3.13"`) |
| Manifest | `pyproject.toml` (PEP 621, `setuptools>=77` build backend, `MANIFEST.in` for sdist scoping) |
| Lockfile | None — project uses stdlib `venv` + `pip` editable installs rather than a locked manager (see Known deviations) |
| Package manager | `pip` inside `.venv/` |
| Local environment | `.venv/` (gitignored) |

Other required tools:
- `gitleaks` (v8.30.1, checksum-verified) — secret scanning in pre-commit and CI — installed into `.venv/bin/gitleaks` by `make install-gitleaks` (`scripts/install-gitleaks.sh`, no `sudo`).
- `pipx` (optional) — only required for `make install-system`.

## 2. Setup

From a clean checkout:

```sh
make setup
make test
```

Prerequisites not installed by `make setup`: `python3` (>= 3.13 with `venv` module), `git`, `curl`, and `sha256sum`/`shasum` (for `make install-gitleaks`).

## 3. Make targets

The Makefile is the contributor entry point; recipes call native tools inside `.venv/`. Agents run these targets through `bobp make <target>`.

| Target | Runs | Notes |
|---|---|---|
| `install` | creates `.venv` if absent; `pip install -e ".[monitor,dev]"` | idempotent; installs runtime, TUI, build, and dev tools |
| `setup` | `install` + `install-gitleaks` + `install-hooks` | full contributor setup |
| `test` | `.venv/bin/python -m unittest discover -s tests` | full unit test suite |
| `test-q` | `.venv/bin/python -m unittest discover -s tests -b` | buffered output; used by CI and routine runs |
| `test-one` | `unittest discover -s tests -p '$(T).py'` | single test module (`T=test_oloy`) |
| `test-uat` | full unit tests + `tests/uat_test*.py` | sprint-close UAT sign-off only |
| `build` | `.venv/bin/python -m build` | builds sdist + wheel into `dist/` |
| `check-dist` | `twine check --strict dist/*`, sdist hygiene check, clean-venv wheel smoke test | run before tagging/releasing and in CI |
| `release-check` | compares `TAG=vX.Y.Z` against `pyproject.toml` `[project].version` | run by `publish.yml` before upload |
| `secrets` | `gitleaks detect --source . --redact` | full git-history secret scan |
| `install-gitleaks` | `./scripts/install-gitleaks.sh .venv/bin` | pinned, checksum-verified gitleaks |
| `install-hooks` | sets `git config core.hooksPath .githooks` | wires pre-commit gitleaks scan |
| `install-scalene-hooks` | `.venv/bin/scg install-hooks --settings-path <TARGET>/.claude/settings.json` | dogfood hook wiring |
| `install-system` | `pipx install --force ".[monitor]"` | optional user-level install |
| `publish` | `.venv/bin/python -m twine upload dist/*` | manual interactive fallback only; official releases use OIDC |
| `screenshots` | `.venv/bin/python docs/generate_monitor_screenshots.py` | regenerates real SVG screenshots for `docs/MONITOR_GUIDE.md` |
| `demo` | `.venv/bin/python demo/run_demo.py` | runs end-to-end masking/blocking demo |
| `via_index` | `via index "$(CURDIR)"` | rebuilds `.via/index.db` |
| `clean` | removes `dist/`, `*.egg-info`, `src/*.egg-info` | keeps `.venv/` and `build/` |
| `distclean` | `clean` + removes `.venv/` | used for from-clean verification |
| `help` | lists targets with descriptions | default goal |

Standard targets deliberately absent:
- `lint` / `format` — no formatter or linter is configured in `pyproject.toml` yet; adding one is a mechanism change.
- `run` — the package exposes two distinct CLI binaries (`scalene-guard` hook on stdin and `scg` operator CLI); invoke them via `.venv/bin/scg` or `make demo`.

## 4. Dependencies

- **Add:** edit `[project].dependencies` in `pyproject.toml` (or `[project.optional-dependencies]` for `monitor` / `dev`), then run `make install`. Keep hot-path hook dependencies minimal — TUI/dev packages must not enter hard `dependencies`.
- **Upgrade / remove:** edit `pyproject.toml`, run `make distclean && make install && make test`.
- **Dev-only tools:** `[project.optional-dependencies].dev` (`build`, `jinja2`, `twine`).
- **Commit afterwards:** `pyproject.toml` (and `MANIFEST.in` if packaging layout changed).
- **Who:** Neo adds and bumps dependencies. Changing the package manager, build backend, or minimum Python version is a mechanism change — Tank's.

## 5. Quality gates

| Gate | Target | Required before |
|---|---|---|
| Unit tests | `make test-q` (or `make test`) | every handoff to Trin; PR merge; release |
| End-to-end UAT | `make test-uat` | sprint close |
| Secret scan (staged) | `.githooks/pre-commit` (`gitleaks git --staged`) | every commit |
| Secret scan (history) | `make secrets` | PR merge; release |
| Package check | `make build && make check-dist` | packaging changes; release |

## 6. Change management

This document is the project's source of truth for how a change gets from request to done. Where another document, skill, or habit disagrees with it, this one wins — and the disagreement is reported to Tank so one of them gets fixed.

### Change classes

| Class | Examples | Proposed by | Approved by | Must pass | Recorded in |
|---|---|---|---|---|---|
| Routine | feature, fix, refactor, docs, adding a dependency via section 4 | Cypher story or user request | Trin UAT + Morpheus review (+ Smith gate for UX/docs) | `make test-q`, pre-commit gitleaks | `task.md`, `agents/CHAT.md`, git commit |
| Mechanism | toolchain, manifest layout, `Makefile` targets, gates, CI, this document | anyone, via `@Tank *devops sdlc` | Tank + user | `make distclean && make setup && make test-q && make build && make check-dist && make secrets` | `docs/SDLC.md`, `agents/CHAT.md` |
| Release / deploy | version bump, tag `vX.Y.Z`, GitHub Release → PyPI publish | user (or Tank prep) | user (manual GitHub Release + `pypi` environment approval) | CI (`test` matrix + `package` + `secrets`) + `release-check` | git tag `vX.Y.Z`, GitHub Release, PyPI |
| Emergency | hotfix outside a sprint | user or Neo | user (may be post-facto) | `make test-q` + `make secrets` at minimum | `agents/CHAT.md`, reviewed at next sprint close |

### Flow

1. **Request** — user request or Cypher story in `docs/USER_STORIES.md`, sized into `task.md`.
2. **Branch** — work happens on `main` (or a short-lived feature branch merged via PR).
3. **Implement** — through `make` targets (`bobp make <target>` for agents); tests accompany behavior changes.
4. **Gate** — section 5 gates pass locally before handoff.
5. **Review** — Trin validates tests/ACs, Morpheus reviews architecture/code, Smith reviews UX/docs where applicable, Tank reviews infra/CI/SDLC.
6. **Integrate** — user approves commits, pushes, and tags.
7. **Record** — `task.md`, `agents/CHAT.md`, relevant `docs/*.md`, and persona state files are updated.

### Rules

- Agents commit, push, or tag only when the user asks.
- Never commit secrets, `.env`, `.venv/`, `.scalene/`, `dist/`, or `build/`.
- **Rollback:** revert the offending commit on `main`. For a bad PyPI release, yank the version on PyPI (PyPI forbids re-uploading the same version) and publish a patch version (`0.1.x`).
- **Changing this document:** only Tank edits `docs/SDLC.md`; every edit updates the Last verified line.

## 7. Versioning and release

- **Package name on PyPI:** `scalene-guard` (console scripts: `scalene-guard`, `scg`).
- **Version lives in:** `pyproject.toml` (`[project].version`, semantic versioning).
- **Bumped:** before cutting a release, by updating `[project].version` on `main`.
- **Artifact:** `make build` produces `dist/scalene_guard-<version>.tar.gz` (sdist) and `dist/scalene_guard-<version>-py3-none-any.whl` (wheel), verified by `make check-dist`.
- **Release procedure:**
  1. Bump `version` in `pyproject.toml`, ensure `README.md` and docs are current, and run `make build && make check-dist && make secrets`.
  2. Commit and push to `main`; wait for `.github/workflows/ci.yml` to go green.
  3. Create and push the matching tag `v<version>` (e.g. `git tag -a v0.1.0 -m "Release v0.1.0" && git push origin v0.1.0`) and publish a GitHub Release for that tag.
  4. Publishing the GitHub Release triggers `.github/workflows/publish.yml`, which re-runs CI, verifies `make release-check`, builds `dist/`, and publishes to PyPI via OIDC Trusted Publishing after the `pypi` environment approval gate.

### One-time PyPI Trusted Publisher setup (`drew.gs.works`)

No PyPI API token is stored in GitHub Secrets. Before the first release:

1. **PyPI (`drew.gs.works` account):** Go to `https://pypi.org/manage/account/publishing/` → **Add a new pending publisher** (or project-level publisher after first upload):
   - **PyPI Project Name:** `scalene-guard`
   - **Owner:** `drusifer`
   - **Repository name:** `Scalene`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
2. **GitHub (`drusifer/Scalene`):** Go to **Settings → Environments → New environment**:
   - Name: `pypi`
   - Enable **Required reviewers** (add `drusifer`) so every publish requires explicit approval.
   - Optionally restrict deployment branches/tags to `v*` tags.

## 8. CI / deploy

Configured in `.github/workflows/` (all actions pinned to full commit SHAs; kept current weekly by `.github/dependabot.yml`):

- **`.github/workflows/ci.yml`** — runs on pushes to `main`, pull requests, and via `workflow_call` from `publish.yml`:
  - `test`: Python `3.13` and `3.15` matrix running `make install && make test-q`.
  - `package`: Python `3.13` running `make install && make build && make check-dist`.
  - `secrets`: full git history (`fetch-depth: 0`) running `make install-gitleaks && make secrets`.
- **`.github/workflows/publish.yml`** — runs on GitHub Release `published`:
  - Calls `ci.yml` (`verify` job).
  - Verifies `make release-check TAG="${{ github.ref_name }}"`, builds and validates `dist/` on Python `3.13`.
  - Publishes `dist/` to PyPI using `pypa/gh-action-pypi-publish` with `id-token: write` inside the `pypi` GitHub Environment.

## 9. Known deviations

- **No lockfile / stdlib `venv` + `pip` instead of `uv`:** Scalene predates the `uv` default in `build-env/SKILL.md` and established `.venv` + `pip` in `Makefile`. Preserved per Principle 1 ("Detect before you create"); migrating to `uv` + `uv.lock` is a separate user decision.
- **No `lint` or `format` targets:** No static linter (`ruff`) is adopted yet; tests (`unittest`) and secret scanning (`gitleaks`) are the active gates.

## 10. Conformance check

Run by Tank at sprint close (`*devops sdlc-check`):

1. `make distclean && make setup && make test-q && make build && make check-dist && make secrets` passes from clean.
2. Every third-party import under `src/scalene/` is declared in `pyproject.toml` (`dependencies` or `[monitor]`), and no declared runtime dependency is unused.
3. Every target in section 3 exists in `Makefile` and matches its documented behavior; no undocumented targets exist.
4. No doc or script instructs contributors to bypass `make` or install project dev deps outside `.venv/`.
5. `requires-python`, `.gitignore` (`.venv/`, `.scalene/`, `dist/`, `build/`), and `MANIFEST.in` exclusions match section 1 & 7.
6. Changes followed section 6 (right class, approval, recorded in `task.md`/`agents/CHAT.md`).
7. All actions in `.github/workflows/*.yml` remain pinned to full commit SHAs with least-privilege `permissions`.

---
*Last verified: 2026-11-22 against Python 3.13+ policy update (post-d94f054) by Tank.*
