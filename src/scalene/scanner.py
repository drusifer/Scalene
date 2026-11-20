"""Scanner protocol + registry (STORY-1001, STORY-1002).

docs/ARCHITECTURE.md sec13.2: replaces the old PolicyRule/allowlist matching
model (sec13.1) -- each scanner owns its own resource-detection logic (no
user-authored jsonpath/pattern), and scan() reuses today's
secrets_scan.py/LocalHeuristicChecker unchanged via the existing isolated
subprocess boundary (subprocess_isolation.run_scanner, STORY-601), so scan
results stay at parity with pre-Sprint-4 behavior.

Bash's `command` string gets no dedicated scanner type (sec13.2 decision) --
it's simply one more string value that both FileScanner's and URLScanner's
generic fallback regexes look at, same as any other tool's args.

2026-07-22 (docs/ARCHITECTURE.md sec19, direct user session): URLScanner
recognizes any URI scheme (ftp://, ws://, s3://, ...), not just http(s) --
with one deliberate exception, file://, which is a filesystem reference
wearing a URI shape and is FileScanner's resource instead. Neither scanner
requires a caller to know which one applies to a given string; both run
their generic fallback over every tool's args unconditionally.
"""

from __future__ import annotations

import functools
import importlib
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pathspec

from .subprocess_isolation import run_scanner

if TYPE_CHECKING:
    # Deferred: policy_config.py imports SCANNERS/Scanner/etc. from this
    # module, so a real top-level `from .policy_config import PolicyRule`
    # here would be circular. Only needed for Scanner.match()'s type hint --
    # `from __future__ import annotations` (above) already makes annotations
    # lazy strings, so this is resolved for type checkers only, never at
    # runtime.
    from .policy_config import PolicyRule

# Per-tool field that carries a file path directly, as opposed to a value
# that merely might contain one (STORY-1002: known fields first, generic
# fallback for everything else).
_FILE_PATH_FIELDS = {
    "Read": "file_path",
    "Write": "file_path",
    "Edit": "file_path",
}

# Per-tool field that carries a URL directly.
_URL_FIELDS = {
    "WebFetch": "url",
}


def locator_fields(tool_name: str) -> frozenset[str]:
    """docs/ARCHITECTURE.md sec24.3: the argument field(s) a tool's schema
    uses to *name* its target resource (`file_path`, `url`) -- the same
    per-tool tables identify() reads. OLOY's auto-mask never masks these:
    replacing a path/URL breaks the call, and that resource was already
    vetted by auto-review."""
    return frozenset(f for f in (_FILE_PATH_FIELDS.get(tool_name), _URL_FIELDS.get(tool_name)) if f)


# Conservative on purpose: only path-shaped tokens match, so ordinary words
# in a Bash command (e.g. "echo hello world") don't produce false-positive
# file resources. 3 shapes, each requiring a `/` before any path characters
# so a bare "~" or "$VAR" mid-sentence (no clear path continuation) still
# doesn't match:
#   - `/...`, `./...`, `../...`      -- the original, explicit-prefix form
#   - `~/...`, `~user/...`           -- shell home-dir shorthand
#   - `$VAR/...`, `${VAR}/...`       -- an embedded environment variable
# 2026-08-07 (direct user request): a sensitive path like `~/.ssh/id_rsa` or
# `$HOME/.env` embedded in a Bash command string didn't match the original
# regex at all (neither `~` nor `$` was an accepted prefix) -- silently
# invisible to FileScanner regardless of _normalize_path()'s own expansion
# below. Broadening the match set is only safe because identify() now also
# validates each fallback match actually resolves to something real on disk
# (see the `os.path.exists()` check there) -- see that comment for why.
#
# 2026-08-07 (2nd correction, same day -- found via a real stuck-`Verify`
# report, traced through a real project's `.scalene/scan_cache.json`): none
# of the 3 alternatives above required their own match to *start* at a real
# token boundary -- `finditer()` happily started a match mid-token, at any
# internal `/` no matter what came before it, silently dropping everything
# before that `/`. A deliberately-unmatched bare relative token like
# "agents/CHAT.md" (no `/`, `./`, `../`, `~`, or `$` prefix -- exactly the
# case this file's own docstring says should NOT match) was in practice
# matched anyway, starting at the `/` between "agents" and "CHAT.md",
# producing the wrong absolute identity "/CHAT.md" (filesystem root) rather
# than correctly not matching at all. The leading `(?<![\w./~])` negative
# lookbehind fixes this: a match may only start where the preceding
# character (if any) is not itself part of a path/word token, so an
# internal `/` deep inside an unrelated string can never become a match
# start on its own.
_PATH_FALLBACK_RE = re.compile(
    r"(?<![\w./~])(?P<path>"
    r"~[\w-]*/[\w./+-]+"
    r"|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?/[\w./+-]+"
    r"|\.{0,2}/[\w./+-]+"
    r")"
)

