#!/usr/bin/env bash
# Simple deploy helper for pushing the repo to a Hugging Face Space (Streamlit)
# Usage: scripts/deploy_hf_space.sh <hf-username> <space-name>
set -e
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <hf-username> <space-name>"
  exit 1
fi
USER=$1
SPACE=$2
SPACE_REPO="https://huggingface.co/spaces/$USER/$SPACE"

git init || true
git add .
git commit -m "Deploy to HF Space" || true
# Add remote if not present
if ! git remote | grep origin >/dev/null 2>&1; then
  git remote add origin $SPACE_REPO
fi

git push -u origin main
echo "Pushed to $SPACE_REPO"
