#!/usr/bin/env bash
# Deploy QuickChat to a Hugging Face Space (Docker SDK).
#
# Usage:
#   scripts/deploy_hf_space.sh <hf-username> <space-name>
#
# Prerequisites:
#   1. pip install huggingface_hub  (or use the HF CLI)
#   2. huggingface-cli login        (authenticate with your HF token)
#   3. Set Space secrets in HF UI:
#        LLM_PROVIDER = groq
#        GROQ_API_KEY = gsk_your_key_here
#
# What this script does:
#   - Adds your HF Space as a git remote
#   - Pushes the current branch to the Space (triggers a rebuild)
set -e

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <hf-username> <space-name>"
  echo ""
  echo "Example: $0 rampradeep28 quickchat"
  echo ""
  echo "IMPORTANT: Before deploying, set these secrets in your HF Space settings:"
  echo "  LLM_PROVIDER = groq"
  echo "  GROQ_API_KEY = gsk_your_key_here"
  exit 1
fi

USER=$1
SPACE=$2
SPACE_REPO="https://huggingface.co/spaces/$USER/$SPACE"

echo "Deploying to: $SPACE_REPO"
echo ""

# Add HF remote if not present
if ! git remote | grep -q hf; then
  echo "Adding HF Space remote..."
  git remote add hf "https://huggingface.co/spaces/$USER/$SPACE"
fi

# Push to HF Space (main branch)
echo "Pushing to HF Space..."
git push hf HEAD:main --force

echo ""
echo "========================================="
echo " Deployed to $SPACE_REPO"
echo "========================================="
echo ""
echo "Services available after build:"
echo "  Streamlit demo:  $SPACE_REPO  (port 7860)"
echo "  Chat API:        POST /chat    (port 8000, internal)"
echo "  Voice WebSocket: WS /voice-ws  (port 8000, internal)"
echo "  Health check:    GET /health   (port 8000, internal)"
echo ""
echo "NOTE: Port 8000 (FastAPI) is internal to the container."
echo "For external API access, consider deploying to a VPS or cloud platform."
