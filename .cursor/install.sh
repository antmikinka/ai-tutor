#!/usr/bin/env bash
# Idempotent setup for the AI Math Tutor Cloud Agent environment.
# Prepares the Python backend (FastAPI) and the React renderer.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Installing system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq \
  python3.12-venv python3-dev build-essential \
  libsndfile1 ffmpeg

echo "==> Creating Python virtual environment"
python3 -m venv venv
./venv/bin/python -m pip install --upgrade pip wheel setuptools

echo "==> Installing backend Python dependencies (runtime subset)"
./venv/bin/pip install -r .cursor/requirements-cloud.txt
# CPU build of PyTorch (the CUDA build is unnecessary for the lazy-loaded models)
./venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu

echo "==> Creating runtime directories required by backend Settings"
mkdir -p \
  src/backend/models/cache \
  src/backend/data \
  src/backend/logs \
  src/backend/uploads \
  src/backend/temp

echo "==> Installing Node dependencies (root + renderer via postinstall)"
npm install

echo "==> Setup complete"
