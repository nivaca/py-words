#!/usr/bin/env python3
"""Builds the static site of py-words, which runs in the browser with
Pyodide: python3 pages/build.py [-o FOLDER]

The site (site/ by default) is the page and its script (pages/index.html
and pages/app.js), the icon, and py-words.zip: the program's .py files and
its data, which the page unpacks into Pyodide's files.  It can be served by
any static web server (GitHub Pages ...); to try it here:

    python3 pages/build.py && python3 -m http.server -d site 8001
"""

import argparse
import importlib.util
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ICON = os.path.join(ROOT, 'icons', 'linux', 'icons', 'hicolor', '48x48',
                    'apps', 'py-words.png')


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
    with zipfile.ZipFile(os.path.join(out, 'py-words.zip'), 'w',
                         zipfile.ZIP_DEFLATED) as z:
        for f in program_files():
            z.write(os.path.join(ROOT, f), f.replace(os.sep, '/'))
    open(os.path.join(out, '.nojekyll'), 'w').close()   # (GitHub Pages)
    return sorted(os.listdir(out))


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
