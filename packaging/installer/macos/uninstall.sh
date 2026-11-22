#!/bin/sh
# py-words, a Latin dictionary and parser.
# Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENCE.txt file, or <https://www.gnu.org/licenses/>.
#
# Quita py-words de macOS, tal como lo instaló su paquete (.pkg):
#
#   sudo /Applications/py-words.app/Contents/Resources/uninstall.sh [--purge] [--yes]
#
# o "sudo py-words uninstall".  --purge quita también los ajustes, el
# historial y la caché del usuario que lo corre con sudo.

APPS=/Applications
BUNDLE_ID=io.github.nivaca.py-words
PURGE=
YES=
for arg in "$@"; do
    case $arg in
        --purge) PURGE=1 ;;
        -y|--yes) YES=1 ;;
        -h|--help)
            echo "Usage: sudo $0 [--purge] [--yes]"
            echo "Removes py-words and, with --purge, the settings, history and"
            echo "cache of the user who runs it with sudo."
            exit 0 ;;
        *) echo "uninstall.sh: unknown option: $arg" >&2; exit 1 ;;
    esac
done

if [ "$(id -u)" != 0 ]; then
    echo "Run it with sudo: sudo $0 $*" >&2
    exit 1
fi

if [ -z "$YES" ] && [ -t 0 ]; then
    printf 'Remove py-words from %s? [Y/n] ' "$APPS"
    read -r answer
    case $answer in ''|[yYsS]*) ;; *) exit 1 ;; esac
fi

# (cada aplicación solo si es de py-words)
ours() {
    [ -f "$1/Contents/Info.plist" ] && grep -q "$BUNDLE_ID" "$1/Contents/Info.plist"
}
for app in "$APPS/py-words (CLI).app" "$APPS/py-words (TUI).app" \
           "$APPS/py-words (Web).app" "$APPS/py-words.app"; do
    if ours "$app"; then
        rm -rf "$app" && echo "Removed $app"
    fi
done
link=/usr/local/bin/py-words
if [ -L "$link" ]; then
    case $(readlink "$link") in
        "$APPS/py-words.app/"*) rm -f "$link" && echo "Removed $link" ;;
    esac
fi
# Que macOS olvide los paquetes instalados
for id in app terminal command; do
    pkgutil --forget "$BUNDLE_ID.$id" >/dev/null 2>&1
done

if [ -n "$PURGE" ]; then
    user=${SUDO_USER:-}
    if [ -n "$user" ]; then
        home=$(dscl . -read "/Users/$user" NFSHomeDirectory 2>/dev/null | sed 's/^[^:]*: *//')
        for d in "$home/Library/Application Support/py-words" \
                 "$home/Library/Caches/py-words"; do
            if [ -n "$home" ] && [ -d "$d" ]; then
                rm -rf "$d" && echo "Removed $d"
            fi
        done
    fi
fi
echo "py-words was removed."
