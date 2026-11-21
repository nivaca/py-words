#!/usr/bin/env python3
# py-words, a Latin dictionary and parser.
# Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENCE.txt file, or <https://www.gnu.org/licenses/>.
"""Hace el paquete .deb de py-words (Debian, Ubuntu y derivados) a partir
de esta copia del repositorio, en build/deb/, y copia el más reciente a
dist/, junto al zip, la AppImage y el RPM.

    python3 packaging/build-deb.py [--sign[=CLAVE]]

El paquete instala lo mismo que el RPM (packaging/py-words.spec): el
programa en /usr/share/py-words, la orden py-words en /usr/bin, las
cuatro entradas del menú, los íconos y la documentación.  No necesita
dpkg: un .deb es un archivo ar con dos tar (control y datos), y aquí se
arman con la biblioteca estándar, así que se puede hacer en Fedora.

Los archivos son los que git conoce, confirmados o no, como en
build-rpm.sh; el commit de HEAD va dentro como COMMIT.  --sign firma el
paquete con OpenPGP (una firma aparte, .deb.asc) con la clave del
proyecto, la misma del RPM.
"""

import argparse
import gzip
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR)
from version import VERSION  # noqa: E402

NAME = 'py-words'
REVISION = '1'                  # la del paquete, no la del programa
SIGNING_KEY = '81870643CA221AF90C30554EBE6832CD35994948'
MAINTAINER = 'Nicolas Vaughan <nicolasvaughan@proton.me>'
PREFIX = f'/usr/share/{NAME}'
OUT = os.path.join(DIR, 'build', 'deb')
DIST = os.path.join(DIR, 'dist')

HELP = ('Build the .deb package of py-words (Debian, Ubuntu) into '
        'build/deb/, and copy it to dist/.')

CONTROL = f"""\
Package: {NAME}
Version: {{version}}
Architecture: all
Maintainer: {MAINTAINER}
Installed-Size: {{size}}
Depends: python3 (>= 3.13), python3-tk
Recommends: hicolor-icon-theme
Section: text
Priority: optional
Homepage: https://github.com/nivaca/py-words
Description: Latin dictionary and parser (Latin-English and Latin-Spanish)
 py-words is a Latin dictionary that parses inflected Latin words: it gives
 each form's analysis (case, number, tense ...) and the dictionary entry
 with its meanings, in English or Spanish, and looks up words the other
 way round. It started from WORDS by William Whitaker, with a redesigned
 program and data, a new English dictionary (Lewis and Short) and two new
 Spanish ones (Echave-Sustaeta and De Miguel).
 .
 It comes as a window, a command line, a full-screen terminal program and
 a web page served on this computer, all started by the py-words command.
 Its interface is in English, Spanish or Medieval Latin.
"""

#  Los módulos se compilan al instalar (los usuarios no pueden escribir
#  junto a ellos, y Python los compilaría en cada arranque) y se borran
#  al desinstalar
POSTINST = f"""\
#!/bin/sh
set -e
if [ "$1" = configure ] && command -v python3 >/dev/null 2>&1; then
    python3 -m compileall -q {PREFIX} >/dev/null 2>&1 || true
fi
"""
PRERM = f"""\
#!/bin/sh
set -e
find {PREFIX} -name __pycache__ -type d -prune -exec rm -rf {{}} + 2>/dev/null || true
"""

COPYRIGHT = f"""\
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: {NAME}
Upstream-Contact: {MAINTAINER}
Source: https://github.com/nivaca/py-words

Files: *
Copyright: 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
License: GPL-3.0+

Files: usr/share/{NAME}/data/*
Copyright: William A. Whitaker (1936-2010), WORDS; 2026 Nicolas Vaughan
License: GPL-3.0+ and CC-BY-SA-4.0
Comment: The data of WORDS are free for any use ("Permission is hereby
 freely given for any and all use of program and data").  The Lewis and
 Short meanings come from the text of the Perseus Digital Library, under
 CC BY-SA 4.0.  See /usr/share/doc/{NAME}/README.md.

License: GPL-3.0+
 This program is free software: you can redistribute it and/or modify it
 under the terms of the GNU General Public License as published by the Free
 Software Foundation, either version 3 of the License, or (at your option)
 any later version.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in "/usr/share/common-licenses/GPL-3".

License: CC-BY-SA-4.0
 Creative Commons Attribution-ShareAlike 4.0 International.  The full text
 is at <https://creativecommons.org/licenses/by-sa/4.0/legalcode>.
"""

