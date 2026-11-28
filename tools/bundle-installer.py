#!/usr/bin/env python3
"""Hace los instaladores de py-words, con un Python propio, para los tres
sistemas:

    python3 tools/bundle-installer.py [--system linux|windows|macos]
                                      [--arch ARQ] [-o CARPETA]
                                      [--python TARBALL] [--no-extras]
                                      [--stage-only] [--iscc ISCC]

Cada uno lleva el programa (los archivos del zip de bundle-zip.py, sin
words_install.py), un Python 3.13 con Tk del proyecto
python-build-standalone (https://github.com/astral-sh/python-build-standalone),
recortado, y packaging/installer/launcher.py, que da la orden py-words con
las mismas órdenes que el AppImage (gui, cli, tui, web ...):

* Linux: dist/py-words-v.VERSION-linux-ARQ.run, un script de sh seguido
  de un tar.gz (packaging/installer/install.sh).  Instala para el usuario
  o, como root, para todos; la orden, las entradas del menú, los íconos y
  un desinstalador.  Se hace en cualquier sistema.
* Windows: dist/py-words-v.VERSION-windows-x64-setup.exe, hecho con Inno
  Setup (packaging/installer/py-words.iss): para el usuario o para todos,
  menú Inicio, escritorio, PATH, desinstalador en "Aplicaciones".  Necesita
  ISCC, es decir, Windows (o --stage-only).
* macOS: dist/py-words-v.VERSION-macos-ARQ.pkg (arm64 o x86_64), hecho
  con pkgbuild y productbuild: py-words.app en /Applications, las tres
  aplicaciones de Terminal y la orden en /usr/local/bin, cada parte
  opcional (packaging/installer/macos/).  Necesita macOS (o --stage-only).

El Python y los paquetes extra (certifi; en Windows, windows-curses para
words_tui.py) se descargan la primera vez, se comprueban con su SHA-256 y
se guardan en ~/.cache/py-words-build.  --python da otro tarball de
python-build-standalone (sin comprobarlo), y --no-extras deja fuera los
paquetes extra.  --stage-only arma la carpeta del instalador en la
carpeta de salida sin hacer el instalador (sirve para revisarla, y para
las pruebas).  En dist/ se borran los instaladores de versiones
anteriores del mismo sistema y arquitectura.
"""

import os
import sys

#  La carpeta del programa (este script está en su tools/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from version import check_python  # noqa: E402
check_python()          # (before the modules that need it)

import argparse
import compileall
import glob
import hashlib
import importlib.util
import platform
import plistlib
import py_compile
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from typing import NamedTuple
from xml.sax.saxutils import escape, quoteattr

from version import COMMIT_FILE, VERSION

DIST = os.path.join(ROOT, 'dist')
INSTALLER = os.path.join(ROOT, 'packaging', 'installer')
APP_ID = 'py-words'
BUNDLE_ID = 'io.github.nivaca.py-words'
SYSTEMS = ('linux', 'windows', 'macos')

#  El Python que va en los instaladores: una versión fija de
#  python-build-standalone, sin símbolos de depuración (install_only_stripped:
#  sin ellos, el .run de Linux pasaba de 80 MB), con la suma SHA-256 de cada
#  tarball (de su SHA256SUMS).  Para cambiarla, cambiar las tres cosas juntas.
PYTHON_VERSION = '3.13.18'
PBS_RELEASE = '20261110'
PBS_URL = ('https://github.com/astral-sh/python-build-standalone/releases/'
           'download/{release}/cpython-{version}+{release}-{triple}-'
           'install_only_stripped.tar.gz')
