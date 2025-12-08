#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$( cd "${BASH_SOURCE[0]%/*}/.." && pwd )"
cd "$PROJECT_ROOT"

if [[ -d "venv/Scripts" ]]; then
  source venv/Scripts/activate
elif [[ -d "venv/bin" ]]; then
  source venv/bin/activate
fi

python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py test tests
ruff check .
