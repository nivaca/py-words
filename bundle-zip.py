#!/usr/bin/env python3
"""Makes a zip of the program, to distribute it: python3 bundle-zip.py

The zip is py-words-v.VERSION.zip (the version of version.py), with the
program in a folder of the same name.  It has the programs, the data, the
icons and the documents, but no hidden files or folders (.git ...), and
none of what is made while the program runs or is edited (__pycache__,
.bak and .tmp files, WORD.OUT ...), nor what is in its folder but not
part of it (the built site, local-only/, an editor's TAGS).  The tests
are left out, unless --tests says otherwise.
"""

from version import check_python
check_python()          # (before the modules that need it)

import argparse
import fnmatch
import os
import sys
import zipfile

import interface
from interface import tr
from version import VERSION

HERE = os.path.dirname(os.path.abspath(__file__))

#  What is made while the program runs or is edited (as in .gitignore)
LEFT_OUT = ('__pycache__', '*.pyc', '*.bak', '*.tmp', '*~', 'WORD.MOD',
            'WORD.MDV', 'WORD.OUT', 'WORD.UNK', 'WORD.STA', 'py-words-v*.zip')
#  What is in the program's folder but not part of it: the site built by
#  pages/build.py, a folder kept out of git, and an editor's tags
#  TODO: no lee .gitignore.  Una carpeta nueva que no deba ir en el zip
#  hay que añadirla aquí a mano.
NOT_PART = ('site', 'local-only', 'TAGS', 'tools')


def name() -> str:
    """The name of the zip, without .zip: py-words-v.2.1."""
    return f'py-words-v.{VERSION}'


def files(tests: bool = False) -> list[str]:
    """The files of the distribution, relative to the program's folder."""
    out = []
    for folder, dirs, names in os.walk(HERE):
        dirs[:] = sorted(d for d in dirs if not _left_out(d) and
                         (folder != HERE or
                          d not in NOT_PART and (tests or d != 'tests')))
        for n in sorted(names):
            if not _left_out(n) and (folder != HERE or n not in NOT_PART):
                out.append(os.path.relpath(os.path.join(folder, n), HERE))
    return out


def _left_out(n: str) -> bool:
    return n.startswith('.') or any(fnmatch.fnmatch(n, p) for p in LEFT_OUT)


def bundle(folder: str, tests: bool = False) -> str:
    """Writes the zip into FOLDER; returns its path."""
    path = os.path.join(folder, name() + '.zip')
    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files(tests):
            z.write(os.path.join(HERE, f),
                    name() + '/' + f.replace(os.sep, '/'))
    os.replace(tmp, path)
    return path


def main(argv=None):
    interface.use_configured()
    interface.translate_argparse()
    parser = argparse.ArgumentParser(
        prog='bundle-zip.py',
        description=tr('Make a zip of the program, to distribute it: '
                       '{name}.zip, without hidden files.', name=name()))
    parser.add_argument('-o', '--output', metavar=tr('FOLDER'),
                        default='.',
                        help=tr('the folder to write it in (default: the '
                                'current one)'))
    parser.add_argument('--tests', action='store_true',
                        help=tr('include the tests'))
    args = parser.parse_args(argv)
    if not os.path.isdir(args.output):
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