TRIPLES = {
    ('linux', 'x86_64'): 'x86_64-unknown-linux-gnu',
    ('linux', 'aarch64'): 'aarch64-unknown-linux-gnu',
    ('windows', 'x64'): 'x86_64-pc-windows-msvc',
    ('macos', 'arm64'): 'aarch64-apple-darwin',
    ('macos', 'x86_64'): 'x86_64-apple-darwin',
}
PBS_SHA256 = {
    'x86_64-unknown-linux-gnu':
        'f2d2199eb25880e07863b391cf7124e7ffa1338b0d65600dfcec117c4223a7fb',
    'aarch64-unknown-linux-gnu':
        '55c00325f7c1fddf325dfc621aabdfbbac4dc54adda224af88ec411dc12db239',
    'x86_64-pc-windows-msvc':
        '2e0fed09d48989f64c9305da9ff2d37a41c0d13ab2aa6283405b2b620dfbf805',
    'aarch64-apple-darwin':
        '7a2384641584ab9984221fcb0fc9265df465922af71be71410529e2a9c3f0540',
    'x86_64-apple-darwin':
        'd27d59a722db9f69926eb6d9564071247221f45a04da920ea7f3001c97e32f9b',
}
#  The minor version, as in lib/python3.13
PYTHON_MINOR = '.'.join(PYTHON_VERSION.split('.')[:2])


class Wheel(NamedTuple):
    url: str
    sha256: str


#  Los paquetes que se añaden al Python: los certificados de certifi (el
#  OpenSSL del Python propio no siempre encuentra los del sistema; véase
#  launcher.py) y, en Windows, curses, que su Python no trae
CERTIFI = Wheel(
    'https://files.pythonhosted.org/packages/6d/39/5eec3296860b94ac20bb8ed'
    '807725b88f6adfab3f343df592afd975f5f86/'
    'certifi-2026.11.20-py3-none-any.whl',
    '7422df25243767b9877031a2248cb14d09ddac9beee846f4cef3d5c9191d488f')
WINDOWS_CURSES = Wheel(
    'https://files.pythonhosted.org/packages/47/e8/38fd0fef95271280a77a4f3'
    'b65e0961d3c39716388b39c08b3040bfb4f2c/'
    'windows_curses-2.4.2-cp313-cp313-win_amd64.whl',
    '1bf3d0c902374b6c430a954adcb686a5ecd7a31fc4195d31136385b5c1bea925')

#  Lo que se quita del Python (no lo usa el programa): las pruebas, IDLE,
#  pip, los archivos para compilar extensiones ...  (Not share/terminfo:
#  its curses reads the terminal descriptions from there.)
STDLIB_LEFT_OUT = ('test', 'idlelib', 'turtledemo', 'ensurepip')
UNIX_LEFT_OUT = ('include', 'share/man', 'lib/pkgconfig',
                 f'lib/python{PYTHON_MINOR}/config-*', 'bin/pip*',
                 'bin/idle*', 'bin/pydoc*', 'bin/2to3*', 'bin/*-config')
WINDOWS_LEFT_OUT = ('include', 'libs', 'Scripts')

#  Lo que no va en los instaladores: el instalador de entradas de menú
#  (cada instalador hace las suyas)
NOT_INSTALLED = ('words_install.py',)

#  Los diccionarios que el usuario podría editar quedan de solo lectura
#  (una actualización borraría lo editado; véase editor.read_only)
DATA = 'program/data'
DICTIONARY = 'program/data/dictionary.xml'

#  bin/py-words in Linux and macOS: runs launcher.py with the Python of
#  the installation, wherever a link to it is
POSIX_COMMAND = r'''#!/bin/sh
# Starts py-words (launcher.py, with the Python of the installation).
self=$0
while [ -L "$self" ]; do
    link=$(readlink -- "$self")
    case $link in
        /*) self=$link ;;
        *) self=$(dirname -- "$self")/$link ;;
    esac
done
root=$(cd -- "$(dirname -- "$self")/.." && pwd -P)
exec "$root/python/bin/python3" "$root/launcher.py" "$@"
'''

#  bin\py-words.cmd in Windows
WINDOWS_COMMAND = '''@echo off
rem Starts py-words (launcher.py, with the Python of the installation).
"%~dp0..\\python\\python.exe" "%~dp0..\\launcher.py" %*
'''

