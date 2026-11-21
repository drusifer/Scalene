# Smith — User-Oriented Documentation Review (Pre-PyPI Release)

**Date:** 2026-11-21
**Reviewer:** Smith (HCI Expert & UX Advocate)
**Scope:** End-user documentation ahead of publishing `scalene-guard` (`0.1.0`) to PyPI:
- `README.md`
- `docs/GETTING_STARTED.md`
- `docs/SETUP.md`
- `docs/USER_GUIDE.md`
- `docs/MONITOR_GUIDE.md`
- `docs/SDLC.md`

**Method:** Followed every user-facing command and walkthrough verbatim in fresh scratch directories against the freshly built `.venv` binaries (`scalene-guard`, `scg`, `demo/run_demo.py`), verified all `README.md` links against the repository tree, and cross-checked documented behavior against `src/scalene/`.

---

## Verdict

**Needs targeted doc fixes before PyPI launch.**

Tank's new PyPI packaging metadata, `README.md` absolute links, and `docs/SDLC.md` are solid and verified. However, running the existing end-user guides (`GETTING_STARTED.md`, `SETUP.md`, `USER_GUIDE.md`, `MONITOR_GUIDE.md`) cold as a first-time PyPI user surfaced **4 factual contradictions** against the shipped code (accumulated across Sprints 9–13), **3 PyPI-user discoverability/shell hazards**, and **1 CLI help bug** (`scg --help` exits 2).

---

## P0 — Must-Fix Before PyPI Publish (Factual Contradictions)

### 1. `docs/GETTING_STARTED.md` Steps 2–4 do not match actual tool output

- **HEURISTIC:** #1 Visibility of System Status, #2 Match Between System and Real World, #10 Help and Documentation
- **SURFACE:** `docs/GETTING_STARTED.md` lines 23–86
- **COMMAND:** Ran Steps 2, 3, and 4 literally in a clean temp directory (`mktemp -d`).
- **EXPECTED (per doc):**
  - Step 2 (`Read` on `secret.txt`): no policy file exists, file is unrecognized, session tagged `trust: low`.
  - Step 3 (`WebFetch` on `https://example.com`): reason reads `"Blocked: https://example.com has no validated, explicitly-allowed rule, and this session has already touched sensitive/untrusted data (trust=low, sensitivity=public)."`
  - Step 4: `scalene_policy.yaml` contains only the single `example.com` rule.
- **ACTUAL:**
  - Step 2 **auto-creates `scalene_policy.yaml`** with a `project folder default (auto-created)` rule (`sensitivity: internal`, `mode: allow`) covering the working directory (`cli.py:50`). `secret.txt` resolves inside that directory and matches it, so the session is tagged **`trust=high, sensitivity=internal`** — not `trust=low, sensitivity=public`.
  - Step 3 outputs:
    `"Blocked: https://example.com has no explicitly-allowed rule, and this session has already touched sensitive/untrusted data (trust=high, sensitivity=internal). Wait for review, then retry."`
  - Step 4's `scalene_policy.yaml` contains **two** rules (the new `example.com` rule inserted above the auto-created project-folder rule).
- **IMPACT:** A first-time PyPI user following the 5-minute walkthrough immediately gets an unexplained `scalene_policy.yaml`, different session tags, and different block text than the guide shows — eroding confidence in a security tool on minute 1.
- **FIX:** Update Steps 2–4 to explain the auto-created project-folder rule (`sensitivity: internal`), show the real Step 3 JSON response (`trust=high, sensitivity=internal`, `"Wait for review, then retry."`), and show both rules in Step 4's `scalene_policy.yaml`.

### 2. `docs/USER_GUIDE.md` Access-Control Model table contradicts the live `trust=low + sensitivity=restricted` gate

