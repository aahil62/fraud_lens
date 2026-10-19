#!/usr/bin/env bash
# Upload the committed HEAD to a Hugging Face Docker Space.
# Usage: scripts/deploy_hf.sh <hf-username>/<space-name>
# Prerequisites (done by you, never by this script): create the Space with the
# Docker SDK, install the `hf` CLI and run `hf auth login` with a write token.
# `hf upload` stores binary files the way the Hub requires, so no git-lfs setup
# is needed. docs/ is skipped: the image never uses it.
set -euo pipefail
SPACE_ID="${1:?Usage: scripts/deploy_hf.sh <hf-username>/<space-name>}"
command -v hf >/dev/null || { echo "Install the Hugging Face CLI first: curl -LsSf https://hf.co/cli/install.sh | bash" >&2; exit 1; }
hf auth whoami >/dev/null || { echo "Run 'hf auth login' first." >&2; exit 1; }
ROOT="$(git rev-parse --show-toplevel)"
REV="$(git -C "$ROOT" rev-parse --short HEAD)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git -C "$ROOT" archive HEAD | tar -x -C "$WORK"
cp "$ROOT/deploy/hf-space/README.md" "$WORK/README.md"
# --delete removes files left over from an earlier deploy that HEAD no longer has.
hf upload "$SPACE_ID" "$WORK" . --repo-type=space --exclude="docs/*" --delete="*" \
  --commit-message="Deploy FraudLens $REV"
echo "Uploaded $REV to https://huggingface.co/spaces/$SPACE_ID"