#  La documentación que va en /usr/share/doc/py-words (como %doc del RPM)
DOCS = ('README.md', 'README_es.md', 'README_la.md', 'CHANGELOG.md',
        'CHANGELOG_es.md', 'docs/DESCRIPTION.md', 'docs/DESCRIPCIÓN_es.md',
        'docs/LICENCES.md', 'docs/LICENCIAS_es.md', 'docs/MANUAL_en.pdf',
        'docs/MANUAL_es.pdf', 'docs/MANUAL_la.pdf')


def die(message: str):
    sys.exit(f'build-deb: {message}')


def git(*args: str) -> str:
    return subprocess.run(['git', '-C', DIR, *args], check=True,
                          capture_output=True, text=True).stdout


def known_files() -> list[str]:
    """The files git knows about, committed or not, that exist."""
    #  -z: sin él, git cita los nombres con letras no ASCII
    #  ("docs/DESCRIPCI\303\223N_es.md") y no se encuentran
    out = git('ls-files', '-z', '--cached', '--others', '--exclude-standard')
    return [f for f in out.split('\0')
            if f and os.path.isfile(os.path.join(DIR, f))]


def contents(files: list[str], commit: str) -> dict[str, tuple[bytes, int]]:
    """{path in the package: (bytes, mode)}: what the package installs."""
    out = {}

    def add(path, data, mode=0o644):
        out[path] = (data, mode)

    def copy(src, path, mode=0o644):
        with open(os.path.join(DIR, src), 'rb') as f:
            add(path, f.read(), mode)

    #  el programa: los módulos de arriba y lo que leen (data/ y los
    #  íconos); words_install.py no, porque el paquete trae sus entradas
    for f in files:
        if '/' not in f and f.endswith('.py') and f != 'words_install.py':
            copy(f, f'usr/share/{NAME}/{f}')
        elif f.startswith('data/') or f in ('icons/py-words.svg',
                                            'icons/uniandes.svg') or \
                f.startswith('icons/linux/icons/hicolor/'):
            copy(f, f'usr/share/{NAME}/{f}')
    add(f'usr/share/{NAME}/COMMIT', (commit + '\n').encode())
    #  the command, as for the RPM
    with open(os.path.join(DIR, 'packaging', 'py-words-launcher.in'),
              encoding='utf-8') as f:
        launcher = f.read().replace('@DATADIR@', PREFIX) \
                           .replace('@PYTHON@', '/usr/bin/python3') \
                           .replace('as installed by the RPM '
                                    '(packaging/py-words.spec)',
                                    'as installed by the .deb '
                                    '(packaging/build-deb.py)')
    if re.search(r'@[A-Z]+@', launcher):
        die('the launcher still has a @PLACEHOLDER@')
    add('usr/bin/py-words', launcher.encode(), 0o755)
    for f in files:
        if f.startswith('packaging/') and f.endswith('.desktop'):
            copy(f, f'usr/share/applications/{os.path.basename(f)}')
        elif f.startswith('icons/linux/icons/hicolor/'):
            copy(f, 'usr/share/icons/' + f[len('icons/linux/icons/'):])
    #  la documentación, con el copyright y el changelog que pide Debian
    doc = f'usr/share/doc/{NAME}'
    for f in DOCS:
        if f not in files:
            die(f'{f} is missing (build the manuals with latexmk in docs/)')
        copy(f, f'{doc}/{os.path.basename(f)}')
    add(f'{doc}/copyright', COPYRIGHT.encode())
    add(f'{doc}/changelog.Debian.gz', gzip.compress(changelog().encode(),
                                                    mtime=0))
    return out


def changelog() -> str:
    """A Debian changelog entry for this version (the changes are in
    CHANGELOG.md)."""
    date = time.strftime('%a, %d %b %Y %H:%M:%S +0000',
                         time.gmtime(epoch()))
    return (f'{NAME} ({VERSION}-{REVISION}) unstable; urgency=medium\n\n'
            f'  * Version {VERSION}; see /usr/share/doc/{NAME}/'
            'CHANGELOG.md.\n\n'
            f' -- {MAINTAINER}  {date}\n')