- **HEURISTIC:** #2 Match Between System and Real World, #4 Consistency and Standards, #10 Help and Documentation
- **SURFACE:** `docs/USER_GUIDE.md` lines 108–116 vs. line 140 and `src/scalene/resource_verifier.py:287-300`
- **EXPECTED:** Access-control table accurately states when an `allow` rule is overridden.
- **ACTUAL:** Line 110 claims a clean `mode: allow` match *"Bypasses the block-when-tainted gate below entirely — this is what onboarding + a rule is for."* Twenty lines later, line 140 (in the OLOY table) states *"Session is `trust: low` + `sensitivity: restricted` → Blocked"*. In live code (`resource_verifier.py:287-298`), labeled `mode: allow` matches escalate tags first and **still block** if the session reaches `trust=low` AND `sensitivity=restricted` (the 2026-08-07 `decide_access()` correction).
- **IMPACT:** Users reading the core access-control model get an outdated security guarantee that contradicts both the code and the OLOY table right below it.
- **FIX:** Update rows 1–2 of the access-control table to explain tag escalation followed by the `trust=low` + `sensitivity=restricted` block gate (and note that `med`/`internal` are valid labels that do not trip this binary gate on their own). Also document the optional `trust:` rule field and the auto-created project-folder rule.

### 3. `docs/MONITOR_GUIDE.md` and `docs/USER_GUIDE.md` falsely claim `scg monitor` "Takes no flags" and disagree on queue order

- **HEURISTIC:** #4 Consistency and Standards, #6 Recognition Rather Than Recall, #10 Help and Documentation
- **SURFACE:** `docs/MONITOR_GUIDE.md:19`, `docs/USER_GUIDE.md:95`
- **COMMAND:** `scg monitor --help`
- **EXPECTED (per both docs):** `scg monitor` takes no flags; `USER_GUIDE.md:95` says queue is *"oldest first"*, `MONITOR_GUIDE.md:35` says *"most-recent-first"*.
- **ACTUAL:** `scg monitor --help` exits 0 and documents 4 real flags: `--policy-path`, `--cache-path`, `--state-dir`, `--audit-log-path` (`src/scalene/monitor.py:35-38`). Queue ordering in `src/scalene/monitor_app.py:1267` is **most-recent-first** (`reverse=True`).
- **IMPACT:** Users running `scg monitor` from a different terminal working directory think there is no way to point it at a project's `.scalene/` or `scalene_policy.yaml`, and `USER_GUIDE.md` gives the wrong queue sort order.
- **FIX:** Document `scg monitor`'s 4 path flags in both `MONITOR_GUIDE.md` and `USER_GUIDE.md` (with a one-line tip on avoiding cwd mismatch), change `USER_GUIDE.md:95` from "oldest first" to "most-recent-first", and note the E19 OLOY session-line summary in `MONITOR_GUIDE.md`.

### 4. `docs/SETUP.md` is stale in 3 user-visible areas

- **HEURISTIC:** #1 Visibility of System Status, #10 Help and Documentation
- **SURFACE:** `docs/SETUP.md` lines 12, 47, 65
- **ACTUAL:**
  - Line 12 lists `scg` subcommands as `(`onboard`, `install-hooks`)` — omits `monitor` and doesn't mention `pip install "scalene-guard[monitor]"`.
  - Line 47 says *"If the file is missing, Scalene falls back to fail-safe defaults (`sensitive_by_default: true`, `untrusted_by_default: true`)"* — stale since Sprint 9 (`cli.py:50` auto-creates `scalene_policy.yaml` with the project-folder default rule; fail-safe fallback only applies when creation/load fails) — and links to internal `docs/ARCHITECTURE.md §13` instead of `docs/USER_GUIDE.md`.
  - Line 65 says *"there is no CI workflow in this repo that captures build artifacts, so no further exclusion is needed there."* — now factually wrong (`.github/workflows/ci.yml` + `publish.yml` exist) and irrelevant repo-internal phrasing for a PyPI user.
