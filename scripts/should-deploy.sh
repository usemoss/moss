#!/bin/bash
# Only build for: direct push to deploy, or PRs targeting deploy
[ "$VERCEL_GIT_COMMIT_REF" = "deploy" ] && exit 1
if [ -n "$VERCEL_GIT_PULL_REQUEST_ID" ]; then
  T=$(curl -s "https://api.github.com/repos/$VERCEL_GIT_REPO_OWNER/$VERCEL_GIT_REPO_SLUG/pulls/$VERCEL_GIT_PULL_REQUEST_ID" | python3 -c "import sys,json;print(json.load(sys.stdin).get('base',{}).get('ref',''))")
  [ "$T" = "deploy" ] && exit 1
fi
exit 0