#  macOS: el ejecutable de py-words.app (la ventana)
MACOS_APP = r'''#!/bin/sh
# Starts the window of py-words (see Resources/launcher.py).
here=$(cd -- "$(dirname -- "$0")/../Resources" && pwd -P)
exec "$here/python/bin/python3" "$here/launcher.py" gui "$@"
'''

#  macOS: las aplicaciones de Terminal abren este .command
MACOS_TERMINAL = '''#!/bin/sh
# Opens py-words {command} in Terminal.
cd ~ || exit 1
clear
exec /Applications/py-words.app/Contents/Resources/bin/py-words {command}
'''

#  (kind, command) of the Terminal applications of macOS
MACOS_TERMINAL_APPS = (('CLI', 'cli'), ('TUI', 'tui'), ('Web', 'web'))

#  Los textos de las partes del paquete de macOS, en inglés; son también
#  las claves de es.lproj/Localizable.strings
MACOS_CHOICES = (
    ('app', 'The dictionary',
     'py-words.app, the dictionary in a window, with a Python of its own.'),
    ('terminal', 'Terminal programs',
     'py-words (CLI), (TUI) and (Web): the command line, the full-screen '
     'terminal version and the web page, opened in Terminal.'),
    ('command', 'The py-words command',
     'The py-words command in /usr/local/bin, to use the programs in '
     'Terminal (py-words cli amicus).'),
)
MACOS_MINIMUM = '11.0'


# ---------------------------------------------------------------------------
#  Nombres y carpetas

def host_system() -> str:
    return {'win32': 'windows', 'darwin': 'macos'}.get(sys.platform, 'linux')


def default_arch(system: str) -> str:
    """The architecture of this computer, in the names of SYSTEM, if there
    is an installer for it (x86_64 otherwise)."""
    if system == 'windows':
        return 'x64'
    machine = platform.machine().lower()
    if system == 'macos':
        return 'arm64' if machine in ('arm64', 'aarch64') else 'x86_64'
    return 'aarch64' if machine in ('arm64', 'aarch64') else 'x86_64'


def name(system: str, arch: str) -> str:
    """The file name of the installer."""
    return {'linux': f'py-words-v.{VERSION}-linux-{arch}.run',
            'windows': f'py-words-v.{VERSION}-windows-{arch}-setup.exe',
            'macos': f'py-words-v.{VERSION}-macos-{arch}.pkg'}[system]


def older(folder: str, system: str, arch: str) -> list[str]:
    """The installers of other versions for SYSTEM and ARCH in FOLDER."""
    pattern = name(system, arch).replace(f'v.{VERSION}-', 'v.*-')
    current = name(system, arch)
    return sorted(p for p in glob.glob(os.path.join(folder, pattern))
                  if os.path.basename(p) != current)


def file_version() -> str:
    """VERSION with four numbers, as Windows wants it: 3.34.0.0."""
    numbers = [n for n in VERSION.split('.') if n.isdigit()]
    return '.'.join((numbers + ['0'] * 4)[:4])


def cache_dir() -> str:
    """Where the downloads are kept (as bundle-appimage.py)."""
    base = os.environ.get('XDG_CACHE_HOME') or \
        os.path.join(os.path.expanduser('~'), '.cache')
    path = os.path.join(base, 'py-words-build')
    os.makedirs(path, exist_ok=True)
    return path


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def download(url: str, expected: str) -> str:
    """The file at URL, downloaded into the cache unless it is there
    already, and checked against its SHA-256 EXPECTED."""
    path = os.path.join(cache_dir(), url.rsplit('/', 1)[1])
    if not os.path.isfile(path):
        print(f'Downloading {url} ...', file=sys.stderr)
        tmp = path + '.tmp'
        with urllib.request.urlopen(url, timeout=120) as r, \
                open(tmp, 'wb') as f:
            shutil.copyfileobj(r, f)
        os.replace(tmp, path)
    found = sha256(path)
    if found != expected:
        os.remove(path)
        raise OSError(f'{os.path.basename(path)}: its SHA-256 is {found}, '
                      f'not {expected}; it was deleted (try again)')
    return path


