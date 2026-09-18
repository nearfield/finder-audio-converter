#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
TASK_ROOT="$(cd "$(dirname "$0")" && pwd)"
TASK_PYTHON="${FINDER_AUDIO_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$TASK_PYTHON" ]]; then echo 'Python 3 is required.' >&2; exit 1; fi
exec "$TASK_PYTHON" "$TASK_ROOT/scripts/install.py" --uninstall "$@"
