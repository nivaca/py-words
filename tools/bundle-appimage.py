#!/usr/bin/env python3
"""Makes an AppImage of the program, for Linux:
python3 tools/bundle-appimage.py

The AppImage is dist/py-words-v.VERSION-x86_64.AppImage (the version of
version.py; dist is made in the program's folder if need be, and --output
gives another folder).  It holds a Python of its own, with Tk (a relocatable Python
of the python-appimage project, https://github.com/niess/python-appimage),
and the program as bundle-zip.py puts it in the zip, so it runs on any
Linux of the last ten years or so, without installing anything.

It starts the window (words_gui.py); a first argument chooses another of
the programs:

    py-words.AppImage [gui|cli|tui|web|edit|edit-gui|check|convert] ...

and so does the name it is called by, if it is a link named words,
words_tui, words_web ... (as the programs, without .py).  "help" lists
them.  The AppImage cannot be written to: to edit the dictionary, copy the
data folder somewhere and give it as the data folder (in the settings, or
with --datadir or $PY_WORDS_DATADIR).

What it needs is downloaded the first time, and kept in the user's cache
folder (~/.cache/py-words-build): the Python and appimagetool
(https://github.com/AppImage/appimagetool).  --python and --appimagetool
give them instead.
"""

import os
import sys

#  The program's folder (this script is in its tools/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from version import check_python  # noqa: E402
check_python()          # (before the modules that need it)

import argparse
import glob
import importlib.util
import json
import shutil
import stat
import subprocess
import tempfile
import urllib.request

import interface
from interface import tr
from version import COMMIT_FILE, NAME, VERSION

#  Where the AppImage goes, unless --output says otherwise
DIST = os.path.join(ROOT, 'dist')
APP_ID = 'py-words'
ARCH = 'x86_64'

#  The Python put in the AppImage (python-appimage has one release per
#  version, with an AppImage per manylinux; the older the manylinux, the
#  older the systems it runs on)
PYTHON = '3.13'
PYTHON_RELEASES = 'https://api.github.com/repos/niess/python-appimage/' \
    'releases/tags/python{version}'
MANYLINUX = ('manylinux2014', 'manylinux_2_28')
APPIMAGETOOL = 'https://github.com/AppImage/appimagetool/releases/' \
    f'download/continuous/appimagetool-{ARCH}.AppImage'

#  What is not for the AppImage: the installer of menu entries (they would
#  point inside the AppImage, which is mounted somewhere else each time).
#  (What makes the bundles, in tools/, is not in the zip either.)
NOT_IN_IMAGE = ('words_install.py',)

#  The programs: (command, program)
COMMANDS = (('gui', 'words_gui.py'),
            ('cli', 'words.py'),
            ('tui', 'words_tui.py'),
            ('web', 'words_web.py'),
            ('edit', 'words_edit.py'),
            ('edit-gui', 'words_edit_gui.py'),
            ('check', 'words_check.py'),
            ('convert', 'words_convert.py'))

DESKTOP = f"""[Desktop Entry]
Type=Application
Name={NAME}
Comment=Latin Dictionary
Comment[es]=Diccionario latino
Keywords=dictionary;Latin;
Categories=Education;
Icon={APP_ID}
Exec={APP_ID}
Terminal=false
StartupNotify=true
StartupWMClass={APP_ID}
"""

#  {python}: the interpreter, relative to the AppDir
APPRUN = r"""#!/bin/bash
#  Starts py-words in the AppImage (made by tools/bundle-appimage.py).
ROOT="$(dirname "$(readlink -f -- "$0")")"
export APPDIR="${APPDIR:-$ROOT}"
PROGRAM="$APPDIR/opt/py-words"
SELF="${ARGV0:-$0}"

#  The Tcl/Tk and certificates of the Python of the AppImage
for d in "$APPDIR"/usr/share/tcltk/tcl8* "$APPDIR"/usr/share/tcltk/tcl9*; do
    [ -d "$d" ] && export TCL_LIBRARY="$d"
done
for d in "$APPDIR"/usr/share/tcltk/tk8* "$APPDIR"/usr/share/tcltk/tk9*; do
    [ -d "$d" ] && export TK_LIBRARY="$d" TKPATH="$d"
done
for f in "$APPDIR"/opt/python*/lib/python*/site-packages/certifi/cacert.pem; do
    [ -f "$f" ] && export SSL_CERT_FILE="${SSL_CERT_FILE:-$f}"
done
#  (the AppImage cannot be written to)
export PYTHONDONTWRITEBYTECODE=1

usage() {
    echo "Usage: ${SELF##*/} [COMMAND] [ARGUMENTS ...]"
    echo
    echo "Commands (gui if none is given):"
%(usage)s
    echo
    echo "\"${SELF##*/} COMMAND --help\" tells what each one takes."
}

program() {
    case "$1" in
%(cases)s
        *) return 1 ;;
    esac
}

#  A link named after a program runs it; otherwise the first argument says
#  which, or the window
name="$(basename -- "$SELF")"
name="${name%%.py}"
if script="$(program "$name")"; then
    :
elif [ "$1" = help ]; then
    usage
    exit 0
elif script="$(program "$1")"; then
    shift
else
    script=words_gui.py
fi
exec "$APPDIR/%(python)s" "$PROGRAM/$script" "$@"
"""