def python_tarball(system: str, arch: str) -> str:
    triple = TRIPLES[system, arch]
    url = PBS_URL.format(release=PBS_RELEASE, version=PYTHON_VERSION,
                         triple=triple)
    return download(url, PBS_SHA256[triple])


def bundle_zip():
    """The module bundle-zip.py, whose list of files is used."""
    spec = importlib.util.spec_from_file_location(
        'bundle_zip', os.path.join(ROOT, 'tools', 'bundle-zip.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
#  La carpeta del programa instalado (la "imagen"), igual en los tres
#  sistemas salvo bin/:
#
#    python/       el Python propio
#    program/      el programa
#    launcher.py   la orden py-words
#    bin/          py-words (Linux, macOS) o py-words.cmd (Windows)

def remove(path: str):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    elif os.path.lexists(path):
        os.remove(path)


def site_packages(python: str, system: str) -> str:
    if system == 'windows':
        return os.path.join(python, 'Lib', 'site-packages')
    return os.path.join(python, 'lib', f'python{PYTHON_MINOR}',
                        'site-packages')


def unpack_python(tarball: str, image: str, system: str) -> str:
    """Unpacks TARBALL (python-build-standalone, install_only or
    install_only_stripped) into IMAGE/python and trims it; returns that
    folder."""
    with tarfile.open(tarball) as t:
        t.extractall(image, filter='data')
    python = os.path.join(image, 'python')
    if not os.path.isdir(python):
        raise OSError(f'{tarball} has no python/ folder: is it an '
                      'install_only tarball of python-build-standalone?')
    if system == 'windows':
        stdlib = os.path.join(python, 'Lib')
        left_out = WINDOWS_LEFT_OUT
    else:
        stdlib = os.path.join(python, 'lib', f'python{PYTHON_MINOR}')
        left_out = UNIX_LEFT_OUT
    for pattern in left_out:
        for path in glob.glob(os.path.join(python, pattern)):
            remove(path)
    for name_ in STDLIB_LEFT_OUT:
        remove(os.path.join(stdlib, name_))
    for path in glob.glob(os.path.join(site_packages(python, system),
                                       'pip*')):
        remove(path)
    return python


def add_wheels(python: str, system: str, wheels: list[Wheel]):
    """Unpacks each of WHEELS (pure Python or for SYSTEM) into the
    site-packages of PYTHON."""
    target = site_packages(python, system)
    os.makedirs(target, exist_ok=True)
    for wheel in wheels:
        with zipfile.ZipFile(download(wheel.url, wheel.sha256)) as z:
            z.extractall(target)


def add_program(image: str, commit: str | None) -> str:
    """Copies the files of the program into IMAGE/program."""
    program = os.path.join(image, 'program')
    for f in bundle_zip().files():
        if f in NOT_INSTALLED:
            continue
        target = os.path.join(program, f)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, f), target)
    if commit:
        with open(os.path.join(program, COMMIT_FILE), 'w',
                  encoding='ascii') as f:
            f.write(commit + '\n')
    #  Compilado de antemano, si este Python es de la misma versión que el
    #  del instalador (con hashes: los archivos instalados no siempre
    #  conservan sus fechas)
    if '%d.%d' % sys.version_info[:2] == PYTHON_MINOR:
        compileall.compile_dir(
            program, quiet=1, invalidation_mode=py_compile.
            PycInvalidationMode.CHECKED_HASH)
    return program


def write(path: str, text: str, mode: int = 0o644, newline: str = '\n'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline=newline) as f:
        f.write(text)
    os.chmod(path, mode)


def make_image(image: str, system: str, tarball: str,
               wheels: list[Wheel]) -> str:
    os.makedirs(image)
    python = unpack_python(tarball, image, system)
    add_wheels(python, system, wheels)
    add_program(image, bundle_zip().built_from())
    shutil.copy2(os.path.join(INSTALLER, 'launcher.py'),
                 os.path.join(image, 'launcher.py'))
    if system == 'windows':
        write(os.path.join(image, 'bin', 'py-words.cmd'), WINDOWS_COMMAND,
              newline='\r\n')
        shutil.copy2(os.path.join(ROOT, 'icons', 'windows', 'py-words.ico'),
                     os.path.join(image, 'py-words.ico'))
    else:
        write(os.path.join(image, 'bin', 'py-words'), POSIX_COMMAND, 0o755)
    return image