def epoch() -> int:
    """The time of the files: that of the commit, so the same commit
    makes the same package ($SOURCE_DATE_EPOCH, if set, comes first)."""
    if os.environ.get('SOURCE_DATE_EPOCH'):
        return int(os.environ['SOURCE_DATE_EPOCH'])
    return int(git('log', '-1', '--format=%ct').strip())


def tar(members: dict[str, tuple[bytes, int]], mtime: int) -> bytes:
    """A tar.xz of MEMBERS, owned by root, with their folders."""
    folders = set()
    for path in members:
        parts = path.split('/')[:-1]
        for i in range(1, len(parts) + 1):
            folders.add('/'.join(parts[:i]))
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:xz',
                      format=tarfile.GNU_FORMAT) as t:
        def info(name, mode, kind=tarfile.REGTYPE, size=0):
            i = tarfile.TarInfo('./' + name if name else './')
            i.type, i.mode, i.size, i.mtime = kind, mode, size, mtime
            i.uid = i.gid = 0
            i.uname = i.gname = 'root'
            return i
        t.addfile(info('', 0o755, tarfile.DIRTYPE))
        for d in sorted(folders):
            t.addfile(info(d + '/', 0o755, tarfile.DIRTYPE))
        for path in sorted(members):
            data, mode = members[path]
            t.addfile(info(path, mode, size=len(data)), io.BytesIO(data))
    return buffer.getvalue()


def ar(members: list[tuple[str, bytes]], mtime: int) -> bytes:
    """An ar archive (the format of a .deb) of MEMBERS."""
    out = [b'!<arch>\n']
    for name, data in members:
        header = (f'{name:<16}{mtime:<12}{0:<6}{0:<6}{0o100644:<8o}'
                  f'{len(data):<10}`\n').encode()
        assert len(header) == 60
        out += [header, data, b'\n' if len(data) % 2 else b'']
    return b''.join(out)


def build(sign: str | None) -> str:
    files = known_files()
    if git('status', '--porcelain').strip():
        print('note: the tree has uncommitted changes; they go into this '
              'build.')
    commit = git('rev-parse', 'HEAD').strip()
    mtime = epoch()
    data = contents(files, commit)
    version = f'{VERSION}-{REVISION}'
    size = sum((len(d) + 1023) // 1024 for d, _ in data.values())
    control = {
        'control': (CONTROL.format(version=version, size=size).encode(),
                    0o644),
        'md5sums': (''.join(f'{hashlib.md5(d).hexdigest()}  {p}\n'
                            for p, (d, _) in sorted(data.items())
                            ).encode(), 0o644),
        'postinst': (POSTINST.encode(), 0o755),
        'prerm': (PRERM.encode(), 0o755),
    }
    deb = ar([('debian-binary', b'2.0\n'),
              ('control.tar.xz', tar(control, mtime)),
              ('data.tar.xz', tar(data, mtime))], mtime)
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    path = os.path.join(OUT, f'{NAME}_{version}_all.deb')
    with open(path, 'wb') as f:
        f.write(deb)
    print(f'Wrote {os.path.relpath(path, DIR)} ({len(deb) // 1024} KiB, '
          f'{len(data)} files)')
    made = [path]
    if sign:
        subprocess.run(['gpg', '--batch', '--yes', '--armor',
                        '--local-user', sign, '--detach-sign', path],
                       check=True)
        made.append(path + '.asc')
        print(f'Signed: {os.path.relpath(path, DIR)}.asc')
    #  el .deb más reciente también en dist/, en lugar de los anteriores
    os.makedirs(DIST, exist_ok=True)
    for old in os.listdir(DIST):
        if old.startswith(f'{NAME}_') and (old.endswith('.deb') or
                                           old.endswith('.deb.asc')):
            os.remove(os.path.join(DIST, old))
    for f in made:
        shutil.copy2(f, DIST)
    print('Copied to dist/: ' + ' '.join(os.path.basename(f)
                                         for f in made))
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=HELP)
    parser.add_argument('--sign', nargs='?', const=SIGNING_KEY,
                        metavar='KEY',
                        help='also sign it (a detached OpenPGP signature, '
                             '.deb.asc) with the project\'s key, or KEY')
    args = parser.parse_args(argv)
    build(args.sign)


if __name__ == '__main__':
    main()
