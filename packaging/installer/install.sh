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
# El instalador de py-words para Linux: este script, seguido de un tar.gz
# con el programa y un Python propio (tools/bundle-installer.py lo arma y
# llena los campos entre arrobas).  Se corre con sh; --help dice qué
# acepta.

VERSION='@VERSION@'
ARCH='@ARCH@'
PAYLOAD_LINE=@PAYLOAD_LINE@
PAYLOAD_SHA256='@PAYLOAD_SHA256@'
APP_ID=py-words

SELF=$0
case $SELF in
    */*) ;;
    *) SELF=./$SELF ;;
esac

# --- Mensajes, en inglés o en español según el idioma del entorno -------

lang=${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}
case $lang in
    es*) SPANISH=1 ;;
    *) SPANISH= ;;
esac

# say ENGLISH SPANISH: prints the one for the language of the environment
say() {
    if [ -n "$SPANISH" ]; then printf '%s\n' "$2"; else printf '%s\n' "$1"; fi
}

die() {
    say "py-words installer: $1" "Instalador de py-words: $2" >&2
    exit 1
}

usage() {
    if [ -n "$SPANISH" ]; then cat <<EOF
Instalador de py-words $VERSION ($ARCH), un diccionario de latín.

Uso: sh ${SELF##*/} [OPCIONES]

Instala el programa con un Python propio (no hace falta nada más), la
orden py-words, las entradas del menú de aplicaciones y los íconos.  Como
usuario normal, todo va en sus carpetas (~/.local); como root, para todos
(/opt/py-words, /usr/local).  Si ya estaba instalado, lo reemplaza.

  -y, --yes          no preguntar nada
  --prefix CARPETA   dónde instalar el programa
                     (por omisión: ~/.local/share/py-words, o /opt/py-words)
  --bindir CARPETA   dónde poner la orden py-words
                     (por omisión: ~/.local/bin, o /usr/local/bin)
  --only-gui         solo la entrada del menú de la ventana
  --no-menu          sin entradas en el menú ni íconos
  --no-command       sin la orden py-words
  --uninstall        quitar py-words (de --prefix, o de su lugar por omisión)
  --purge            con --uninstall: quitar también los ajustes, el
                     historial y la caché del usuario
  --check            solo comprobar que el instalador está entero
  --extract CARPETA  solo desempacar el programa en CARPETA
  --version          mostrar la versión
  -h, --help         mostrar esta ayuda

Después: py-words abre la ventana; py-words help muestra los demás
programas; py-words uninstall lo quita.
EOF
    else cat <<EOF
Installer of py-words $VERSION ($ARCH), a Latin dictionary.

Usage: sh ${SELF##*/} [OPTIONS]

Installs the program with a Python of its own (nothing else is needed),
the py-words command, the entries of the applications menu and the icons.
As a normal user, everything goes into your own folders (~/.local); as
root, for everyone (/opt/py-words, /usr/local).  If it was installed
already, it is replaced.

  -y, --yes          ask nothing
  --prefix FOLDER    where to install the program
                     (default: ~/.local/share/py-words, or /opt/py-words)
  --bindir FOLDER    where to put the py-words command
                     (default: ~/.local/bin, or /usr/local/bin)
  --only-gui         only the menu entry of the window
  --no-menu          no menu entries or icons
  --no-command       no py-words command
  --uninstall        remove py-words (from --prefix, or its default place)
  --purge            with --uninstall: also remove the user's settings,
                     history and cache
  --check            only check that the installer is whole
  --extract FOLDER   only unpack the program into FOLDER
  --version          show the version
  -h, --help         show this help

Afterwards: py-words opens the window; py-words help lists the other
programs; py-words uninstall removes it.
EOF
    fi
}

# --- Las opciones ---------------------------------------------------------

YES=
PREFIX=
BINDIR=
ONLY_GUI=
MENU=1
COMMAND=1
ACTION=install
PURGE=
EXTRACT=