# ---------------------------------------------------------------------------
#  Linux: un .run (install.sh y un tar.gz)

def normalised(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
    """INFO owned by root, readable by all, and the data read-only."""
    info.uid = info.gid = 0
    info.uname = info.gname = 'root'
    if info.isdir():
        info.mode = 0o555 if info.name == DATA else 0o755
    elif info.isfile():
        runs = info.mode & stat.S_IXUSR
        info.mode = 0o755 if runs else 0o644
        if info.name == DICTIONARY:
            info.mode = 0o444
    return info


def payload(image: str, path: str):
    """Writes IMAGE, as a tar.gz, into PATH."""
    with tarfile.open(path, 'w:gz', compresslevel=9) as t:
        for entry in sorted(os.listdir(image)):
            t.add(os.path.join(image, entry), arcname=entry,
                  filter=normalised)


def build_linux(image: str, work: str, output: str, arch: str) -> str:
    data = os.path.join(work, 'payload.tar.gz')
    payload(image, data)
    with open(os.path.join(INSTALLER, 'install.sh'), encoding='utf-8') as f:
        header = f.read()
    if not header.endswith('\n'):
        header += '\n'
    #  (el contenido empieza en la línea que sigue al script)
    line = header.count('\n') + 1
    header = header.replace('@VERSION@', VERSION) \
                   .replace('@ARCH@', arch) \
                   .replace('@PAYLOAD_LINE@', str(line)) \
                   .replace('@PAYLOAD_SHA256@', sha256(data))
    if '@' in ''.join(l for l in header.splitlines()
                      if l.startswith(('VERSION=', 'ARCH=', 'PAYLOAD_'))):
        raise ValueError('install.sh still has a @FIELD@')
    path = os.path.join(output, name('linux', arch))
    with open(path + '.tmp', 'wb') as out, open(data, 'rb') as f:
        out.write(header.encode('utf-8'))
        shutil.copyfileobj(f, out)
    os.chmod(path + '.tmp', 0o755)
    os.replace(path + '.tmp', path)
    return path


# ---------------------------------------------------------------------------
#  Windows: Inno Setup

def find_iscc() -> str | None:
    for command in ('iscc', 'ISCC'):
        if shutil.which(command):
            return shutil.which(command)
    for base in (os.environ.get('ProgramFiles(x86)'),
                 os.environ.get('ProgramFiles'),
                 os.environ.get('LOCALAPPDATA') and os.path.join(
                     os.environ['LOCALAPPDATA'], 'Programs')):
        if base:
            found = sorted(glob.glob(os.path.join(base, 'Inno Setup *',
                                                  'ISCC.exe')))
            if found:
                return found[-1]
    return None


def build_windows(image: str, output: str, arch: str,
                  iscc: str | None) -> str:
    iscc = iscc or find_iscc()
    if not iscc:
        raise OSError('Inno Setup (ISCC.exe) is not installed; it makes '
                      'the installer on Windows (--stage-only only makes '
                      'its folder)')
    path = os.path.join(output, name('windows', arch))
    subprocess.run([iscc, '/Q', f'/DAppVersion={VERSION}',
                    f'/DFileVersion={file_version()}',
                    f'/DSourceDir={os.path.abspath(image)}',
                    f'/DOutputDir={os.path.abspath(output)}',
                    f'/DOutputName={os.path.splitext(name("windows", arch))[0]}',
                    os.path.join(INSTALLER, 'py-words.iss')], check=True)
    return path


# ---------------------------------------------------------------------------
#  macOS: un .pkg con tres partes (pkgbuild y productbuild)

def info_plist(kind: str | None) -> dict:
    """The Info.plist of py-words.app (KIND None) or of a Terminal
    application."""
    title = 'py-words' if kind is None else f'py-words ({kind})'
    return {
        'CFBundleName': title,
        'CFBundleDisplayName': title,
        'CFBundleIdentifier': BUNDLE_ID if kind is None
        else f'{BUNDLE_ID}.{kind.lower()}',
        'CFBundleExecutable': APP_ID,
        'CFBundleIconFile': APP_ID,
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': VERSION,
        'CFBundleVersion': VERSION,
        'CFBundleInfoDictionaryVersion': '6.0',
        'CFBundleDevelopmentRegion': 'en',
        'LSApplicationCategoryType': 'public.app-category.education',
        'LSMinimumSystemVersion': MACOS_MINIMUM,
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright':
            'Copyright (C) 2026 Nicolas Vaughan. GPL-3.0-or-later.',
    }


def make_bundle(app: str, kind: str | None, executable: str):
    contents = os.path.join(app, 'Contents')
    write(os.path.join(contents, 'MacOS', APP_ID), executable, 0o755)
    os.makedirs(os.path.join(contents, 'Resources'), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, 'icons', 'macos', 'py-words.icns'),
                 os.path.join(contents, 'Resources', APP_ID + '.icns'))
    with open(os.path.join(contents, 'Info.plist'), 'wb') as f:
        plistlib.dump(info_plist(kind), f)


