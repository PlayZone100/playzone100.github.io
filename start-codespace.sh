#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f package.json ]; then
  echo "package.json not found. Run this script from the repository root."
  exit 1
fi

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "Created .env from .env.example. Add your authorized video API URL and key, then run this script again."
  else
    echo ".env.example not found."
    exit 1
  fi
fi

if grep -q "your-authorized-video-api.example.com\|replace_with_real_secret" .env; then
  echo "Please replace the placeholder values in .env before starting the generator."
  exit 1
fi

npm install
exec npm start
