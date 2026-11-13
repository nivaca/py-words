#!/usr/bin/env python3
"""Makes the Flatpak of py-words: python3 tools/bundle-flatpak.py
[--install] [--flathub FOLDER]

From the manifest packaging/flatpak/io.github.nivaca.PyWords.yml, built
with the files of the working tree that the zip has (tools/bundle-zip.py,
with COMMIT) and those of packaging/ that the build reads, it writes
dist/py-words-v.VERSION.flatpak, a single-file bundle that installs with

    flatpak install --user dist/py-words-v.VERSION.flatpak

(it takes the runtime, org.freedesktop.Platform, from Flathub).  It needs
flatpak-builder and org.freedesktop.Sdk of the manifest's version
(flatpak install --user flathub org.freedesktop.Sdk//VERSION); the work is
done in build/flatpak/.  --install also installs it for this user.

--flathub FOLDER writes instead into FOLDER the manifest for Flathub: the
same, but with the program taken from the tag vVERSION of the git
repository (which must be there already, as tools/release.py makes it).
"""

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from version import COMMIT_FILE, VERSION  # noqa: E402

APP_ID = 'io.github.nivaca.PyWords'
MANIFEST = os.path.join(ROOT, 'packaging', 'flatpak', APP_ID + '.yml')
METAINFO = os.path.join(ROOT, 'packaging', 'flatpak',
                        APP_ID + '.metainfo.xml')
WORK = os.path.join(ROOT, 'build', 'flatpak')
DIST = os.path.join(ROOT, 'dist')
GIT_URL = 'https://github.com/nivaca/py-words.git'
#  Where the users' flatpak finds the runtime of a bundle
RUNTIME_REPO = 'https://dl.flathub.org/repo/flathub.flatpakrepo'
#  The files of packaging/ that the build reads (packaging/ is not in the
#  zip)
PACKAGING = ('py-words-launcher.in', 'py-words.desktop',
             'py-words.cli.desktop', 'py-words.tui.desktop',
             'py-words.web.desktop',
             os.path.join('flatpak', APP_ID + '.metainfo.xml'))
#  The start of the py-words module's sources in the manifest, which is
#  the last thing in it
SOURCES = '    sources:\n      # (tools/bundle-flatpak.py'


def name() -> str:
    """The name of the bundle: py-words-v.3.15.flatpak."""
    return f'py-words-v.{VERSION}.flatpak'


def bundle_zip():
    """The module tools/bundle-zip.py."""
    spec = importlib.util.spec_from_file_location(
        'bundle_zip', os.path.join(ROOT, 'tools', 'bundle-zip.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def with_sources(sources: str) -> str:
    """The manifest, with SOURCES (YAML, indented as there) as those of
    py-words."""
    with open(MANIFEST, encoding='utf-8') as f:
        text = f.read()
    at = text.index(SOURCES)
    return text[:at] + '    sources:\n' + sources


def tree(folder: str):
    """The files the build reads into FOLDER (emptied first)."""
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    zip_files = bundle_zip()
    for f in zip_files.files() + [os.path.join('packaging', p)
                                  for p in PACKAGING]:
        os.makedirs(os.path.join(folder, os.path.dirname(f)),
                    exist_ok=True)
        shutil.copy2(os.path.join(ROOT, f), os.path.join(folder, f))
    hash = zip_files.built_from()
    if hash:
        with open(os.path.join(folder, COMMIT_FILE), 'w') as f:
            f.write(hash + '\n')


def released() -> str | None:
    """The version of the newest <release> of the metainfo."""
    with open(METAINFO, encoding='utf-8') as f:
        m = re.search(r'<release version="([^"]+)"', f.read())
    return m.group(1) if m else None


def build(install: bool) -> str:
    """Builds the bundle into dist/; returns its path."""
    for tool in ('flatpak', 'flatpak-builder'):
        if shutil.which(tool) is None:
            sys.exit(f'bundle-flatpak.py: there is no {tool} (sudo dnf '
                     f'install {tool})')
    src = os.path.join(WORK, 'tree')
    tree(src)
    manifest = os.path.join(WORK, APP_ID + '.yml')
    with open(manifest, 'w', encoding='utf-8') as f:
        f.write(with_sources(f'      - type: dir\n        path: {src}\n'))
    repo = os.path.join(WORK, 'repo')
    command = ['flatpak-builder', '--user', '--force-clean',
               '--state-dir', os.path.join(WORK, 'state'), '--repo', repo]
    if install:
        command.append('--install')
    subprocess.run(command + [os.path.join(WORK, 'app'), manifest],
                   check=True)
    os.makedirs(DIST, exist_ok=True)
    path = os.path.join(DIST, name())
    subprocess.run(['flatpak', 'build-bundle', '--runtime-repo',
                    RUNTIME_REPO, repo, path, APP_ID], check=True)
    return path


def flathub(folder: str) -> str:
    """Writes the manifest for Flathub into FOLDER; returns its path."""
    tag = f'v{VERSION}'
    try:
        commit = subprocess.run(
            ['git', 'rev-parse', '--verify', '--quiet', tag + '^{commit}'],
            cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        sys.exit(f'bundle-flatpak.py: there is no tag {tag} (tools/'
                 f'release.py makes it)')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, APP_ID + '.yml')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(with_sources(
            f'      - type: git\n'
            f'        url: {GIT_URL}\n'
            f'        tag: {tag}\n'
            f'        commit: {commit}\n'
            f'        x-checker-data:\n'
            f'          type: git\n'
            f'          tag-pattern: ^v([\\d.]+)$\n'
            f'      # (for "About": git is not there when it runs)\n'
            f'      - type: inline\n'
            f'        dest-filename: {COMMIT_FILE}\n'
            f'        contents: {commit}\n'))
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='tools/bundle-flatpak.py',
        description='Make the Flatpak of py-words (dist/' + name() + '), '
                    'or the manifest for Flathub.')
    parser.add_argument('--install', action='store_true',
                        help='also install it for this user')
    parser.add_argument('--flathub', metavar='FOLDER',
                        help='write the manifest for Flathub into FOLDER '
                             '(from the tag vVERSION), and build nothing')
    args = parser.parse_args(argv)
    if released() != VERSION:
        sys.exit(f'bundle-flatpak.py: the newest <release> of {METAINFO} '
                 f'is {released()}, not {VERSION}')
    if args.flathub:
        print('Wrote', flathub(args.flathub))
    else:
        print('Wrote', build(args.install))


if __name__ == '__main__':
    main()