# Generic URI scheme prefix (RFC 3986 scheme grammar, simplified) -- matches
# any protocol (https://, ftp://, ws://, s3://, ...), not just http(s).
_URI_SCHEME = r"[a-zA-Z][a-zA-Z0-9+.-]*://"

# 2026-07-22 (direct user request): URLScanner handles any URL with a
# protocol -- EXCEPT file://, which is a filesystem reference wearing a URI
# shape and belongs to FileScanner instead (see _FILE_URI_RE below).
# Deliberately matches ANY scheme here, including file:// -- filtering it
# out belongs in the caller (URLScanner.identify(), below), not in this
# regex: a `(?!file://)` lookahead only blocks a match *starting* at that
# exact position, but finditer still retries one character later and
# happily matches "ile://..." as if "ile" were a scheme name (a real bug
# found via a test that actually exercised it, not assumed safe).
# STORY-1101 (docs/ARCHITECTURE.md sec14.2): captures the full URL (scheme +
# host + path), stopping at the first '?' -- identity is per-URL, not
# per-host, so scanning one path can no longer vouch for an unbounded set of
# other paths under the same host. Query string dropped to keep cache keys
# bounded.
_URL_FALLBACK_RE = re.compile(r"(?P<url>" + _URI_SCHEME + r"[^\s\"'?]+)")

# file:// is a filesystem reference, not a fetchable URL -- FileScanner's
# own resource, stripped down to the real path (matches _resolve_resource()'s
# existing file:// handling in onboard.py, same normalization).
_FILE_URI_RE = re.compile(r"file://(?P<path>[^\s\"']+)")


def _is_file_uri(url: str) -> bool:
    return url.lower().startswith("file://")

# Full URI span (any scheme, including file://) -- used only to exclude a
# URI's internal slashes from _PATH_FALLBACK_RE, so "https://host/a/b" (or
# "file:///a/b") doesn't get double-counted as a stray path fragment on top
# of its own correct extraction (URLScanner's or _FILE_URI_RE's).
_ANY_URI_SPAN_RE = re.compile(_URI_SCHEME + r"\S+")


def _normalize_path(raw: str) -> str:
    """docs/ARCHITECTURE.md sec18.2 correction (2026-08-07, direct user
    request): a detected path may be shell shorthand (`~`, `~user`) or
    carry an embedded environment variable (`$HOME`, `${HOME}`) rather than
    already being a literal filesystem path -- `os.path.abspath()` alone
    treats either as a literal relative-path segment (`~/.ssh/id_rsa`
    normalizes to `<cwd>/~/.ssh/id_rsa`, not the real
    `/home/user/.ssh/id_rsa`), silently missing the exact class of
    sensitive path `_HARDCODED_RESTRICTED_PREFIXES` below exists to catch.
    `expandvars()`/`expanduser()` resolve against *this process's own*
    environment -- correct here specifically because this hook runs in the
    same environment the real Bash tool call would, so `$HOME` etc. expand
    identically to how the shell itself would expand them. Order matters:
    `expanduser()` first, so a leading `~` resolves before `expandvars()`
    looks at the rest of the string; `abspath()` last, for the pre-existing
    relative-path handling."""
    return os.path.abspath(os.path.expandvars(os.path.expanduser(raw)))


