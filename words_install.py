#!/usr/bin/env python3
"""Add py-words to the applications menu: python3 words_install.py
[--uninstall]

Adds two entries that start the program from this folder, one for the
window (words_gui.py) and one for the command line (words.py, in a
terminal), with the program's icon:

* Linux and other freedesktop systems: .desktop files and the icons in the
  user's data folder ($XDG_DATA_HOME, usually ~/.local/share);
* Windows: shortcuts in the user's Start menu (made with PowerShell);
* macOS: two small applications in ~/Applications.

Everything goes in the user's own folders, so no administrator rights are
needed.  Run it again after moving this folder; --uninstall removes
everything it added.
"""

import argparse
import os
import plistlib
import shlex
import shutil
import struct
import subprocess
import sys
from typing import NamedTuple

from version import VERSION

APP_ID = 'py-whitaker-words'             # the names of the entries and icons
BUNDLE_ID = 'io.github.nivaca.py-whitaker-words'
NAME = 'Py-Whitaker-Words (%s)'          # the name shown, with GUI or CLI
COMMENT = 'Latin Dictionary'
HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(HERE, 'icons')

#  (kind, program, whether it runs in a terminal)
PROGRAMS = (('GUI', 'words_gui.py', False),
            ('CLI', 'words.py', True))


# ---------------------------------------------------------------------------
#  Linux and other freedesktop systems

HICOLOR = os.path.join(ICON_DIR, 'linux', 'icons', 'hicolor')

ENTRY = """[Desktop Entry]
Type=Application
Version=1.0
Name={name}
Comment={comment}
Keywords=dictionary;Latin;
Categories=Education;
Icon={app_id}
Exec={exec}
"""

#  The lines that differ, by kind
ENTRY_REST = {
    'GUI': 'Terminal=false\nStartupNotify=true\nStartupWMClass=%s\n' % APP_ID,
    'CLI': 'Terminal=true\n',
}

#  The file names of the entries, by kind
ENTRY_FILES = {'GUI': APP_ID + '.desktop', 'CLI': APP_ID + '.cli.desktop'}


def data_home():
    return os.environ.get('XDG_DATA_HOME') or \
        os.path.join(os.path.expanduser('~'), '.local', 'share')


def entry_path(kind):
    return os.path.join(data_home(), 'applications', ENTRY_FILES[kind])


def exec_arg(arg):
    """ARG quoted for an Exec line, as the desktop entry specification
    requires when it has spaces or special characters."""
    if arg and not any(c in arg for c in ' \t\n"\'\\><~|&;$*?#()`'):
        return arg
    for c in '\\"`$':
        arg = arg.replace(c, '\\' + c)
    return '"%s"' % arg


def icon_files():
    """(source, path relative to the hicolor theme) for each icon."""
    if not os.path.isdir(HICOLOR):
        return []
    found = []
    for size in sorted(os.listdir(HICOLOR)):
        apps = os.path.join(HICOLOR, size, 'apps')
        for name in (APP_ID + '.png', APP_ID + '.svg'):
            if os.path.isfile(os.path.join(apps, name)):
                found.append((os.path.join(apps, name),
                              os.path.join(size, 'apps', name)))
    return found


def refresh_linux():
    """Tells the desktop about the change (each tool only if present)."""
    for command in (['update-desktop-database',
                     os.path.join(data_home(), 'applications')],
                    ['gtk-update-icon-cache', '-f', '-t', '-q',
                     os.path.join(data_home(), 'icons', 'hicolor')],
                    ['kbuildsycoca6'], ['kbuildsycoca5']):
        if shutil.which(command[0]):
            subprocess.run(command, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=False)
            if command[0] == 'kbuildsycoca6':
                break


