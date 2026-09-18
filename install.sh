#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
TASK_ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ "${1:-}" == --bootstrap ]]; then
  shift
  "$TASK_ROOT/scripts/bootstrap.sh"
fi
if [[ "$(uname -s)" != Darwin ]]; then echo 'macOS is required.' >&2; exit 1; fi
if ! /usr/bin/xcrun --find swiftc >/dev/null 2>&1; then
  echo 'Command Line Tools are required. Run ./install.sh --bootstrap first.' >&2; exit 1
fi
TASK_PYTHON="${FINDER_AUDIO_PYTHON:-$(command -v python3 || true)}"
if [[ -z "$TASK_PYTHON" ]]; then echo 'Python 3 is required. Run ./install.sh --bootstrap.' >&2; exit 1; fi
exec "$TASK_PYTHON" "$TASK_ROOT/scripts/install.py" "$@"
