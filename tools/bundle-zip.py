#!/usr/bin/env python3
"""Hace un zip del programa, para distribuirlo:
python3 tools/bundle-zip.py

El zip es dist/py-words-v.VERSION.zip (la versión de version.py; dist se
crea en la carpeta del programa si hace falta, y --output da otra
carpeta), con el programa en una carpeta del mismo nombre.  Lleva los
programas, los datos, los íconos y los documentos, pero no los archivos ni
las carpetas ocultos (.git ...), ni lo que se produce mientras el programa
corre o se edita (__pycache__, archivos .bak y .tmp, WORD.OUT ...), ni lo
que está en su carpeta sin ser parte de él (local-only/, tools/,
packaging/, build/, dist/, los TAGS de un editor).  Las pruebas quedan
fuera, salvo que --tests diga otra cosa.  Lleva también COMMIT, el commit
del que se hizo (para "About").
"""

import os
import sys

#  La carpeta del programa (este script está en su tools/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from version import check_python  # noqa: E402
check_python()          # (before the modules that need it)

import argparse
import fnmatch
import zipfile

import interface
from interface import tr
from version import COMMIT_FILE, VERSION, commit

#  Adónde va el zip, salvo que --output diga otra cosa
DIST = os.path.join(ROOT, 'dist')

#  What is made while the program runs or is edited (as in .gitignore)
LEFT_OUT = ('__pycache__', '*.pyc', '*.bak', '*.tmp', '*~', 'WORD.MOD',
            'WORD.MDV', 'WORD.OUT', 'WORD.UNK', 'WORD.STA', 'py-words-v*.zip')
#  Lo que está en la carpeta del programa sin ser parte de él: la carpeta
#  de los paquetes, una carpeta que no va en git, los tags de un editor y
#  las herramientas que hacen los paquetes, los íconos y las versiones
#  TODO: no lee .gitignore.  Una carpeta nueva que no deba ir en el zip
#  hay que añadirla aquí a mano.
NOT_PART = ('dist', 'local-only', 'TAGS', 'tools', 'packaging', 'build')


def name() -> str:
    """The name of the zip, without .zip: py-words-v.2.1."""
    return f'py-words-v.{VERSION}'


def files(tests: bool = False) -> list[str]:
    """The files of the distribution, relative to the program's folder."""
    out = []
    for folder, dirs, names in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if not _left_out(d) and
                         (folder != ROOT or
                          d not in NOT_PART and (tests or d != 'tests')))
        for n in sorted(names):
            if not _left_out(n) and (folder != ROOT or n not in NOT_PART):
                out.append(os.path.relpath(os.path.join(folder, n), ROOT))
    return out


def _left_out(n: str) -> bool:
    return n.startswith('.') or any(fnmatch.fnmatch(n, p) for p in LEFT_OUT)


def built_from() -> str | None:
    """The commit the zip is made from: that of GitHub Actions
    ($GITHUB_SHA), or else the program's."""
    return os.environ.get('GITHUB_SHA') or commit(ROOT)


def bundle(folder: str, tests: bool = False) -> str:
    """Writes the zip into FOLDER; returns its path."""
    path = os.path.join(folder, name() + '.zip')
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files(tests):
            z.write(os.path.join(ROOT, f),
                    name() + '/' + f.replace(os.sep, '/'))
        hash = built_from()
        if hash:
            z.writestr(name() + '/' + COMMIT_FILE, hash + '\n')
    os.replace(tmp, path)
    return path


def main(argv=None):
    interface.use_configured()
    interface.translate_argparse()
    parser = argparse.ArgumentParser(
        prog='tools/bundle-zip.py',
        description=tr('Make a zip of the program, to distribute it: '
                       '{name}.zip, without hidden files.', name=name()))
    parser.add_argument('-o', '--output', metavar=tr('FOLDER'),
                        default=None,
                        help=tr('the folder to write it in (default: dist, '
                                "in the program's folder)"))
    parser.add_argument('--tests', action='store_true',
                        help=tr('include the tests'))
    args = parser.parse_args(argv)
    if args.output is None:
        args.output = DIST
        os.makedirs(DIST, exist_ok=True)
    elif not os.path.isdir(args.output):
        sys.exit('bundle-zip.py: ' + tr('there is no folder {folder}',
                                        folder=args.output))
    try:
        path = bundle(args.output, args.tests)
    except OSError as e:
        sys.exit(f'bundle-zip.py: {e}')
    with zipfile.ZipFile(path) as z:
        count = len(z.namelist())
    print(tr('Wrote {path} ({n} files, {size:.1f} MB).', path=path, n=count,
             size=os.path.getsize(path) / 1e6))


if __name__ == '__main__':
    main()
