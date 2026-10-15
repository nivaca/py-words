#!/bin/sh
# Removes the py-words icons installed by install.sh.
set -e
share="${XDG_DATA_HOME:-$HOME/.local/share}"
name="py-words"

# Icons: every size under hicolor, including scalable
if [ -d "$share/icons/hicolor" ]; then
    find "$share/icons/hicolor" -path "*/apps/$name.*" -type f -delete
fi

# Refresh caches (ignore failures if the tools are missing)
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t "$share/icons/hicolor" || true

echo "Uninstalled."
