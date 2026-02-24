#!/usr/bin/env bash
# scripts/run_streamlit.sh
# Activate/create .venv then run Streamlit app
VENV=".venv"
APP="app/streamlit_app.py"

echo "Run Streamlit (helper)"

if [ -z "$VIRTUAL_ENV" ]; then
  if [ -f "$VENV/bin/activate" ]; then
    echo "Activating venv at $VENV"
    # shellcheck source=/dev/null
    source "$VENV/bin/activate"
  else
    echo "Virtualenv not found at $VENV. Creating..."
    python -m venv "$VENV"
    # shellcheck source=/dev/null
    source "$VENV/bin/activate"
    if [ -f "requirements.txt" ]; then
      echo "Installing requirements..."
      pip install -r requirements.txt
    fi
  fi
else
  echo "Virtualenv already active."
fi

echo "Starting Streamlit app: $APP"
streamlit run "$APP"
