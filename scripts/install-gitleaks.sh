#!/usr/bin/env bash
# Installs a pinned gitleaks release into this repo's .venv/bin (no sudo),
# for the pre-commit secret scan in .githooks/pre-commit.
#
# The download is verified against the release's own checksums file before
# anything is extracted. Re-running is a no-op when the pinned version is
# already installed. Bump GITLEAKS_VERSION to upgrade.
set -euo pipefail

GITLEAKS_VERSION="${GITLEAKS_VERSION:-8.30.1}"
DEST_DIR="${1:-.venv/bin}"
DEST="$DEST_DIR/gitleaks"

if [ -x "$DEST" ] && "$DEST" version 2>/dev/null | grep -qx "v\?$GITLEAKS_VERSION"; then
    echo "gitleaks $GITLEAKS_VERSION already installed at $DEST"
    exit 0
fi

case "$(uname -s)" in
    Linux) os=linux ;;
    Darwin) os=darwin ;;
    *) echo "install-gitleaks: unsupported OS $(uname -s) — install gitleaks manually: https://github.com/gitleaks/gitleaks#installing" >&2; exit 1 ;;
esac
case "$(uname -m)" in
    x86_64 | amd64) arch=x64 ;;
    aarch64 | arm64) arch=arm64 ;;
    *) echo "install-gitleaks: unsupported architecture $(uname -m) — install gitleaks manually: https://github.com/gitleaks/gitleaks#installing" >&2; exit 1 ;;
esac

if command -v sha256sum >/dev/null 2>&1; then
    sha256() { sha256sum "$1" | cut -d' ' -f1; }
elif command -v shasum >/dev/null 2>&1; then
    sha256() { shasum -a 256 "$1" | cut -d' ' -f1; }
else
    echo "install-gitleaks: need sha256sum or shasum to verify the download" >&2
    exit 1
fi

asset="gitleaks_${GITLEAKS_VERSION}_${os}_${arch}.tar.gz"
base="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Downloading $asset..."
curl -fsSL "$base/$asset" -o "$tmp/$asset"
curl -fsSL "$base/gitleaks_${GITLEAKS_VERSION}_checksums.txt" -o "$tmp/checksums.txt"

expected="$(awk -v a="$asset" '$2 == a {print $1}' "$tmp/checksums.txt")"
actual="$(sha256 "$tmp/$asset")"
if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then
    echo "install-gitleaks: checksum mismatch for $asset (expected '${expected:-<missing>}', got '$actual') — not installing" >&2
    exit 1
fi

tar -xzf "$tmp/$asset" -C "$tmp" gitleaks
mkdir -p "$DEST_DIR"
install -m 0755 "$tmp/gitleaks" "$DEST"
echo "Installed gitleaks $("$DEST" version) at $DEST (checksum verified)"
