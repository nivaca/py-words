#!/bin/sh
# Removes the py-words .desktop entries and icons from the user's data
# folder, and nothing else (no folders, not even empty ones).
set -e
share="${XDG_DATA_HOME:-$HOME/.local/share}"
name="py-words"

# The menu entries (as made by words_install.py)
for entry in "$name.desktop" "$name.cli.desktop" "$name.tui.desktop" \
             "$name.web.desktop"; do
    if [ -f "$share/applications/$entry" ]; then
        rm -f "$share/applications/$entry"
    fi
done

# The icons: <size>/apps/py-words.png and .svg, in every size
if [ -d "$share/icons/hicolor" ]; then
    for dir in "$share/icons/hicolor"/*/apps; do
        for ext in png svg; do
            if [ -f "$dir/$name.$ext" ]; then
                rm -f "$dir/$name.$ext"
            fi
        done
    done
fi

# Refresh caches (ignore failures if the tools are missing)
command -v update-desktop-database >/dev/null && update-desktop-database "$share/applications" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t "$share/icons/hicolor" || true

echo "Uninstalled."
