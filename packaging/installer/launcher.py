# py-words, a Latin dictionary and parser.
# Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENCE.txt file, or <https://www.gnu.org/licenses/>.
"""Inicia py-words tal como lo dejan sus instaladores (Windows, macOS y
Linux; tools/bundle-installer.py), con las mismas órdenes que el AppImage,
el RPM y el .deb:

    py-words [gui|cli|tui|web|edit|edit-gui|check|convert] [ARGUMENTOS ...]
    py-words help | uninstall

Está en la carpeta de la instalación, junto a python/ (el Python propio)
y program/ (el programa).  Lo corre ese Python: en Windows, bin/py-words.cmd;
en Linux y macOS, bin/py-words.  Antes de pasar al programa le prepara el
entorno: el Tcl/Tk del Python propio y, si el sistema no los ofrece, los
certificados de certifi (para Logeion).
"""

import glob
import os
import ssl
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.join(HERE, 'program')
WINDOWS = sys.platform == 'win32'

#  The programs: (command, script)
COMMANDS = (('gui', 'words_gui.py'),
            ('cli', 'words.py'),
            ('tui', 'words_tui.py'),
            ('web', 'words_web.py'),
            ('edit', 'words_edit.py'),
            ('edit-gui', 'words_edit_gui.py'),
            ('check', 'words_check.py'),
            ('convert', 'words_convert.py'))

#  Los desinstaladores que pueden estar junto a este archivo
UNINSTALLERS = ('uninstall.sh', 'unins000.exe')


def usage() -> str:
    width = max(len(c) for c, _ in COMMANDS)
    lines = ['Usage: py-words [COMMAND] [ARGUMENTS ...]', '',
             'Commands (gui if none is given):']
    lines += [f'  {c.ljust(width)}  {s}' for c, s in COMMANDS]
    lines += ['', f'  {"help".ljust(width)}  this list',
              f'  {"uninstall".ljust(width)}  remove py-words', '',
              '"py-words COMMAND --help" tells what each one takes.']
    return '\n'.join(lines)


def tcl_tk(env: dict) -> None:
    """Points Tcl and Tk to the libraries of the bundled Python, unless
    the environment already says where they are.  (On Windows, Python
    finds them by itself.)"""
    if WINDOWS:
        return
    lib = os.path.join(sys.base_prefix, 'lib')
    for name, script, variable in (('tcl', 'init.tcl', 'TCL_LIBRARY'),
                                   ('tk', 'tk.tcl', 'TK_LIBRARY')):
        if env.get(variable):
            continue
        #  (tcl8.6, tcl9.0 ...: el más nuevo que tenga su script)
        found = [d for d in sorted(glob.glob(os.path.join(lib, name + '[89].*')))
                 if os.path.isfile(os.path.join(d, script))]
        if found:
            env[variable] = found[-1]


def certificates(env: dict) -> None:
    """Gives OpenSSL the certificates of certifi when the system's are not
    where the bundled Python looks for them (the bundled OpenSSL does not
    know every system's layout).  Windows uses its own store."""
    if WINDOWS or env.get('SSL_CERT_FILE') or env.get('SSL_CERT_DIR'):
        return
    paths = ssl.get_default_verify_paths()
    if paths.cafile and os.path.isfile(paths.cafile):
        return
    if paths.capath and os.path.isdir(paths.capath) and os.listdir(paths.capath):
        return
    try:
        import certifi
    except ImportError:
        return
    env['SSL_CERT_FILE'] = certifi.where()


def uninstall(args: list[str]) -> int:
    """Runs the uninstaller that the installer left beside this file."""
    for name in UNINSTALLERS:
        path = os.path.join(HERE, name)
        if os.path.isfile(path):
            command = (['/bin/sh', path] if name.endswith('.sh')
                       else [path]) + args
            return subprocess.call(command)
    print('py-words: there is no uninstaller in ' + HERE, file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    scripts = dict(COMMANDS)
    if sys.platform == 'darwin':
        #  (las versiones viejas de macOS pasan -psn_... a las aplicaciones)
        argv = [a for a in argv if not a.startswith('-psn_')]
    if argv and argv[0] in ('help', '--help', '-h'):
        print(usage())
        return 0
    if argv and argv[0] == 'uninstall':
        return uninstall(argv[1:])
    if argv and argv[0] in scripts:
        script, argv = scripts[argv[0]], argv[1:]
    else:
        script = 'words_gui.py'
    env = dict(os.environ)
    tcl_tk(env)
    certificates(env)
    command = [sys.executable, os.path.join(PROGRAM, script), *argv]
    if not WINDOWS:
        os.execve(sys.executable, command, env)
    #  En Windows, execv crea otro proceso y la consola recupera el control
    #  antes de tiempo: hay que esperarlo
    try:
        return subprocess.call(command, env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
