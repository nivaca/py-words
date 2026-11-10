#!/usr/bin/env python3
"""Builds the static site of py-words, which runs in the browser with
Pyodide: python3 pages/build.py [-o FOLDER]

The site (site/ by default) has, in browser/, the page and its script
(pages/index.html and pages/app.js), the icon, and py-words.zip: the
program's .py files and its data (and COMMIT, the commit it was built
from), which the page unpacks into Pyodide's files.  Its own page
(pages/redirect.html) sends the visitor to the program on a server
(SERVER, or --server), with the search of the address (?q=...), and links
to browser/.  It can be served by any static web server (GitHub Pages
...); to try it here:

    python3 pages/build.py && python3 -m http.server -d site 8001

and open localhost:8001/browser/.
"""

import argparse
import html
import importlib.util
import json
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
#  The program on a web server for everyone (words_web.public_app), where
#  the page of the site sends its visitors
SERVER = 'https://nivaca.pythonanywhere.com/'
BROWSER = 'browser'                     # (the folder of the Pyodide version)
ICON = os.path.join(ROOT, 'icons', 'linux', 'icons', 'hicolor', '48x48',
                    'apps', 'py-words.png')


def bundle_zip():
    """The module tools/bundle-zip.py."""
    sys.path.insert(0, ROOT)
    spec = importlib.util.spec_from_file_location(
        'bundle_zip', os.path.join(ROOT, 'tools', 'bundle-zip.py'))
    bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle)
    return bundle


def program_files() -> list[str]:
    """The program's .py files and data (those of the distribution, but not
    its icons, documents or tests; only the university's logo, which the
    page shows), relative to ROOT."""
    return [f for f in bundle_zip().files()
            if (f.endswith('.py') and os.sep not in f) or
            f.startswith('data' + os.sep) or
            f == os.path.join('icons', 'uniandes.svg')]


def redirect_page(server: str) -> str:
    """The page of the site: to SERVER, with the search."""
    with open(os.path.join(HERE, 'redirect.html'), encoding='utf-8') as f:
        page = f.read()
    return page.replace('$server', html.escape(server)).replace(
        '$json_server', json.dumps(server).replace('<', '\\u003c')).replace(
        '$browser', BROWSER + '/')


def build(out: str, server: str = SERVER) -> list[str]:
    """Writes the site into OUT (emptied first): its page, to SERVER, and
    the version in the browser in OUT/browser.  Returns the files of
    OUT."""
    if os.path.isdir(out):
        shutil.rmtree(out)
    browser = os.path.join(out, BROWSER)
    os.makedirs(browser)
    for name in ('index.html', 'app.js'):
        shutil.copy(os.path.join(HERE, name), browser)
    for folder in (out, browser):
        shutil.copy(ICON, os.path.join(folder, 'icon.png'))
    with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(redirect_page(server))
    with zipfile.ZipFile(os.path.join(browser, 'py-words.zip'), 'w',
                         zipfile.ZIP_DEFLATED) as z:
        for f in program_files():
            z.write(os.path.join(ROOT, f), f.replace(os.sep, '/'))
        bundle = bundle_zip()
        hash = bundle.built_from()
        if hash:                        # (for "About")
            z.writestr(bundle.COMMIT_FILE, hash + '\n')
    open(os.path.join(out, '.nojekyll'), 'w').close()   # (GitHub Pages)
    return sorted(os.listdir(out))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Build the static site of py-words (with Pyodide).')
    parser.add_argument('-o', '--output', default=os.path.join(ROOT, 'site'),
                        help='the folder to write it in (default: site/)')
    parser.add_argument('--server', default=SERVER,
                        help=f'where its page sends the visitors (default: '
                             f'{SERVER})')
    args = parser.parse_args(argv)
    names = build(args.output, args.server)
    size = os.path.getsize(os.path.join(args.output, BROWSER,
                                        'py-words.zip'))
    print(f'Wrote {args.output}: {", ".join(names)} '
          f'(py-words.zip: {size / 1e6:.1f} MB)')


if __name__ == '__main__':
    sys.exit(main())