def _has_real_path_content(path: str) -> bool:
    """2026-08-07 (direct user bug report): a match built entirely from
    separators (`/`, `//`, `///`, `..`) satisfies `_PATH_FALLBACK_RE`'s
    shape but isn't a reference to any specific resource -- a Rust `///`
    doc comment, or a bare `//` used as a stray comment marker in prose,
    both matched and normalized to the bare filesystem root `/` (which
    then passed the real-file existence check below, since the root always
    exists, and got identified as a genuinely touched resource). Requires
    at least one real content character (alnum or `_`) somewhere in the
    match -- a real path always names *something* under a directory; pure
    punctuation never does."""
    return any(c.isalnum() or c == "_" for c in path)


def _find_paths_excluding_urls(text: str) -> list[str]:
    url_spans = [m.span() for m in _ANY_URI_SPAN_RE.finditer(text)]
    paths = []
    for match in _PATH_FALLBACK_RE.finditer(text):
        start, end = match.span()
        if any(start < url_end and end > url_start for url_start, url_end in url_spans):
            continue
        path = match.group("path")
        if not _has_real_path_content(path):
            continue
        paths.append(path)
    return paths


@dataclass(frozen=True)
class Resource:
    kind: str  # "file" | "url" -- extensible, not a closed enum
    identity: str  # cache key material: absolute path, or full URL (sec14.2 -- not bare host)
    scanner_name: str


@dataclass(frozen=True)
class ScanResult:
    label: str  # "public" | "sensitive" | "trusted" | "untrusted"
    reason: str = ""
    reputation: float | None = None  # sec17.6: 0.0 (worst) .. 1.0 (best); None where no graded signal exists


class ScannerMachineryError(Exception):
    """Raised by Scanner.scan() when the scan itself couldn't run (STORY-1004:
    scanning-machinery failure, e.g. subprocess spawn failure or the target
    couldn't even be read) -- distinct from an ordinary finding, which is
    always returned as a ScanResult, never raised."""


class Scanner:
    """Base class, not a structural Protocol -- `match()` and `from_config()`
    below need a real default implementation subclasses inherit rather than
    each having to redefine it. `load_scanners()` still validates
    conformance by hasattr (duck typing), so a third-party scanner that
    doesn't inherit from this class at all keeps working exactly as before,
    provided it defines `.name`/`.identify()`/`.scan()`; it just won't get
    match()/from_config()'s default behavior for free."""

    name: str  # "secrets", "reputation", ... -- the label namespace this scanner owns

    def identify(self, tool_name: str, args: dict) -> list[Resource]:
        """Find candidate resources this scanner cares about within a call's args."""
        raise NotImplementedError

    def scan(self, resource: Resource) -> ScanResult:
        """Verify one resource. Runs in an isolated subprocess; never raises."""
        raise NotImplementedError

    def match(self, rule: "PolicyRule", resource: Resource) -> bool:
        """Does `rule.pattern` select `resource`? Default: plain regex
        against `resource.identity`, same behavior as before this method
        existed. A scanner whose identity strings have their own shape
        (e.g. FileScanner's filesystem paths) can override this rather than
        resource_verifier.py applying one generic matcher to every resource
        kind with no awareness of how each scanner's identities are formed.

        PolicyRule no longer validates `pattern` as regex at construction
        time (policy_config.py: pattern's syntax is scanner-owned, so it
        can't know at construction whether a given rule is meant for a
        scanner that reads it as regex or as something else, e.g. gitignore
        syntax for FileScanner). A pattern authored for a different syntax
        (e.g. a gitignore "**/" prefix) is often not valid regex at all --
        this must fail safe (no match), not raise and take the whole
        hot-path hook call down with it."""
        try:
            return bool(re.search(rule.pattern, resource.identity))
        except re.error:
            return False

    @classmethod
    def from_config(cls, raw_config: dict) -> "Scanner":
        """Construct an instance from this scanner's own `scanners.extra[]`
        config sub-block (STORY-1501's registry, `load_scanners()` below).
        Default: ignore config, exactly today's bare `cls()` behavior -- a
        scanner that needs settings (an enterprise CMDB/vuln-DB endpoint,
        credentials path, etc., STORY-1501's own motivating rationale)
        overrides this; every existing scanner needs no change to keep
        working unchanged."""
        return cls()