- **FIX:** Add `monitor` + `"scalene-guard[monitor]"` install note, describe the auto-created `scalene_policy.yaml` behavior, link to `USER_GUIDE.md` and `MONITOR_GUIDE.md`, and rewrite the `.scalene/` section for end users (add `.scalene/` to your project's `.gitignore`).

---

## P1 — Should-Fix for First-Time PyPI Users (Discoverability & Shell Ergonomics)

### 5. `SCALENE_URLHAUS_AUTH_KEY` and built-in restricted paths (`/etc`, `~/.ssh`) are invisible to PyPI users

- **HEURISTIC:** #6 Recognition Rather Than Recall, #10 Help and Documentation
- **SURFACE:** All user docs (`README.md`, `SETUP.md`, `GETTING_STARTED.md`, `USER_GUIDE.md`)
- **ACTUAL:** `SCALENE_URLHAUS_AUTH_KEY` (optional free URLhaus/abuse.ch external URL malware reputation check) is only documented in `.env.example`, which is **not shipped** in the PyPI wheel or sdist. Similarly, `FileScanner`'s hardcoded restricted-path floor (`/etc`, `~/.ssh`) is never mentioned in `USER_GUIDE.md`.
- **IMPACT:** PyPI users have no way to discover external URL reputation checking or understand why `/etc` / `~/.ssh` paths are always restricted.
- **FIX:** Add a short **Environment variables** section to `docs/USER_GUIDE.md` covering `SCALENE_OLOY` and `SCALENE_URLHAUS_AUTH_KEY` (with the `https://auth.abuse.ch/` signup link and clean fallback behavior), and add a one-line note on `/etc` and `~/.ssh` in Resource Verification.

### 6. Unquoted extras (`pip install scalene-guard[monitor]`) fail in `zsh`

- **HEURISTIC:** #5 Error Prevention
- **SURFACE:** `docs/MONITOR_GUIDE.md:15`, `docs/USER_GUIDE.md:95` (and runtime error string in `src/scalene/monitor.py:45`)
- **ACTUAL:** Unquoted `[monitor]` triggers `zsh: no matches found` on macOS (and any zsh shell). `README.md` already quotes it (`pip install "scalene-guard[monitor]"`), but the guides do not.
- **FIX:** Quote `"scalene-guard[monitor]"` consistently in `MONITOR_GUIDE.md` and `USER_GUIDE.md` (and note `monitor.py:45` for Neo).

### 7. Minor PyPI landing-page & walkthrough polish

- **HEURISTIC:** #2 Match Between System and Real World, #10 Help and Documentation
- **SURFACE:** `README.md:3`, `docs/GETTING_STARTED.md:105-107`, `docs/MONITOR_GUIDE.md:126`
- **DETAILS:**
  - `README.md:3`: *"MCP triangle of death"* is domain jargon for first-time PyPI visitors — add a brief parenthetical gloss: *(untrusted input + sensitive data + external egress in one agent session)*.
  - `docs/GETTING_STARTED.md:107`: recommends `make demo` without noting it requires a git clone of the repo (not available from `pip install scalene-guard`); lines 105–106 use inline code paths instead of clickable markdown links.
  - `docs/MONITOR_GUIDE.md:162-165`: when editing a rule in `RulesScreen`, the UI shows `public`/`restricted` and `high`/`low` (preserving backlogged `internal`/`med` values unless changed) — worth a one-sentence note so users editing the auto-created `internal` rule aren't puzzled when neither sensitivity radio button starts selected.

---

## P2 — CLI UX Defect Found During Doc Verification (Code, Not Docs — Route to Trin/Neo)

### 8. `scg --help` and `scg -h` fail with exit code 2

- **HEURISTIC:** #4 Consistency and Standards, #10 Help and Documentation
- **COMMAND:** `scg --help`
- **EXPECTED:** Prints subcommand usage/descriptions to stdout and exits `0` (matching `scalene-guard --help`, `scg onboard --help`, `scg install-hooks --help`, `scg monitor --help`).
- **ACTUAL:** Prints `usage: scg <onboard|install-hooks|monitor> ...` to stderr and exits **`2`** (`src/scalene/main_cli.py:16-18`).
- **IMPACT:** The single most common command a new PyPI user runs right after `pip install scalene-guard` fails as a CLI error and gives no one-line descriptions of `onboard`, `install-hooks`, or `monitor`.
- **FIX:** Route via Trin/Neo to handle `-h`/`--help` (or use `argparse` with subcommand help descriptions) returning exit `0`.

---

## Verified Good (No Action Needed)

- `README.md`: All 13 absolute GitHub URLs resolve to real files in the repo; PyPI `twine check --strict` passes cleanly; install snippet clearly separates core vs. `[monitor]`.
- `docs/SDLC.md`: Complete, accurate against live `Makefile` and `.github/workflows/`, clean PyPI Trusted Publisher instructions for `drew.gs.works`.
- `docs/USER_GUIDE.md`: `scg onboard --help` and `scalene-guard --help` blocks match live `--help` output verbatim; OLOY mode section matches live E19 implementation.
- `demo/run_demo.py`: Runs cleanly end-to-end against real binaries.
