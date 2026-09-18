#!/bin/bash
# Explicit opt-in: install development tools and audio dependencies through Homebrew.
set -euo pipefail
if [[ "$(uname -s)" != Darwin ]]; then echo 'macOS is required.' >&2; exit 1; fi
if [[ "$EUID" == 0 ]]; then echo 'Run this as your normal user, not with sudo.' >&2; exit 1; fi
TASK_BREW="$(command -v brew || true)"
for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
  if [[ -z "$TASK_BREW" && -x "$candidate" ]]; then TASK_BREW="$candidate"; fi
done
if [[ -z "$TASK_BREW" ]]; then
  echo 'Installing Homebrew and its Command Line Tools prerequisites. A terminal administrator password may be needed.'
  /usr/bin/sudo -v
  TASK_INSTALLER="$(mktemp -t finder-audio-homebrew)"
  trap 'rm -f "$TASK_INSTALLER"' EXIT
  /usr/bin/curl --fail --location --proto '=https' --tlsv1.2 https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$TASK_INSTALLER"
  NONINTERACTIVE=1 /bin/bash "$TASK_INSTALLER"
  TASK_BREW=/opt/homebrew/bin/brew
fi
if ! /usr/bin/xcrun --find swiftc >/dev/null 2>&1; then
  echo 'Installing Apple Command Line Tools through Software Update.'
  /usr/bin/sudo -v
  TASK_MARKER=/tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress
  TASK_MARKER_CREATED=0
  if [[ ! -e "$TASK_MARKER" ]]; then /usr/bin/sudo /usr/bin/touch "$TASK_MARKER"; TASK_MARKER_CREATED=1; fi
  TASK_CLT="$(/usr/sbin/softwareupdate --list 2>&1 | /usr/bin/sed -n 's/.*Label: \(Command Line Tools.*\)/\1/p' | /usr/bin/tail -1)"
  if [[ "$TASK_MARKER_CREATED" == 1 ]]; then /usr/bin/sudo /bin/rm -f "$TASK_MARKER"; fi
  if [[ -z "$TASK_CLT" ]]; then echo 'Apple did not offer Command Line Tools. Check softwareupdate --list in Terminal.' >&2; exit 1; fi
  /usr/bin/sudo /usr/sbin/softwareupdate --install "$TASK_CLT" --verbose
  /usr/bin/sudo /usr/bin/xcode-select --switch /Library/Developer/CommandLineTools
fi
"$TASK_BREW" install python ffmpeg
