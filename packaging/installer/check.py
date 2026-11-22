# py-words, a Latin dictionary and parser.
# Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENCE.txt file, or <https://www.gnu.org/licenses/>.
"""Comprueba, con el Python de una instalación de py-words hecha por uno
de sus instaladores, lo que el programa necesita de ese Python:

    CARPETA/python/bin/python3 check.py CARPETA [--no-network]

(en Windows, CARPETA\\python\\python.exe).  Prepara el entorno como
launcher.py y prueba Tcl (sin pantalla: no abre ninguna ventana), curses
y, salvo con --no-network, una conexión HTTPS como las de Logeion.  Lo
usa .github/workflows/installers.yml tras instalar cada uno.
"""

import os
import sys


def main(argv: list[str]) -> int:
    if not argv:
        print('Usage: python check.py FOLDER [--no-network]',
              file=sys.stderr)
        return 2
    root = os.path.abspath(argv[0])
    sys.path.insert(0, root)
    import launcher
    env = dict(os.environ)
    launcher.tcl_tk(env)
    launcher.certificates(env)
    os.environ.update(env)
    failed = 0

    def check(what, test):
        nonlocal failed
        try:
            result = test()
        except Exception as e:      # (cualquier fallo cuenta)
            failed += 1
            print(f'FAILED  {what}: {type(e).__name__}: {e}')
        else:
            print(f'ok      {what}: {result}')

    check('Python', lambda: f'{sys.version.split()[0]} in {sys.base_prefix}')
    check('Tcl', lambda: __import__('tkinter').Tcl().eval('info patchlevel'))
    check('curses', lambda: __import__('curses').__name__)
    def program():
        path = os.path.join(root, 'program', 'words.py')
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        return path
    check('the program', program)
    if '--no-network' not in argv:
        def https():
            import urllib.request
            with urllib.request.urlopen('https://github.com',
                                        timeout=30) as r:
                return f'HTTP {r.status}'
        check('HTTPS', https)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