def _string_args(args: dict) -> list[str]:
    return [value for value in args.values() if isinstance(value, str) and value]


@functools.lru_cache(maxsize=256)
def _compiled_gitignore_spec(pattern: str) -> pathspec.GitIgnoreSpec:
    # Cached: FileScanner.match() runs on the hot path (every pre_tool_use
    # call re-checks every rule against every identified resource) --
    # compiling the same rule's pattern from scratch on every single call
    # would be wasted work. `pattern` may be multiple gitignore lines (a
    # directory-wide rule needs 2: the root path itself, and "root/**" for
    # everything under it -- plain gitignore semantics don't match a bare
    # directory via "dir/**" alone), so split on newlines here rather than
    # forcing every caller to do it.
    return pathspec.GitIgnoreSpec.from_lines(pattern.splitlines())


_GITIGNORE_SPECIAL_CHARS = set("*?[]!#\\")


def escape_gitignore_literal(literal: str) -> str:
    """gitignore-pattern analog of re.escape()/glob.escape() -- for a
    caller (onboard.py, monitor_app.py, policy_config.py) that wants a
    FileScanner rule's pattern to match one exact literal path, not
    interpret any of its characters as gitignore wildcard syntax."""
    return "".join("\\" + ch if ch in _GITIGNORE_SPECIAL_CHARS else ch for ch in literal)


# docs/ARCHITECTURE.md sec18.2 (STORY-1502): kept to exactly the two paths
# the user named -- not expanded to a broader guessed list. A developer can
# add their own restricted paths today via scalene_policy.yaml's `rules:`
# (sec14.1); this constant is a hardcoded floor, not the whole mechanism.
_HARDCODED_RESTRICTED_PREFIXES = (
    "/etc",
    os.path.expanduser("~/.ssh"),
)


def _is_hardcoded_restricted(identity: str) -> bool:
    """True if `identity` (an absolute file path) is exactly one of, or
    strictly under, a hardcoded restricted prefix -- not a naive
    str.startswith, which would also match a false positive like
    "/etcetera/file" against the "/etc" prefix."""
    for prefix in _HARDCODED_RESTRICTED_PREFIXES:
        if identity == prefix or identity.startswith(prefix.rstrip("/") + os.sep):
            return True
    return False


