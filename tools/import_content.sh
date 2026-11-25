#!/usr/bin/env bash
# Refresh content/ with a sparse copy of research-software-support.
#
# Only the parts the PoC needs are copied: main/, config.json, LICENSE.md and
# the lesson modules. The copy is committed (not a submodule) so that a
# typo fix can be made in the GitHub web editor of this repo and get a PR
# preview. content/SOURCE records the upstream commit.
#
# Usage: tools/import_content.sh [ref]   (default: main)
#
# CONTENT_REPO overrides the source, e.g. a local clone with an unpushed
# branch: CONTENT_REPO=~/code/research-software-support make content REF=<branch>
# content/SOURCE then records that path; re-import from upstream before
# committing.
set -euo pipefail

REPO=${CONTENT_REPO:-https://github.com/esciencecenter-digital-skills/research-software-support}
REF=${1:-main}
PATHS=(main config.json LICENSE.md modules/licenses modules/softwarelandscape modules/gen-ai)

root=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

git clone --quiet --filter=blob:none --no-checkout "$REPO" "$tmp/src"
git -C "$tmp/src" sparse-checkout set --no-cone "${PATHS[@]/#//}"
git -C "$tmp/src" checkout --quiet "$REF"

rm -rf "$root/content"
mkdir -p "$root/content/modules"
for p in "${PATHS[@]}"; do
  mkdir -p "$root/content/$(dirname "$p")"
  cp -r "$tmp/src/$p" "$root/content/$p"
done

{
  echo "repo: $REPO"
  echo "commit: $(git -C "$tmp/src" rev-parse HEAD)"
  echo "date: $(git -C "$tmp/src" log -1 --format=%cI)"
  echo "paths: ${PATHS[*]}"
} > "$root/content/SOURCE"

echo "content/ refreshed from $REF:"
cat "$root/content/SOURCE"