def component_plist(path: str, apps: list[str]):
    """Tells pkgbuild that the applications stay in /Applications (it
    would otherwise install over a copy of the same identifier found
    elsewhere) and may replace any version."""
    with open(path, 'wb') as f:
        plistlib.dump([{'RootRelativeBundlePath': app,
                        'BundleIsRelocatable': False,
                        'BundleIsVersionChecked': False,
                        'BundleHasStrictIdentifier': True,
                        'BundleOverwriteAction': 'upgrade'}
                       for app in apps], f)


def distribution(arch: str) -> str:
    """distribution.xml, for productbuild."""
    host = 'arm64' if arch == 'arm64' else 'x86_64'
    outline = '\n'.join(f'        <line choice="{c}"/>'
                        for c, _, _ in MACOS_CHOICES)
    choices = []
    for choice, title, description in MACOS_CHOICES:
        #  (the window is always installed)
        required = ' enabled="false"' if choice == 'app' else ''
        choices.append(
            f'    <choice id="{choice}" title={quoteattr(title)} '
            f'description={quoteattr(description)} selected="true"'
            f'{required}>\n'
            f'        <pkg-ref id="{BUNDLE_ID}.{choice}"/>\n'
            '    </choice>')
    refs = '\n'.join(
        f'    <pkg-ref id="{BUNDLE_ID}.{c}" version="{escape(VERSION)}" '
        f'onConclusion="none">{c}.pkg</pkg-ref>' for c, _, _ in MACOS_CHOICES)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!-- py-words {VERSION}, made by tools/bundle-installer.py -->
