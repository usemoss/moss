#!/usr/bin/env bash
# Usage: npm-release-tag.sh <npm package> <git tag>
#
# Run in an npm release job before `npm publish`. Pushes the release tag at
# GITHUB_SHA so it always marks the commit that built the tarball, then writes
# to GITHUB_OUTPUT:
#   published=true  the version is already on npm and tagged here; skip publish
#   dist_tag=...    the npm dist-tag to publish under
# Needs VERSION, GITHUB_SHA, GITHUB_REPOSITORY, GITHUB_OUTPUT and GH_TOKEN.
set -euo pipefail

PACKAGE="$1"
TAG="$2"

# `npm view` exits 1 both for a missing version and for a failed lookup;
# only E404 means "not there". Prints the value, or nothing on E404.
npm_lookup() {
  local out
  if out=$(npm view "$1" "$2" --json 2>/dev/null); then
    jq -r '.' <<<"$out"
  elif [[ "$(jq -r '.error.code // empty' <<<"$out" 2>/dev/null)" != "E404" ]]; then
    echo "Couldn't look up $1 $2 on npm: $out" >&2
    return 1
  fi
}

TAGGED_SHA=$(git ls-remote origin "refs/tags/$TAG" | cut -f1)
PUBLISHED=$(npm_lookup "$PACKAGE@$VERSION" version)

if [[ -n "$PUBLISHED" ]]; then
  if [[ "$TAGGED_SHA" == "$GITHUB_SHA" ]]; then
    echo "$PACKAGE@$VERSION is already on npm and tagged at $GITHUB_SHA, nothing left to do"
    echo "published=true" >> "$GITHUB_OUTPUT"
    exit 0
  fi
  echo "$PACKAGE@$VERSION is already on npm. Bump the version in package.json." >&2
  exit 1
fi

# npm 11 refuses to put a prerelease on latest unless told to. Do that only
# while latest is itself a prerelease (the package has no stable release yet),
# so a beta never replaces a stable latest.
DIST_TAG=latest
if [[ "$VERSION" == *-* ]]; then
  CURRENT_LATEST=$(npm_lookup "$PACKAGE" dist-tags.latest)
  if [[ -n "$CURRENT_LATEST" && "$CURRENT_LATEST" != *-* ]]; then
    DIST_TAG=next
  fi
fi
echo "dist_tag=$DIST_TAG" >> "$GITHUB_OUTPUT"

if [[ "$TAGGED_SHA" == "$GITHUB_SHA" ]]; then
  echo "$TAG already points at $GITHUB_SHA"
  exit 0
fi

# The version never reached npm, so a tag left by a failed run marks nothing
# and can move, but only forward: re-running an older failed run mustn't
# publish older code over a fix.
if [[ -n "$TAGGED_SHA" ]]; then
  COMPARE=$(gh api "repos/$GITHUB_REPOSITORY/compare/$TAGGED_SHA...$GITHUB_SHA" --jq .status)
  if [[ "$COMPARE" != "ahead" ]]; then
    echo "$TAG points at $TAGGED_SHA, which $GITHUB_SHA doesn't build on ($COMPARE). Release from a newer commit, or delete the tag." >&2
    exit 1
  fi
fi

git config user.name "github-actions"
git config user.email "github-actions@users.noreply.github.com"
git tag -f "$TAG"
git push -f origin "$TAG"