need_arg() {
    [ $# -ge 2 ] && [ -n "$2" ] || die "$1 needs a value" "$1 necesita un valor"
}

while [ $# -gt 0 ]; do
    case $1 in
        -y|--yes) YES=1 ;;
        --prefix) need_arg "$@"; PREFIX=$2; shift ;;
        --prefix=*) PREFIX=${1#*=} ;;
        --bindir) need_arg "$@"; BINDIR=$2; shift ;;
        --bindir=*) BINDIR=${1#*=} ;;
        --only-gui) ONLY_GUI=1 ;;
        --no-menu) MENU= ;;
        --no-command) COMMAND= ;;
        --uninstall) ACTION=uninstall ;;
        --purge) PURGE=1 ;;
        --check) ACTION=check ;;
        --extract) need_arg "$@"; ACTION=extract; EXTRACT=$2; shift ;;
        --extract=*) ACTION=extract; EXTRACT=${1#*=} ;;
        --version) echo "py-words $VERSION ($ARCH)"; exit 0 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1 (--help lists them)" \
               "opción desconocida: $1 (--help las muestra)" ;;
    esac
    shift
done

# Las carpetas: las del usuario, o las de todos si corre como root
if [ "$(id -u)" = 0 ]; then
    SYSTEM=1
    : "${PREFIX:=/opt/py-words}"
    : "${BINDIR:=/usr/local/bin}"
    SHARE=/usr/local/share
else
    SYSTEM=
    [ -n "$HOME" ] || die "HOME is not set" "HOME no está definida"
    SHARE=${XDG_DATA_HOME:-$HOME/.local/share}
    : "${PREFIX:=$SHARE/py-words}"
    : "${BINDIR:=$HOME/.local/bin}"
fi

