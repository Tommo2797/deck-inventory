#!/bin/bash
# Pubblica una nuova versione di Deck Inventory (solo autore, Mac).
# Uso: .app/src/tools/publish.sh <versione> [--skip-online] [--dry-run]
# Funziona da qualunque cartella: i percorsi si calcolano da qui.
# Usa l'ambiente isolato del progetto (.app/runtime), come i launcher.

ROOT="$(cd "$(dirname "$0")/../../.." && pwd -P)" || exit 1
cd "$ROOT" || exit 1

RT="$ROOT/.app/runtime"
export UV_CACHE_DIR="$RT/uv-cache"
export UV_PYTHON_INSTALL_DIR="$RT/python"
export UV_PROJECT_ENVIRONMENT="$RT/venv"
export PLAYWRIGHT_BROWSERS_PATH="$RT/browsers"
export UV_PYTHON_PREFERENCE="only-managed"
export UV_NO_CONFIG=1
export PYTHONPATH="$ROOT/.app/src"
unset VIRTUAL_ENV

UV="$RT/uv/uv"
[ -x "$UV" ] || UV="$(command -v uv)" || { echo "uv non trovato: avvia prima Start (Mac).command." >&2; exit 1; }

exec "$UV" run --frozen --project .app/src python .app/src/tools/publish.py "$@"
