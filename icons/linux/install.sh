#!/bin/sh
# Installs the icon theme files and desktop entry for the current user.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
share="${XDG_DATA_HOME:-$HOME/.local/share}"
mkdir -p "$share/icons" "$share/applications"
cp -r "$here/icons/hicolor" "$share/icons/"
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t "$share/icons/hicolor" || true
echo "Installed."