def name() -> str:
    """The name of the AppImage: py-words-v.3.7-x86_64.AppImage."""
    return f'py-words-v.{VERSION}-{ARCH}.AppImage'


def bundle_zip():
    """The module bundle-zip.py, whose list of files is used."""
    spec = importlib.util.spec_from_file_location(
        'bundle_zip', os.path.join(ROOT, 'tools', 'bundle-zip.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def files() -> list[str]:
    """The files of the program in the AppImage, relative to its folder."""
    return [f for f in bundle_zip().files() if f not in NOT_IN_IMAGE]


def cache_dir() -> str:
    """Where the downloads are kept."""
    base = os.environ.get('XDG_CACHE_HOME') or \
        os.path.join(os.path.expanduser('~'), '.cache')
    path = os.path.join(base, 'py-words-build')
    os.makedirs(path, exist_ok=True)
    return path


def download(url: str, path: str) -> str:
    """Downloads URL into PATH (unless it is there already); returns
    PATH."""
    if not os.path.isfile(path):
        print(tr('Downloading {url} ...', url=url), file=sys.stderr)
        tmp = path + '.tmp'
        with urllib.request.urlopen(url, timeout=60) as r, \
                open(tmp, 'wb') as f:
            shutil.copyfileobj(r, f)
        os.replace(tmp, path)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def python_url(version: str) -> str:
    """The URL of the Python AppImage of VERSION (3.13 ...), for the
    oldest manylinux there is one for."""
    url = PYTHON_RELEASES.format(version=version)
    request = urllib.request.Request(
        url, headers={'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=60) as r:
        assets = json.load(r)['assets']
    tag = 'cp' + version.replace('.', '')
    for manylinux in MANYLINUX:
        #  (not those of the Python without the GIL, cp313t)
        end = f'-{tag}-{tag}-{manylinux}_{ARCH}.AppImage'
        found = [a['browser_download_url'] for a in assets
                 if a['name'].endswith(end)]
        if found:
            return found[0]
    raise OSError(tr('there is no Python {version} AppImage at {url}',
                     version=version, url=url))


def python_appimage(version: str) -> str:
    """The Python AppImage of VERSION, downloaded if need be."""
    url = python_url(version)
    return download(url, os.path.join(cache_dir(), url.rsplit('/', 1)[1]))


def extract(appimage: str, folder: str) -> str:
    """Extracts APPIMAGE into FOLDER; returns its AppDir."""
    subprocess.run([os.path.abspath(appimage), '--appimage-extract'],
                   cwd=folder, check=True, stdout=subprocess.DEVNULL)
    return os.path.join(folder, 'squashfs-root')


def make_appdir(appdir: str, commit: str | None):
    """Turns the AppDir of the Python into that of py-words."""
    pythons = sorted(glob.glob(os.path.join(
        appdir, 'opt', 'python3*', 'bin', 'python3.*')))
    pythons = [p for p in pythons if not p.endswith('-config')]
    if not pythons:
        raise OSError(tr('there is no Python in {path}', path=appdir))
    python = os.path.relpath(pythons[0], appdir)
    #  Out with what makes it the Python's AppImage
    for pattern in ('AppRun', '*.desktop', '*.png', '*.svg', '.DirIcon',
                    'usr/share/applications', 'usr/share/metainfo'):
        for path in glob.glob(os.path.join(appdir, pattern)):
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
    #  The program
    program = os.path.join(appdir, 'opt', APP_ID)
    for f in files():
        target = os.path.join(program, f)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, f), target)
    if commit:
        with open(os.path.join(program, COMMIT_FILE), 'w',
                  encoding='ascii') as f:
            f.write(commit + '\n')
    #  How to start it, its menu entry and its icon
    width = max(len(c) for c, _ in COMMANDS)
    usage = '\n'.join(f'    echo "  {c.ljust(width)}  {p}"'
                      for c, p in COMMANDS)
    cases = '\n'.join(f'        {c}|{p[:-3]}) echo {p} ;;'
                      for c, p in COMMANDS)
    apprun = os.path.join(appdir, 'AppRun')
    with open(apprun, 'w', encoding='utf-8', newline='\n') as f:
        f.write(APPRUN % {'usage': usage, 'cases': cases, 'python': python})
    os.chmod(apprun, 0o755)
    with open(os.path.join(appdir, APP_ID + '.desktop'), 'w',
              encoding='utf-8', newline='\n') as f:
        f.write(DESKTOP)
    #  (a PNG: appimagetool wants one for .DirIcon, as file managers do)
    shutil.copy2(os.path.join(ROOT, 'icons', 'linux', 'icons', 'hicolor',
                              '256x256', 'apps', APP_ID + '.png'),
                 os.path.join(appdir, APP_ID + '.png'))
    os.symlink(APP_ID + '.png', os.path.join(appdir, '.DirIcon'))
    hicolor = os.path.join(ROOT, 'icons', 'linux', 'icons', 'hicolor')
    if os.path.isdir(hicolor):
        shutil.copytree(hicolor,
                        os.path.join(appdir, 'usr', 'share', 'icons',
                                     'hicolor'), dirs_exist_ok=True)


def open_to_all(appdir: str):
    """Lets everyone read the AppDir: folders 0755, files 0644, or 0755 if
    they can be run.  (Folders of the Python come out 0700, and whoever
    runs the AppImage could not read them.)"""
    def fix(path, mode):
        if not os.path.islink(path):
            os.chmod(path, mode)
    fix(appdir, 0o755)
    for folder, dirs, names in os.walk(appdir):
        for d in dirs:
            fix(os.path.join(folder, d), 0o755)
        for n in names:
            path = os.path.join(folder, n)
            if not os.path.islink(path):
                runs = os.stat(path).st_mode & stat.S_IXUSR
                fix(path, 0o755 if runs else 0o644)


def bundle(output: str, python: str | None = None,
           appimagetool: str | None = None,
           version: str = PYTHON) -> str:
    """Writes the AppImage into OUTPUT; returns its path."""
    python = python or python_appimage(version)
    appimagetool = appimagetool or download(
        APPIMAGETOOL, os.path.join(cache_dir(), os.path.basename(
            APPIMAGETOOL)))
    path = os.path.join(output, name())
    with tempfile.TemporaryDirectory() as tmp:
        appdir = extract(python, tmp)
        make_appdir(appdir, bundle_zip().built_from())
        open_to_all(appdir)
        #  (without FUSE, as in a container, the tool runs extracted)
        env = dict(os.environ, ARCH=ARCH, APPIMAGE_EXTRACT_AND_RUN='1')
        subprocess.run([os.path.abspath(appimagetool), '--no-appstream',
                        appdir, path + '.tmp'], check=True, env=env)
    os.replace(path + '.tmp', path)
    return path


def main(argv=None):
    interface.use_configured()
    interface.translate_argparse()
    parser = argparse.ArgumentParser(
        prog='tools/bundle-appimage.py',
        description=tr('Make an AppImage of the program, for Linux: '
                       '{name}, with a Python of its own.', name=name()))
    parser.add_argument('-o', '--output', metavar=tr('FOLDER'),
                        default=None,
                        help=tr('the folder to write it in (default: dist, '
                                "in the program's folder)"))
    parser.add_argument('--python', metavar=tr('APPIMAGE'),
                        help=tr('the Python AppImage to use (default: one '
                                'of python-appimage, downloaded)'))
    parser.add_argument('--python-version', metavar=tr('VERSION'),
                        default=PYTHON,
                        help=tr('the version of Python to download '
                                '(default: {version})', version=PYTHON))
    parser.add_argument('--appimagetool', metavar=tr('APPIMAGE'),
                        help=tr('the appimagetool to use (default: '
                                'downloaded)'))
    args = parser.parse_args(argv)
    if not sys.platform.startswith('linux'):
        sys.exit('bundle-appimage.py: ' + tr('AppImages are made on Linux'))
    if args.output is None:
        args.output = DIST
        os.makedirs(DIST, exist_ok=True)
    elif not os.path.isdir(args.output):
        sys.exit('bundle-appimage.py: ' + tr('there is no folder {folder}',
                                             folder=args.output))
    try:
        path = bundle(args.output, args.python, args.appimagetool,
                      args.python_version)
    except (OSError, subprocess.CalledProcessError, ValueError,
            KeyError) as e:
        sys.exit(f'bundle-appimage.py: {e}')
    print(tr('Wrote {path} ({size:.1f} MB).', path=path,
             size=os.path.getsize(path) / 1e6))


if __name__ == '__main__':
    main()