class FileScanner(Scanner):
    name = "secrets"

    def match(self, rule: "PolicyRule", resource: Resource) -> bool:
        """gitignore syntax, not regex -- file paths are the case this
        match() override exists for (user request: familiar wildcard
        matching for "the whole project folder recursively", same syntax
        as .gitignore rather than inventing a bespoke convention). `pattern`
        may be multiple lines (see _compiled_gitignore_spec) -- a
        directory-wide rule needs 2 lines (the root itself, and "root/**"
        for everything under it), since plain gitignore semantics don't
        match a bare directory via "root/**" alone, only its contents.
        pathspec's GitIgnoreSpec handles the absolute-path leading "/" and
        the "/etc" vs. false-positive "/etcetera" boundary correctly on its
        own -- no bespoke boundary-check code needed here."""
        return _compiled_gitignore_spec(rule.pattern).match_file(resource.identity)

    def identify(self, tool_name: str, args: dict) -> list[Resource]:
        identities: list[str] = []

        # `known_field`/file:// paths are structured references -- the tool
        # schema (or an explicit file:// URI) already tells us this string
        # IS a path, so no existence check here: `Write`'s own target
        # legitimately doesn't exist yet (docs/ARCHITECTURE.md sec13.4's
        # abspath-normalization note applies equally to expanduser/
        # expandvars below -- same identity a live evaluation would produce).
        known_field = _FILE_PATH_FIELDS.get(tool_name)
        known_value = args.get(known_field) if known_field else None
        if isinstance(known_value, str) and known_value:
            identities.append(_normalize_path(known_value))

        for value in _string_args(args):
            for path in _find_paths_excluding_urls(value):
                # 2026-08-07 (direct user request): the generic fallback is
                # a heuristic regex match over arbitrary string content
                # (e.g. a whole Bash command), not a structured field known
                # to be a path -- broadening _PATH_FALLBACK_RE to also catch
                # `~`/`$VAR`-shaped tokens (above) is only safe paired with
                # this: validate the *expanded* candidate actually resolves
                # to something real on disk before treating it as a genuine
                # resource, dropping stray regex matches (git refs, ratios
                # in prose, etc.) that were never real paths to begin with.
                # `os.path.exists()`, not `isfile()` -- a directory is a
                # legitimate FileScanner resource too (project-folder rules
                # already match a directory tree, sec18.4).
                normalized = _normalize_path(path)
                if os.path.exists(normalized):
                    identities.append(normalized)
            # 2026-07-22 (direct user request): file:// is a filesystem
            # reference wearing a URI shape -- recognized here, not by
            # URLScanner, regardless of which tool/field it appears in.
            for m in _FILE_URI_RE.finditer(value):
                identities.append(_normalize_path(m.group("path")))

        seen: set[str] = set()
        resources = []
        for identity in identities:
            if identity in seen:
                continue
            seen.add(identity)
            resources.append(Resource(kind="file", identity=identity, scanner_name=self.name))
        return resources

    def scan(self, resource: Resource) -> ScanResult:
        # sec18.2 (STORY-1502): a hardcoded-restricted path short-circuits
        # before the secrets-scan subprocess ever runs -- deliberate, not
        # just an optimization: Scalene shouldn't need to read the byte
        # contents of e.g. ~/.ssh/id_rsa to know it's sensitive. The
        # distinct reason text (vs. a real secrets finding) resolves
        # Smith's Gate 1 non-blocking note (don't let a clean file read as
        # "a secret was found").
        if _is_hardcoded_restricted(resource.identity):
            return ScanResult(label="sensitive", reason="path matches a hardcoded restricted system location")

        # 2026-08-07 (direct user bug report): `pre_tool_use` runs *before*
        # the tool itself executes, so a `Write` to a brand-new path is
        # identified and Verify-able before the file exists. Scanning a
        # nonexistent target used to mean scan_worker's plain `open(path)`
        # raising `FileNotFoundError`, surfacing as a generic `machinery_
        # error` this method doesn't distinguish from a real scanning
        # failure -- `ReviewScreen.action_verify()` already fails safe on
        # that (catches `ScannerMachineryError`, leaves the target
        # unverified rather than crashing the screen), which meant Allow
        # stayed permanently disabled for any new-file `Write`, forever --
        # there is genuinely nothing to scan yet, which is not a finding of
        # "sensitive" (nothing was found), so it shouldn't behave like one.
        # Checked *after* the hardcoded-restricted check above, not before:
        # writing a brand-new file under e.g. `~/.ssh` must still be caught
        # regardless of whether the file exists yet.
        if not os.path.exists(resource.identity):
            return ScanResult(label="public")

        result = run_scanner("secrets", resource.identity)
        if result.get("machinery_error"):
            raise ScannerMachineryError(result.get("reason", "secrets scan machinery failed"))
        if result.get("ok", False):
            return ScanResult(label="public")
        return ScanResult(label="sensitive", reason=result.get("reason", ""))


class URLScanner(Scanner):
    name = "reputation"
    # No match() override -- URL identities aren't path-shaped, so the
    # base class's plain-regex default (unchanged from before match()
    # existed) is still the right behavior here.

    def identify(self, tool_name: str, args: dict) -> list[Resource]:
        urls: list[str] = []

        known_field = _URL_FIELDS.get(tool_name)
        known_value = args.get(known_field) if known_field else None
        if isinstance(known_value, str) and known_value:
            urls.extend(
                m.group("url") for m in _URL_FALLBACK_RE.finditer(known_value) if not _is_file_uri(m.group("url"))
            )

        for value in _string_args(args):
            urls.extend(
                m.group("url") for m in _URL_FALLBACK_RE.finditer(value) if not _is_file_uri(m.group("url"))
            )

        seen: set[str] = set()
        resources = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            resources.append(Resource(kind="url", identity=url, scanner_name=self.name))
        return resources

    def scan(self, resource: Resource) -> ScanResult:
        # sec14.2: identity is per-URL for cache-key granularity, but the
        # reputation heuristic itself is host-level (a URL's path doesn't
        # change whether its host is reputable) -- extract the host if
        # identity parses as a URL, otherwise treat identity as already
        # being a bare host (onboard.py / direct-construction callers).
        host = urlparse(resource.identity).hostname or resource.identity
        result = run_scanner("reputation", host)
        if result.get("machinery_error"):
            raise ScannerMachineryError(result.get("reason", "reputation scan machinery failed"))
        reputation = result.get("reputation")
        if result.get("ok", False):
            return ScanResult(label="trusted", reputation=reputation)
        return ScanResult(label="untrusted", reason=result.get("reason", ""), reputation=reputation)


