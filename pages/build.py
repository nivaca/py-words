#!/usr/bin/env python3
"""Builds the static site of py-words, which runs in the browser with
Pyodide: python3 pages/build.py [-o FOLDER]

The site (site/ by default) is the page and its script (pages/index.html
and pages/app.js), the icon, and py-words.zip: the program's .py files and
its data, which the page unpacks into Pyodide's files.  The languages of
the meanings but English and Spanish are left out of the zip, which keeps
only the start of their files (their name, for the list of languages):
the whole file is beside it, in languages/, and the page downloads it
when the language is chosen (see app.js).  It can be served by
any static web server (GitHub Pages ...); to try it here:

    python3 pages/build.py && python3 -m http.server -d site 8001
"""

import argparse
import importlib.util
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ICON = os.path.join(ROOT, 'icons', 'linux', 'icons', 'hicolor', '48x48',
                    'apps', 'py-words.png')

#  The languages of the meanings that go whole in the zip (the others are
#  downloaded when chosen)
IN_ZIP = ('en', 'es')
LANGUAGES = 'data/languages/'
#  What marks a language file of the zip that is only its start
STUB = 'py-words: downloaded when chosen'


def program_files() -> list[str]:
    """The program's .py files and data (those of the distribution, but not
    its icons, documents or tests), relative to ROOT."""
    sys.path.insert(0, ROOT)
    spec = importlib.util.spec_from_file_location(
        'bundle_zip', os.path.join(ROOT, 'bundle-zip.py'))
    bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle)
    return [f for f in bundle.files()
            if (f.endswith('.py') and os.sep not in f) or
            f.startswith('data' + os.sep)]


def build(out: str) -> list[str]:
    """Writes the site into OUT (emptied first); returns its files."""
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    for name in ('index.html', 'app.js'):
        shutil.copy(os.path.join(HERE, name), out)
    shutil.copy(ICON, os.path.join(out, 'icon.png'))
    os.makedirs(os.path.join(out, 'languages'))
    with zipfile.ZipFile(os.path.join(out, 'py-words.zip'), 'w',
                         zipfile.ZIP_DEFLATED) as z:
        for f in program_files():
            path, name = os.path.join(ROOT, f), f.replace(os.sep, '/')
            code = name[len(LANGUAGES):-len('.xml')]
            if name.startswith(LANGUAGES) and '/' not in code and \
                    code not in IN_ZIP:
                shutil.copy(path, os.path.join(out, 'languages'))
                info = zipfile.ZipInfo.from_file(path, name)
                z.writestr(info, stub(path), zipfile.ZIP_DEFLATED)
            else:
                z.write(path, name)
    open(os.path.join(out, '.nojekyll'), 'w').close()   # (GitHub Pages)
    return sorted(os.listdir(out))


def stub(path: str) -> str:
    """The start of the language file PATH: its root element, with its
    name, and nothing in it."""
    with open(path, encoding='utf-8') as f:
        text = f.read()
    root = re.search(r'<language\b[^>]*>', text)
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<!-- {STUB} -->\n'
            f'{root.group(0)}\n</language>\n')


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Build the static site of py-words (with Pyodide).')
    parser.add_argument('-o', '--output', default=os.path.join(ROOT, 'site'),
                        help='the folder to write it in (default: site/)')
    args = parser.parse_args(argv)
    names = build(args.output)
    size = os.path.getsize(os.path.join(args.output, 'py-words.zip'))
    print(f'Wrote {args.output}: {", ".join(names)} '
          f'(py-words.zip: {size / 1e6:.1f} MB)')


if __name__ == '__main__':
    sys.exit(main())