# (absolute paths, as the menu entries and the link need them)
absolute() {
    case $1 in
        /*) printf '%s\n' "$1" ;;
        *) printf '%s\n' "$(pwd)/$1" ;;
    esac
}
PREFIX=$(absolute "${PREFIX%/}")
BINDIR=$(absolute "${BINDIR%/}")
APPS=$SHARE/applications
ICONS=$SHARE/icons/hicolor
MANIFEST=$PREFIX/.install-manifest

ask() {
    [ -n "$YES" ] && return 0
    if [ ! -t 0 ]; then
        die "not a terminal: give --yes to go on without asking" \
            "no es una terminal: dé --yes para seguir sin preguntar"
    fi
    printf '%s ' "$(say "$1 [Y/n]" "$2 [S/n]")"
    read -r answer || return 1
    case $answer in
        ''|[yYsS]*) return 0 ;;
        *) return 1 ;;
    esac
}

# --- El contenido ---------------------------------------------------------

payload() {
    tail -n +"$PAYLOAD_LINE" -- "$SELF"
}

check() {
    if command -v sha256sum >/dev/null 2>&1; then
        sum=$(payload | sha256sum | cut -d' ' -f1)
    elif command -v shasum >/dev/null 2>&1; then
        sum=$(payload | shasum -a 256 | cut -d' ' -f1)
    else
        say "(no sha256sum: the installer is not checked)" \
            "(sin sha256sum: no se comprueba el instalador)" >&2
        return 0
    fi
    [ "$sum" = "$PAYLOAD_SHA256" ] || die \
        "the installer is damaged (its checksum does not match); download it again" \
        "el instalador está dañado (no coincide su suma de comprobación); descárguelo de nuevo"
}

unpack() {
    mkdir -p -- "$1" || die "cannot make $1" "no se puede crear $1"
    payload | tar -xzf - -C "$1" || die "could not unpack into $1" \
        "no se pudo desempacar en $1"
}

# exec_arg ARG: ARG quoted for the Exec line of a desktop entry
exec_arg() {
    case $1 in
        *[!A-Za-z0-9_./+,:@=-]*)
            printf '"%s"' "$(printf '%s' "$1" | sed -e 's/[\\"`$]/\\&/g' -e 's/%/%%/g')" ;;
        *) printf '%s' "$1" ;;
    esac
}

# entry FILE NAME COMMAND TERMINAL: writes a menu entry
entry() {
    {
        echo '[Desktop Entry]'
        echo 'Type=Application'
        echo 'Version=1.0'
        echo "Name=$2"
        echo 'Comment=A Latin Dictionary'
        echo 'Comment[es]=Diccionario latino'
        echo 'Keywords=dictionary;Latin;'
        echo 'Keywords[es]=diccionario;latín;'
        echo 'Categories=Education;Languages;'
        echo "Icon=$APP_ID"
        echo "Exec=$(exec_arg "$PREFIX/bin/py-words") $3"
        if [ "$4" = true ]; then
            echo 'Terminal=true'
        else
            echo 'Terminal=false'
            echo 'StartupNotify=true'
            echo "StartupWMClass=$APP_ID"
        fi
    } > "$1"
    record "$1"
}

record() {
    printf '%s\n' "$1" >> "$MANIFEST"
}

refresh_menu() {
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APPS" >/dev/null 2>&1
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t -q "$ICONS" >/dev/null 2>&1
    fi
    if command -v kbuildsycoca6 >/dev/null 2>&1; then
        kbuildsycoca6 >/dev/null 2>&1
    elif command -v kbuildsycoca5 >/dev/null 2>&1; then
        kbuildsycoca5 >/dev/null 2>&1
    fi
    :
}

# is_ours DIR: whether DIR is a py-words this installer made
is_ours() {
    [ -f "$1/launcher.py" ] && [ -f "$1/.install-manifest" ]
}

# remove_installed: removes what the manifest lists, and then the folder
remove_installed() {
    if [ -f "$MANIFEST" ]; then
        while IFS= read -r path; do
            case $path in
                /*) if [ -L "$path" ] || [ -f "$path" ]; then rm -f -- "$path"; fi ;;
            esac
        done < "$MANIFEST"
    fi
    # (the data folder is read-only, so that an update cannot lose edits)
    chmod -R u+w -- "$PREFIX" 2>/dev/null
    rm -rf -- "$PREFIX"
}

purge() {
    if [ -n "$SYSTEM" ]; then
        say "(--purge as root removes nothing of the users)" \
            "(--purge como root no quita nada de los usuarios)"
        return
    fi
    for d in "${XDG_CONFIG_HOME:-$HOME/.config}/py-words" \
             "${XDG_STATE_HOME:-$HOME/.local/state}/py-words" \
             "${XDG_CACHE_HOME:-$HOME/.cache}/py-words"; do
        if [ -d "$d" ]; then
            rm -rf -- "$d"
            say "Removed $d" "Se quitó $d"
        fi
    done
}

# --- Las acciones ---------------------------------------------------------

do_check() {
    check
    say "The installer is whole: py-words $VERSION ($ARCH)." \
        "El instalador está entero: py-words $VERSION ($ARCH)."
}

do_extract() {
    check
    EXTRACT=$(absolute "$EXTRACT")
    unpack "$EXTRACT"
    say "Unpacked into $EXTRACT; $EXTRACT/bin/py-words starts it." \
        "Desempacado en $EXTRACT; $EXTRACT/bin/py-words lo inicia."
}

do_uninstall() {
    if [ ! -e "$PREFIX" ]; then
        say "py-words is not installed in $PREFIX." \
            "py-words no está instalado en $PREFIX."
        exit 0
    fi
    is_ours "$PREFIX" || die \
        "$PREFIX was not made by this installer; nothing removed" \
        "$PREFIX no lo hizo este instalador; no se quitó nada"
    ask "Remove py-words from $PREFIX?" "¿Quitar py-words de $PREFIX?" || exit 1
    remove_installed
    refresh_menu
    say "Removed py-words." "Se quitó py-words."
    if [ -n "$PURGE" ]; then
        purge
    elif [ -z "$YES" ] && [ -z "$SYSTEM" ] && [ -t 0 ]; then
        if ask "Remove also your settings, history and cache of py-words?" \
               "¿Quitar también sus ajustes, historial y caché de py-words?"; then
            purge
        fi
    fi
}

do_install() {
    check
    if [ -e "$PREFIX" ] && ! is_ours "$PREFIX"; then
        if [ -d "$PREFIX" ] && [ -z "$(ls -A -- "$PREFIX")" ]; then
            :
        else
            die "$PREFIX exists and was not made by this installer; choose another --prefix" \
                "$PREFIX existe y no lo hizo este instalador; elija otro --prefix"
        fi
    fi
    if [ -n "$SYSTEM" ]; then
        say "py-words $VERSION will be installed for everyone:" \
            "py-words $VERSION se instalará para todos:"
    else
        say "py-words $VERSION will be installed for $(id -un 2>/dev/null || echo you):" \
            "py-words $VERSION se instalará para $(id -un 2>/dev/null || echo usted):"
    fi
    say "  program:      $PREFIX" "  programa:     $PREFIX"
    [ -n "$COMMAND" ] && say "  command:      $BINDIR/py-words" \
                             "  orden:        $BINDIR/py-words"
    [ -n "$MENU" ] && say "  menu entries: $APPS" "  menú:         $APPS"
    if is_ours "$PREFIX"; then
        say "(it replaces the py-words that is there)" \
            "(reemplaza el py-words que hay allí)"
    fi
    ask "Go on?" "¿Seguir?" || exit 1

    # Se desempaca al lado y se cambia al final, para no dejar a medias
    # una instalación que ya funcionaba
    parent=$(dirname -- "$PREFIX")
    mkdir -p -- "$parent" || die "cannot make $parent" "no se puede crear $parent"
    new=$parent/.py-words-new.$$
    trap 'chmod -R u+w -- "$new" 2>/dev/null; rm -rf -- "$new"' EXIT
    trap 'exit 1' INT TERM
    unpack "$new"
    if is_ours "$PREFIX"; then
        remove_installed
    elif [ -d "$PREFIX" ]; then
        rmdir -- "$PREFIX"
    fi
    mv -- "$new" "$PREFIX" || die "cannot make $PREFIX" "no se puede crear $PREFIX"
    trap - EXIT INT TERM
    : > "$MANIFEST"

    if [ -n "$COMMAND" ]; then
        mkdir -p -- "$BINDIR" || die "cannot make $BINDIR" "no se puede crear $BINDIR"
        if [ -e "$BINDIR/py-words" ] && [ ! -L "$BINDIR/py-words" ]; then
            say "Warning: $BINDIR/py-words is not a link of py-words; it was left as it is." \
                "Aviso: $BINDIR/py-words no es un enlace de py-words; se dejó como estaba." >&2
        else
            ln -sf -- "$PREFIX/bin/py-words" "$BINDIR/py-words"
            record "$BINDIR/py-words"
        fi
    fi

    if [ -n "$MENU" ]; then
        mkdir -p -- "$APPS"
        entry "$APPS/$APP_ID.desktop" 'py-words (GUI)' gui false
        for command in cli tui web; do
            file=$APPS/$APP_ID.$command.desktop
            if [ -n "$ONLY_GUI" ]; then
                rm -f -- "$file"
            else
                case $command in
                    web) kind=Web ;;
                    *) kind=$(echo "$command" | tr '[:lower:]' '[:upper:]') ;;
                esac
                entry "$file" "py-words ($kind)" "$command" true
            fi
        done
        icons=$PREFIX/program/icons/linux/icons/hicolor
        for icon in "$icons"/*/apps/"$APP_ID".png "$icons"/*/apps/"$APP_ID".svg; do
            [ -f "$icon" ] || continue
            rel=${icon#"$icons"/}
            mkdir -p -- "$ICONS/${rel%/*}"
            cp -f -- "$icon" "$ICONS/$rel"
            record "$ICONS/$rel"
        done
        refresh_menu
    fi

    # El desinstalador: este mismo script, sin el contenido
    head -n "$((PAYLOAD_LINE - 1))" -- "$SELF" | \
        sed -e "s|^PAYLOAD_LINE=.*|PAYLOAD_LINE=0|" \
            -e "s|^ACTION=install\$|ACTION=uninstall|" \
            -e "s|^PREFIX=\$|PREFIX='$(printf '%s' "$PREFIX" | sed "s/'/'\\\\''/g")'|" \
        > "$PREFIX/uninstall.sh"
    chmod 755 "$PREFIX/uninstall.sh"

    say "Installed py-words $VERSION." "Se instaló py-words $VERSION."
    if [ -n "$COMMAND" ]; then
        case ":$PATH:" in
            *":$BINDIR:"*) ;;
            *) say "Note: $BINDIR is not in your PATH; add it, or run $PREFIX/bin/py-words." \
                   "Nota: $BINDIR no está en su PATH; añádala, o corra $PREFIX/bin/py-words." ;;
        esac
        say "  py-words              the window" \
            "  py-words              la ventana"
        say "  py-words cli amicus   the command line" \
            "  py-words cli amicus   la línea de órdenes"
        say "  py-words help         the other programs" \
            "  py-words help         los demás programas"
        say "  py-words uninstall    remove it" \
            "  py-words uninstall    quitarlo"
    fi
}

case $ACTION in
    check) do_check ;;
    extract) do_extract ;;
    uninstall) do_uninstall ;;
    *)
        [ "$PAYLOAD_LINE" -gt 0 ] || die "this is the uninstaller; give --uninstall" \
                                         "este es el desinstalador; dé --uninstall"
        do_install ;;
esac
exit 0