SCANNERS: dict[str, Scanner] = {"secrets": FileScanner(), "reputation": URLScanner()}


class ScannerRegistryError(ValueError):
    """Raised by load_scanners() on a bad `scanners:` config section --
    caught and re-raised as PolicyConfigError by policy_config.from_yaml
    (avoids scanner.py importing back from policy_config.py)."""


def load_scanners(raw_config: dict) -> dict[str, Scanner]:
    """docs/ARCHITECTURE.md sec18.1 (STORY-1501): builds the registry a
    PolicyConfig uses, starting from the 2 builtins (always present -- an
    empty/absent `scanners:` section reproduces today's exact behavior) plus
    any `extra:` entries the project's scalene_policy.yaml declares.

    `raw_config` is `scalene_policy.yaml`'s `scanners:` section (or {}) --
    parsing/shape-validation of the YAML itself is policy_config.py's job;
    this function only resolves and validates the scanner classes it names.
    """
    scanners: dict[str, Scanner] = dict(SCANNERS)

    extra = raw_config.get("extra", []) or []
    if not isinstance(extra, list):
        raise ScannerRegistryError("'scanners.extra' must be a list")

    for i, entry in enumerate(extra):
        if not isinstance(entry, dict):
            raise ScannerRegistryError(f"'scanners.extra[{i}]' must be a mapping")
        try:
            name = entry["name"]
            import_path = entry["import"]
        except KeyError as exc:
            raise ScannerRegistryError(f"'scanners.extra[{i}]' is missing required field {exc}") from exc

        if name in scanners:
            raise ScannerRegistryError(
                f"'scanners.extra[{i}]' name {name!r} collides with an existing scanner "
                f"(builtin or already-registered)"
            )

        if ":" not in import_path:
            raise ScannerRegistryError(
                f"'scanners.extra[{i}].import' must be \"module.path:ClassName\", got {import_path!r}"
            )
        module_path, _, class_name = import_path.partition(":")
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ScannerRegistryError(f"'scanners.extra[{i}].import' {import_path!r} could not be imported: {exc}") from exc
        try:
            cls = getattr(module, class_name)
        except AttributeError as exc:
            raise ScannerRegistryError(
                f"'scanners.extra[{i}].import' {import_path!r}: module has no attribute {class_name!r}"
            ) from exc

        raw_scanner_config = entry.get("config", {}) or {}
        if not isinstance(raw_scanner_config, dict):
            raise ScannerRegistryError(f"'scanners.extra[{i}].config' must be a mapping")
        try:
            # A third-party class that doesn't inherit Scanner (e.g. this
            # project's own DummyScanner test fixture) has no from_config()
            # at all -- fall back to the pre-existing bare cls(), same
            # behavior as before this method existed.
            from_config = getattr(cls, "from_config", None)
            instance = from_config(raw_scanner_config) if from_config is not None else cls()
        except Exception as exc:
            raise ScannerRegistryError(f"'scanners.extra[{i}]' ({import_path}) could not be constructed: {exc}") from exc

        if not (hasattr(instance, "name") and hasattr(instance, "identify") and hasattr(instance, "scan")):
            raise ScannerRegistryError(
                f"'scanners.extra[{i}]' ({import_path}) does not satisfy the Scanner protocol "
                f"(needs .name, .identify(), .scan())"
            )

        scanners[name] = instance

    return scanners
