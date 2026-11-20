# Fast-track feature (post-E16): Scanner.match() + Scanner.from_config()

Direct user request, arrived as a design discussion (not a written story) that
converged on two additive architecture changes to `scanner.py`:

## 1. Scanner.match() — pattern matching becomes scanner-owned

**Problem identified by the user**: `resource_verifier._find_matching_rule()`
applied one generic `re.search(rule.pattern, resource.identity)` to every
resource, regardless of which scanner produced it — no awareness of how
`FileScanner` vs. `URLScanner` shape their identity strings. Risk: the two
could drift out of sync (e.g. if a scanner's identity format changed, the
central matcher wouldn't know to adapt).

**Fix**: `Scanner` is now a real base class (was a structural `Protocol` —
`load_scanners()`'s conformance check is still duck-typed `hasattr`, so a
third-party scanner that doesn't inherit from it at all is unaffected) with
a concrete default `match(rule, resource) -> bool` (plain regex, unchanged
behavior). `FileScanner` overrides it; `URLScanner` doesn't (inherits the
default — URL identities aren't path-shaped).

**FileScanner.match()** interprets `rule.pattern` as **gitignore syntax**
(`pathspec.GitIgnoreSpec`, not a bespoke glob) — user's own suggestion,
mid-conversation: familiar syntax, real library, real negation (`!pattern`)
support for free. Compiled specs are `functools.lru_cache`d (hot path: every
`pre_tool_use` call re-checks every rule against every resource). A
directory-wide rule needs **2 lines** (`root` + `root/**`) since plain
gitignore semantics don't match a bare directory via `root/**` alone, only
its contents — this is exactly what the whole feature was for ("match the
whole project folder recursively").

**Blast radius handled**:
- `PolicyRule.pattern` is no longer regex-validated at construction time
  (`policy_config.py`) — its syntax is scanner-owned now, and a real
  gitignore pattern (e.g. a leading `**/`) often isn't valid regex at all
  ("nothing to repeat"). Only `tool` (always regex, every scanner) is still
  validated eagerly.
- Base `Scanner.match()`'s regex path now catches `re.error` and fails safe
  (no match, not a crash) — necessary once `pattern` isn't guaranteed valid
  regex, and this runs on the hot path.
- `write_default_project_policy` (STORY-1504's project-root rule) now
  writes `scanner: "secrets"` explicitly (**reverses** the 2026-07-22
  "no scanner filter needed" decision) — its pattern is gitignore syntax
  now, so without the filter, `_find_matching_rule()` would hand it to
  `URLScanner`'s plain-regex default for an unrelated URL resource, which
  would raise, not just fail to match (`**` isn't valid regex).
- 3 call sites that write a FileScanner-targeted default pattern
  (`onboard.py`, `monitor_app.py`'s Allow form, `policy_config.py`'s project
  default) switched from `re.escape(identity)` to the new
  `scanner.escape_gitignore_literal(identity)` — gitignore has different
  special characters than regex (`*?[]!#`, not `.()+`), so the escaping
  itself had to change, not just the matcher.
- New hard dependency: `pathspec>=0.12` in `pyproject.toml`'s base
  `dependencies` (not an extra like `textual`/monitor) — `FileScanner.match()`
  runs on the hot-path hook adapter unconditionally.

## 2. Scanner.from_config() — config-declared scanners can take settings

**Gap identified by the user**: `load_scanners()` (STORY-1501's config-driven
registry) instantiated every scanner via a bare `cls()` — no way for a
config-declared scanner (the whole motivating case: enterprise CMDB/vuln-DB
scanners) to receive any settings (endpoint URL, credentials path) from
`scalene_policy.yaml`.

**Fix**: `Scanner.from_config(raw_config: dict) -> Scanner` classmethod,
default `return cls()` (every existing scanner needs zero changes).
`load_scanners()` now reads an optional `scanners.extra[].config` sub-block
and calls `cls.from_config(config)` if the class defines it, else falls back
to bare `cls()` (so `DummyScanner`, the test fixture with no `from_config`
at all, keeps working unchanged).

## Tests added
- `tests/test_scanner.py`: `TestScannerBaseMatch`, `TestFileScannerMatch`
  (literal, single-`*` cross-directory recursion, `root`+`root/**` two-line
  convention, sibling-directory boundary safety, real gitignore negation),
  `TestScannerFromConfig`.
- `tests/fixtures_configurable_scanner.py`: new fixture (`ConfigurableScanner`,
  overrides `from_config`) alongside the existing `fixtures_custom_scanner.py`.
- `tests/test_policy_config.py`: rewrote the 2 tests that asserted regex
  semantics on `write_default_project_policy`'s rule (`assertRegex` →
  `FileScanner().match()`), added root-itself + sibling-boundary tests.
- `tests/test_onboard.py`: 2 tests updated for the new escaping (gitignore,
  not regex — a plain path has no gitignore-special chars, so it's unescaped
  now, unlike `re.escape` which backslash-escaped the `.`).

`make test`: 458/458 (446 + 12 new).