def install_linux() -> list[str]:
    theme = os.path.join(data_home(), 'icons', 'hicolor')
    for source, rel in icon_files():
        dest = os.path.join(theme, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.lexists(dest):
            os.remove(dest)             # (it may be read-only)
        shutil.copyfile(source, dest)
    paths = []
    for kind, program, _ in PROGRAMS:
        command = [sys.executable, os.path.join(HERE, program)]
        path = entry_path(kind)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(ENTRY.format(name=NAME % kind, comment=COMMENT,
                                 app_id=APP_ID, exec=' '.join(
                                     exec_arg(a) for a in command)))
            f.write(ENTRY_REST[kind])
        os.chmod(path, 0o755)
        paths.append(path)
    refresh_linux()
    return paths


def uninstall_linux() -> list[str]:
    removed = []
    theme = os.path.join(data_home(), 'icons', 'hicolor')
    paths = [os.path.join(theme, rel) for _, rel in icon_files()] + \
        [entry_path(kind) for kind, _, _ in PROGRAMS]
    for path in paths:
        if os.path.isfile(path):
            os.remove(path)
            removed.append(path)
    refresh_linux()
    return removed


# ---------------------------------------------------------------------------
#  Windows

ICO = os.path.join(ICON_DIR, 'windows', APP_ID + '.ico')

#  Makes a shortcut with the Windows Script Host, from the values in the
#  environment (which spares quoting them in the script).
SHORTCUT_SCRIPT = (
    '$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:PYW_LNK);'
    ' $s.TargetPath = $env:PYW_TARGET;'
    ' $s.Arguments = $env:PYW_ARGS;'
    ' $s.WorkingDirectory = $env:PYW_DIR;'
    ' $s.Description = $env:PYW_COMMENT;'
    ' if ($env:PYW_ICON) { $s.IconLocation = $env:PYW_ICON };'
    ' $s.Save()')


class Shortcut(NamedTuple):
    path: str               # the .lnk file
    target: str             # the Python that runs the program
    arguments: str
    folder: str             # where it runs
    icon: str               # "file,index", or ''


def start_menu():
    appdata = os.environ.get('APPDATA') or \
        os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming')
    return os.path.join(appdata, 'Microsoft', 'Windows', 'Start Menu',
                        'Programs')


def windows_shortcuts() -> list[Shortcut]:
    """The shortcuts: the window runs with pythonw.exe, which opens no
    console; the command line with python.exe, which opens one."""
    folder = os.path.dirname(sys.executable)
    pythonw = os.path.join(folder, 'pythonw.exe')
    icon = ICO + ',0' if os.path.isfile(ICO) else ''
    shortcuts = []
    for kind, program, terminal in PROGRAMS:
        target = sys.executable if terminal or not os.path.isfile(pythonw) \
            else pythonw
        shortcuts.append(Shortcut(
            os.path.join(start_menu(), NAME % kind + '.lnk'), target,
            '"%s"' % os.path.join(HERE, program), HERE, icon))
    return shortcuts


def install_windows() -> list[str]:
    paths = []
    for s in windows_shortcuts():
        os.makedirs(os.path.dirname(s.path), exist_ok=True)
        env = dict(os.environ, PYW_LNK=s.path, PYW_TARGET=s.target,
                   PYW_ARGS=s.arguments, PYW_DIR=s.folder, PYW_ICON=s.icon,
                   PYW_COMMENT=COMMENT)
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command',
             SHORTCUT_SCRIPT], env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False)
        if result.returncode != 0 or not os.path.isfile(s.path):
            raise OSError('could not make the shortcut %s: %s' % (
                s.path, result.stdout.decode(errors='replace').strip()))
        paths.append(s.path)
    return paths


def uninstall_windows() -> list[str]:
    removed = []
    for s in windows_shortcuts():
        if os.path.isfile(s.path):
            os.remove(s.path)
            removed.append(s.path)
    return removed


# ---------------------------------------------------------------------------
#  macOS

ICONSET = os.path.join(ICON_DIR, 'macos', APP_ID + '.iconset')

#  The icon types of an .icns file, by the name of the iconset image
ICNS_TYPES = (('icp4', '16x16'), ('ic11', '16x16@2x'),
              ('icp5', '32x32'), ('ic12', '32x32@2x'),
              ('ic07', '128x128'), ('ic13', '128x128@2x'),
              ('ic08', '256x256'), ('ic14', '256x256@2x'),
              ('ic09', '512x512'), ('ic10', '512x512@2x'))


def make_icns(iconset: str) -> bytes:
    """An .icns file holding the PNG images of ICONSET (a folder of
    icon_16x16.png, icon_16x16@2x.png ...), as iconutil would make it;
    b'' if there are none."""
    chunks = b''
    for kind, size in ICNS_TYPES:
        path = os.path.join(iconset, 'icon_%s.png' % size)
        if os.path.isfile(path):
            with open(path, 'rb') as f:
                png = f.read()
            chunks += kind.encode('ascii') + struct.pack('>I', len(png) + 8) \
                + png
    if not chunks:
        return b''
    return b'icns' + struct.pack('>I', len(chunks) + 8) + chunks


def applications_dir():
    return os.path.join(os.path.expanduser('~'), 'Applications')


