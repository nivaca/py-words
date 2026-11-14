#!/usr/bin/env python3
"""Builds the static site of py-words: python3 pages/build.py [-o FOLDER]

The site (site/ by default) has one page (pages/redirect.html, also as
404.html, for the old addresses), which sends the visitor to the program
on a server (SERVER, or --server), with the search of the address
(?q=...).  It can be served by any static web server (GitHub Pages ...);
to try it here:

    python3 pages/build.py && python3 -m http.server -d site 8001

and open localhost:8001.
"""

import argparse
import html
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
#  The program on a web server for everyone (words_web.public_app), where
#  the page of the site sends its visitors
SERVER = 'https://nivaca.pythonanywhere.com/'
ICON = os.path.join(ROOT, 'icons', 'linux', 'icons', 'hicolor', '48x48',
                    'apps', 'py-words.png')


def redirect_page(server: str) -> str:
    """The page of the site: to SERVER, with the search."""
    with open(os.path.join(HERE, 'redirect.html'), encoding='utf-8') as f:
        page = f.read()
    return page.replace('$server', html.escape(server)).replace(
        '$json_server', json.dumps(server).replace('<', '\\u003c'))


def build(out: str, server: str = SERVER) -> list[str]:
    """Writes the site into OUT (emptied first): its page, to SERVER.
    Returns the files of OUT."""
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    shutil.copy(ICON, os.path.join(out, 'icon.png'))
    page = redirect_page(server)
    #  (404.html: GitHub Pages shows it for any other address, as those of
    #  the old version in the browser)
    for name in ('index.html', '404.html'):
        with open(os.path.join(out, name), 'w', encoding='utf-8') as f:
            f.write(page)
    open(os.path.join(out, '.nojekyll'), 'w').close()   # (GitHub Pages)
    return sorted(os.listdir(out))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Build the static site of py-words.')
    parser.add_argument('-o', '--output', default=os.path.join(ROOT, 'site'),
                        help='the folder to write it in (default: site/)')
    parser.add_argument('--server', default=SERVER,
                        help=f'where its page sends the visitors (default: '
                             f'{SERVER})')
    args = parser.parse_args(argv)
    names = build(args.output, args.server)
    print(f'Wrote {args.output}: {", ".join(names)}')


if __name__ == '__main__':
    sys.exit(main())