<installer-gui-script minSpecVersion="2">
    <title>py-words</title>
    <welcome file="welcome.html" mime-type="text/html"/>
    <license file="LICENCE.txt" mime-type="text/plain"/>
    <conclusion file="conclusion.html" mime-type="text/html"/>
    <options customize="allow" require-scripts="false" hostArchitectures="{host}"/>
    <domains enable_anywhere="false" enable_currentUserHome="false" enable_localSystem="true"/>
    <volume-check>
        <allowed-os-versions>
            <os-version min="{MACOS_MINIMUM}"/>
        </allowed-os-versions>
    </volume-check>
    <choices-outline>
{outline}
    </choices-outline>
{chr(10).join(choices)}
{refs}
</installer-gui-script>
'''


def stage_macos(image: str, work: str, arch: str) -> str:
    """Lays out in WORK what pkgbuild and productbuild take: roots/app,
    roots/terminal, roots/command, the component plists, the scripts, the
    resources and distribution.xml.  Returns WORK."""
    source = os.path.join(INSTALLER, 'macos')
    roots = os.path.join(work, 'roots')
    #  py-words.app: la imagen entera va en Resources
    app = os.path.join(roots, 'app', 'py-words.app')
    make_bundle(app, None, MACOS_APP)
    resources = os.path.join(app, 'Contents', 'Resources')
    for entry in os.listdir(image):
        shutil.move(os.path.join(image, entry), os.path.join(resources,
                                                             entry))
    shutil.copy2(os.path.join(source, 'uninstall.sh'),
                 os.path.join(resources, 'uninstall.sh'))
    os.chmod(os.path.join(resources, 'uninstall.sh'), 0o755)
    #  The data read-only, as in Linux (installed by root, it is anyway)
    os.chmod(os.path.join(resources, *DICTIONARY.split('/')), 0o444)
    #  Las aplicaciones de Terminal
    terminal = []
    for kind, command in MACOS_TERMINAL_APPS:
        bundle = f'py-words ({kind}).app'
        path = os.path.join(roots, 'terminal', bundle)
        make_bundle(path, kind, '#!/bin/sh\nexec open -a Terminal '
                    '"$(dirname "$0")/../Resources/run.command"\n')
        write(os.path.join(path, 'Contents', 'Resources', 'run.command'),
              MACOS_TERMINAL.format(command=command), 0o755)
        terminal.append(bundle)
    #  La orden, un enlace
    bin_dir = os.path.join(roots, 'command', 'usr', 'local', 'bin')
    os.makedirs(bin_dir)
    os.symlink('/Applications/py-words.app/Contents/Resources/bin/py-words',
               os.path.join(bin_dir, 'py-words'))
    component_plist(os.path.join(work, 'app.plist'), ['py-words.app'])
    component_plist(os.path.join(work, 'terminal.plist'), terminal)
    shutil.copytree(os.path.join(source, 'scripts'),
                    os.path.join(work, 'scripts'))
    #  Los textos, en inglés y en español
    for lproj in ('en.lproj', 'es.lproj'):
        target = os.path.join(work, 'resources', lproj)
        shutil.copytree(os.path.join(source, lproj), target)
        for page in ('welcome.html', 'conclusion.html'):
            path = os.path.join(target, page)
            with open(path, encoding='utf-8') as f:
                text = f.read().replace('@VERSION@', escape(VERSION))
            write(path, text)
        shutil.copy2(os.path.join(ROOT, 'LICENCE.txt'),
                     os.path.join(target, 'LICENCE.txt'))
    write(os.path.join(work, 'distribution.xml'), distribution(arch))
    return work


def build_macos(work: str, output: str, arch: str) -> str:
    for tool in ('pkgbuild', 'productbuild'):
        if not shutil.which(tool):
            raise OSError(f'{tool} is not installed; the .pkg is made on '
                          'macOS (--stage-only only makes its folder)')
    pkgs = os.path.join(work, 'pkgs')
    os.makedirs(pkgs)
    common = ['--version', VERSION, '--ownership', 'recommended']
    subprocess.run(['pkgbuild', '--root', os.path.join(work, 'roots', 'app'),
                    '--component-plist', os.path.join(work, 'app.plist'),
                    '--scripts', os.path.join(work, 'scripts'),
                    '--identifier', f'{BUNDLE_ID}.app',
                    '--install-location', '/Applications', *common,
                    os.path.join(pkgs, 'app.pkg')], check=True)
    subprocess.run(['pkgbuild', '--root',
                    os.path.join(work, 'roots', 'terminal'),
                    '--component-plist', os.path.join(work, 'terminal.plist'),
                    '--identifier', f'{BUNDLE_ID}.terminal',
                    '--install-location', '/Applications', *common,
                    os.path.join(pkgs, 'terminal.pkg')], check=True)
    subprocess.run(['pkgbuild', '--root',
                    os.path.join(work, 'roots', 'command'),
                    '--identifier', f'{BUNDLE_ID}.command',
                    '--install-location', '/', *common,
                    os.path.join(pkgs, 'command.pkg')], check=True)
    path = os.path.join(output, name('macos', arch))
    subprocess.run(['productbuild', '--distribution',
                    os.path.join(work, 'distribution.xml'),
                    '--resources', os.path.join(work, 'resources'),
                    '--package-path', pkgs, path + '.tmp'], check=True)
    os.replace(path + '.tmp', path)
    return path


# ---------------------------------------------------------------------------

def build(system: str, arch: str, output: str, python: str | None = None,
          extras: bool = True, stage_only: bool = False,
          iscc: str | None = None) -> str:
    """Makes the installer for SYSTEM and ARCH in OUTPUT (or, with
    STAGE_ONLY, its folder); returns its path."""
    if (system, arch) not in TRIPLES:
        raise ValueError(f'there is no installer for {system} {arch} '
                         f'(only: {", ".join(a for s, a in TRIPLES if s == system)})')
    tarball = python or python_tarball(system, arch)
    wheels = ([CERTIFI] + ([WINDOWS_CURSES] if system == 'windows' else [])
              if extras else [])
    if stage_only:
        work = os.path.join(output, f'py-words-{system}-{arch}')
        if os.path.exists(work):
            shutil.rmtree(work)
        os.makedirs(work)
        image = make_image(os.path.join(work, 'image'), system, tarball,
                           wheels)
        if system == 'macos':
            stage_macos(image, work, arch)
            os.rmdir(image)
        return work
    with tempfile.TemporaryDirectory() as work:
        image = make_image(os.path.join(work, 'image'), system, tarball,
                           wheels)
        if system == 'linux':
            path = build_linux(image, work, output, arch)
        elif system == 'windows':
            path = build_windows(image, output, arch, iscc)
        else:
            path = build_macos(stage_macos(image, work, arch), output, arch)
        #  (unas carpetas de solo lectura no dejarían borrar la temporal)
        for folder, _, _ in os.walk(work):
            os.chmod(folder, 0o755)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='tools/bundle-installer.py',
        description='Make an installer of py-words, with a Python of its '
                    'own, for Linux (.run), Windows (setup .exe) or macOS '
                    '(.pkg).')
    parser.add_argument('--system', choices=SYSTEMS, default=host_system(),
                        help='the system (default: this one)')
    parser.add_argument('--arch',
                        help='the architecture: x86_64 or aarch64 (Linux), '
                             'x64 (Windows), arm64 or x86_64 (macOS); '
                             "default: this computer's")
    parser.add_argument('-o', '--output', metavar='FOLDER',
                        help="the folder to write it in (default: dist, in "
                             "the program's folder)")
    parser.add_argument('--python', metavar='TARBALL',
                        help='an install_only tarball of '
                             'python-build-standalone to use (default: '
                             f'Python {PYTHON_VERSION}, downloaded)')
    parser.add_argument('--no-extras', action='store_true',
                        help='without certifi and windows-curses')
    parser.add_argument('--stage-only', action='store_true',
                        help='only lay out the folder of the installer, in '
                             'the output folder')
    parser.add_argument('--iscc', metavar='PATH',
                        help='the ISCC.exe of Inno Setup (default: found)')
    args = parser.parse_args(argv)
    arch = args.arch or default_arch(args.system)
    output = args.output
    if output is None:
        output = DIST
        os.makedirs(DIST, exist_ok=True)
    elif not os.path.isdir(output):
        sys.exit(f'bundle-installer.py: there is no folder {output}')
    try:
        path = build(args.system, arch, output, args.python,
                     not args.no_extras, args.stage_only, args.iscc)
    except (OSError, subprocess.CalledProcessError, ValueError,
            tarfile.TarError, zipfile.BadZipFile) as e:
        sys.exit(f'bundle-installer.py: {e}')
    if args.stage_only:
        print(f'Laid out {path}.')
        return
    #  En dist/, solo el más reciente de cada sistema y arquitectura
    if args.output is None:
        for old in older(DIST, args.system, arch):
            os.remove(old)
            print(f'Removed {old}.')
    print(f'Wrote {path} ({os.path.getsize(path) / 1e6:.1f} MB).')


if __name__ == '__main__':
    main()