def app_path(kind):
    return os.path.join(applications_dir(), NAME % kind + '.app')


def is_ours(app: str) -> bool:
    """Whether APP is an application this script made."""
    try:
        with open(os.path.join(app, 'Contents', 'Info.plist'), 'rb') as f:
            info = plistlib.load(f)
    except (OSError, ValueError, plistlib.InvalidFileException):
        return False
    return str(info.get('CFBundleIdentifier', '')).startswith(BUNDLE_ID)


def write_script(path: str, text: str):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.chmod(path, 0o755)


def make_app(kind: str, program: str, terminal: bool, icns: bytes) -> str:
    """APP.app/Contents/{Info.plist, MacOS/<launcher>, Resources/...}.  The
    launcher runs the program, or, for the command line, opens it in
    Terminal (with a .command file)."""
    app = app_path(kind)
    if os.path.exists(app):
        if not is_ours(app):
            raise OSError('%s exists and was not made by words_install.py; '
                          'move it away first' % app)
        shutil.rmtree(app)
    contents = os.path.join(app, 'Contents')
    macos = os.path.join(contents, 'MacOS')
    resources = os.path.join(contents, 'Resources')
    os.makedirs(macos)
    os.makedirs(resources)
    run = 'exec %s %s\n' % (shlex.quote(sys.executable),
                            shlex.quote(os.path.join(HERE, program)))
    launcher = os.path.join(macos, APP_ID)
    if terminal:
        write_script(os.path.join(resources, 'run.command'),
                     '#!/bin/sh\ncd %s\nclear\n%s' % (shlex.quote(HERE), run))
        write_script(launcher, '#!/bin/sh\nexec open -a Terminal '
                               '"$(dirname "$0")/../Resources/run.command"\n')
    else:
        write_script(launcher, '#!/bin/sh\ncd %s\n%s'
                     % (shlex.quote(HERE), run))
    info = {
        'CFBundleName': NAME % kind,
        'CFBundleDisplayName': NAME % kind,
        'CFBundleIdentifier': BUNDLE_ID + '.' + kind.lower(),
        'CFBundleExecutable': APP_ID,
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': VERSION,
        'CFBundleInfoDictionaryVersion': '6.0',
        'LSApplicationCategoryType': 'public.app-category.education',
        'NSHighResolutionCapable': True,
    }
    if icns:
        with open(os.path.join(resources, APP_ID + '.icns'), 'wb') as f:
            f.write(icns)
        info['CFBundleIconFile'] = APP_ID
    with open(os.path.join(contents, 'Info.plist'), 'wb') as f:
        plistlib.dump(info, f)
    return app


def install_macos() -> list[str]:
    icns = make_icns(ICONSET)
    os.makedirs(applications_dir(), exist_ok=True)
    apps = [make_app(kind, program, terminal, icns)
            for kind, program, terminal in PROGRAMS]
    for app in apps:
        os.utime(app)                   # (so that Finder shows the icon)
    return apps


def uninstall_macos() -> list[str]:
    removed = []
    for kind, _, _ in PROGRAMS:
        app = app_path(kind)
        if os.path.isdir(app) and is_ours(app):
            shutil.rmtree(app)
            removed.append(app)
    return removed


# ---------------------------------------------------------------------------

def system(platform=None) -> str:
    platform = platform or sys.platform
    if platform == 'win32':
        return 'windows'
    if platform == 'darwin':
        return 'macos'
    return 'linux'


def install() -> list[str]:
    return {'linux': install_linux, 'windows': install_windows,
            'macos': install_macos}[system()]()


def uninstall() -> list[str]:
    return {'linux': uninstall_linux, 'windows': uninstall_windows,
            'macos': uninstall_macos}[system()]()


WHERE = {'linux': 'the applications menu', 'windows': 'the Start menu',
         'macos': 'Applications (in your home folder)'}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='words_install.py',
        description='Add py-words to the applications menu, or remove it.')
    parser.add_argument('--uninstall', action='store_true',
                        help='remove what was added')
    args = parser.parse_args(argv)
    try:
        if args.uninstall:
            removed = uninstall()
            print('Removed py-words from %s.' % WHERE[system()] if removed
                  else 'There was nothing to remove.')
            return
        paths = install()
    except OSError as e:
        sys.exit('words_install.py: %s' % e)
    print('Added py-words to %s:' % WHERE[system()])
    for path in paths:
        print('  ' + path)
    print('If you move this folder, run this again.')


if __name__ == '__main__':
    main()
