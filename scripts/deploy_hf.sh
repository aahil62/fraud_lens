#!/usr/bin/env bash
# Push the committed HEAD to a Hugging Face Docker Space.
# Usage: scripts/deploy_hf.sh <hf-username>/<space-name>
# Prerequisites (done by you, never by this script): create the Space with the
# Docker SDK and run `huggingface-cli login` so git can authenticate.
set -euo pipefail
SPACE_ID="${1:?Usage: scripts/deploy_hf.sh <hf-username>/<space-name>}"
ROOT="$(git rev-parse --show-toplevel)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git -C "$ROOT" archive HEAD | tar -x -C "$WORK"
cp "$ROOT/deploy/hf-space/README.md" "$WORK/README.md"
cd "$WORK"
git init -q -b main
git add -A
git commit -q -m "Deploy FraudLens $(git -C "$ROOT" rev-parse --short HEAD)"
git push --force "https://huggingface.co/spaces/$SPACE_ID" main
echo "Pushed to https://huggingface.co/spaces/$SPACE_ID"
