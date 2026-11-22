#!/usr/bin/env python3
"""Publica una versión de py-words en GitHub (con gh) y en Codeberg (con
tea): la etiqueta vVERSION (la versión de version.py), con el zip, el
AppImage, el instalador de Linux (.run) y el .deb firmado adjuntos y
(--rpm) el RPM firmado, que se publica también en Copr.

    python3 tools/release.py [--redo] [--notes TEXT | --notes-file FILE]
                             [--no-build] [--no-appimage] [--no-installer]
                             [--no-deb]
                             [--rpm [--no-copr]]
                             [--only github|codeberg] [--remote REMOTE]
                             [--tea-login LOGIN] [--dry-run] [--yes]
    python3 tools/release.py --installers [--dry-run] [--yes]

En orden, y cada paso solo si hace falta:

1. comprueba que el repositorio esté en main, sin nada por confirmar, y
   que gh y tea estén instalados (con --rpm, también rpmbuild y, salvo
   --no-copr, copr-cli), y que la clave de firma (la del .deb y la del
   RPM) esté en el llavero de gpg del computador;
2. hace el zip, el AppImage y el instalador de Linux en dist/
   (tools/bundle-zip.py, tools/bundle-appimage.py y
   tools/bundle-installer.py --system linux), salvo con --no-build
   (entonces usa los que hay en dist/); también el .deb, con su firma aparte (.deb.asc), en
   dist/ (packaging/build-deb.py --sign), y con --rpm el RPM firmado y su
   clave pública en build/rpm/ (packaging/build-rpm.sh --sign); gpg pide
   la frase de paso;
3. pone la etiqueta vVERSION en HEAD.  Si la etiqueta ya está en otro
   commit, se detiene, salvo que --redo la mueva;
4. sube main y la etiqueta al remoto (origin, que sube tanto a GitHub como
   a Codeberg; --redo sube la etiqueta con --force);
5. en cada forja, crea la versión de la etiqueta, o conserva la que
   exista, y le adjunta los archivos, reemplazando los del mismo nombre;
6. con --rpm, manda el RPM fuente (firmado) a Copr (copr-cli build,
   proyecto nivaca/py-words), salvo con --no-copr.  Copr lo construye para
   cada Fedora del proyecto y lo firma con su propia clave; cada
   construcción necesita una versión-release mayor que la anterior, así
   que el spec debe haberse subido de versión (rpmdev-bumpspec, véase
   packaging/COPR.org).

Antes de hacer nada, muestra las órdenes que va a correr y pregunta; con
--yes no pregunta, y con --dry-run solo las muestra.  Las notas de una
versión nueva son las de --notes o --notes-file, o si no las que GitHub
hace a partir de los commits (en Codeberg, ninguna); una versión que ya
existe conserva sus notas.

Los repositorios se deducen de las direcciones de subida del remoto; tea
usa el login llamado codeberg, salvo que --tea-login nombre otro.

Cuando se sube la etiqueta, GitHub corre .github/workflows/appimage.yml,
que vuelve a hacer el AppImage y reemplaza el que se adjuntó aquí (mismo
commit, mismo nombre de archivo), y .github/workflows/installers.yml,
que hace los instaladores de Windows y de macOS (que solo se pueden hacer
en esos sistemas), los prueba y los adjunta a la versión de GitHub, junto
con otra copia del de Linux.  Cuando ese workflow termina,
--installers (sin nada más) los baja de la versión de GitHub y los
adjunta a la de Codeberg, que de otro modo quedaría sin ellos.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from version import VERSION  # noqa: E402

TAG = f'v{VERSION}'
ZIP = os.path.join('dist', f'py-words-v.{VERSION}.zip')
APPIMAGE = os.path.join('dist', f'py-words-v.{VERSION}-x86_64.AppImage')
#  El instalador de Linux (tools/bundle-installer.py); los de Windows y
#  macOS los hace GitHub (installers.yml)
INSTALLER = os.path.join('dist', f'py-words-v.{VERSION}-linux-x86_64.run')
#  Los que hace GitHub, y adónde los baja --installers para Codeberg
CI_INSTALLERS = [os.path.join('build', 'installers', name) for name in (
    f'py-words-v.{VERSION}-windows-x64-setup.exe',
    f'py-words-v.{VERSION}-macos-arm64.pkg',
    f'py-words-v.{VERSION}-macos-x86_64.pkg')]
#  El .deb que hace packaging/build-deb.py (su REVISION es la 1) y su firma
DEB = os.path.join('dist', f'py-words_{VERSION}-1_all.deb')
DEB_SIGNATURE = DEB + '.asc'
SPEC = os.path.join('packaging', 'py-words.spec')
RPM_KEY = os.path.join('build', 'rpm', 'RPM-GPG-KEY-py-words')
COPR_PROJECT = 'py-words'       # (del usuario de copr-cli, nivaca)


def signing_key() -> str:
    """The project's signing key, as packaging/build-rpm.sh pins it."""
    with open(os.path.join(ROOT, 'packaging', 'build-rpm.sh'),
              encoding='utf-8') as f:
        m = re.search(r'SIGNING_KEY="\$\{SIGNING_KEY:-([0-9A-F]{40})\}"',
                      f.read())
    return m.group(1) if m else ''


def rpm_nvr() -> str:
    """NAME-VERSION-RELEASE of the RPM that packaging/build-rpm.sh makes,
    as its spec says (py-words-3.10-1.fc45); stops if the spec is not at
    VERSION."""
    try:
        nvr = subprocess.run(
            ['rpmspec', '-q', '--srpm', '--qf',
             '%{name}-%{version}-%{release}', SPEC], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sys.exit('release.py: rpmspec cannot read the spec (sudo dnf '
                 'install rpm-build)')
    if not nvr.startswith(f'py-words-{VERSION}-'):
        sys.exit(f'release.py: {SPEC} is not at version {VERSION} '
                 '(rpmdev-bumpspec -n VERSION)')
    return nvr


def rpm() -> str:
    """The path of the RPM (py-words-3.10-1.fc45.noarch.rpm)."""
    return os.path.join('build', 'rpm', 'RPMS', 'noarch',
                        rpm_nvr() + '.noarch.rpm')


def srpm() -> str:
    """The path of the source RPM, which goes to Copr."""
    return os.path.join('build', 'rpm', 'SRPMS', rpm_nvr() + '.src.rpm')
BRANCH = 'main'


class Release:
    """The steps, run (or only shown) in order."""

    def __init__(self, args):
        self.args = args
        self.planned = []           # (description, command)

    # Ejecución --------------------------------------------------------

    def read(self, *command, check=True) -> str:
        """The output of COMMAND (which only reads, so it runs even with
        --dry-run)."""
        out = subprocess.run(command, cwd=ROOT, capture_output=True,
                             text=True)
        if check and out.returncode != 0:
            sys.exit(f'release.py: {shlex.join(command)}: '
                     f'{(out.stderr or out.stdout).strip()}')
        return out.stdout.strip() if out.returncode == 0 else ''

    def plan(self, description: str, *command):
        self.planned.append((description, list(command)))

    def run_plan(self):
        if not self.planned:
            print('Nothing to do.')
            return
        print(f'Releasing {TAG}:')
        for description, command in self.planned:
            print(f'\n  # {description}\n  {shlex.join(command)}')
        print()
        if self.args.dry_run:
            return
        if not self.args.yes:
            answer = input('Run these commands? [y/N] ').strip().lower()
            if answer not in ('y', 'yes', 's', 'sí', 'si'):
                sys.exit('Nothing done.')
        for description, command in self.planned:
            print(f'\n==> {description}', flush=True)
            if subprocess.run(command, cwd=ROOT).returncode != 0:
                sys.exit(f'release.py: failed: {shlex.join(command)}\n'
                         'The steps before it were done; after fixing '
                         'the cause, run the script again (with --redo '
                         'if the tag was already moved).')
        print(f'\nReleased {TAG}.')

    # Las comprobaciones -----------------------------------------------

    def check(self):
        tools = ('git',) + tuple(
            t for t, f in (('gh', 'github'), ('tea', 'codeberg'))
            if f in self.forges)
        if self.args.rpm:
            tools += ('rpmbuild',) + (
                () if self.args.no_copr else ('copr-cli',))
        for tool in tools:
            if not shutil.which(tool):
                sys.exit(f'release.py: {tool} is not installed')
        if self.args.rpm or DEB in self.files:
            key = signing_key()
            if not key or subprocess.run(
                    ['gpg', '--batch', '--list-secret-keys', key],
                    capture_output=True).returncode != 0:
                sys.exit(f'release.py: the signing key {key or "(none)"} is '
                         "not in this machine's gpg keyring; import it "
                         'first (see packaging/COPR.org)')
        branch = self.read('git', 'rev-parse', '--abbrev-ref', 'HEAD')
        if branch != BRANCH:
            sys.exit(f'release.py: on branch {branch}, not {BRANCH}')
        if self.read('git', 'status', '--porcelain'):
            message = 'there are changes not committed (see git status)'
            if not self.args.dry_run:
                sys.exit(f'release.py: {message}')
            print(f'release.py: (dry run) {message}', file=sys.stderr)

    def repos(self) -> dict:
        """{forge: owner/name}, from the push addresses of the remote."""
        urls = self.read('git', 'remote', 'get-url', '--push', '--all',
                         self.args.remote).split('\n')
        found = {}
        for url in urls:
            m = re.search(r'(github\.com|codeberg\.org)[:/]+'
                          r'([^/]+/[^/]+?)(?:\.git)?/?$', url)
            if m:
                found['github' if 'github' in m[1] else 'codeberg'] = m[2]
        for forge in self.forges:
            if forge not in found:
                sys.exit(f'release.py: the remote {self.args.remote} does '
                         f'not push to {forge} (git remote -v)')
        return found

    # Steps ------------------------------------------------------------

    def build(self):
        if self.args.no_build:
            for f in self.files:
                if not os.path.isfile(os.path.join(ROOT, f)):
                    sys.exit(f'release.py: there is no {f} (leave out '
                             '--no-build to make it)')
            return
        self.plan('Make the zip', sys.executable,
                  os.path.join('tools', 'bundle-zip.py'))
        if APPIMAGE in self.files:
            self.plan('Make the AppImage', sys.executable,
                      os.path.join('tools', 'bundle-appimage.py'))
        if INSTALLER in self.files:
            self.plan('Make the installer for Linux', sys.executable,
                      os.path.join('tools', 'bundle-installer.py'),
                      '--system', 'linux', '--arch', 'x86_64')
        if DEB in self.files:
            self.plan('Make the signed .deb', sys.executable, os.path.join(
                'packaging', 'build-deb.py'), '--sign')
        if RPM_KEY in self.files:
            self.plan('Make the signed RPM', os.path.join(
                'packaging', 'build-rpm.sh'), '--sign')

    def tag(self):
        head = self.read('git', 'rev-parse', 'HEAD')
        tagged = self.read('git', 'rev-parse', '--verify', '--quiet',
                           f'refs/tags/{TAG}^{{commit}}', check=False)
        if tagged == head:
            pass
        elif tagged and not self.args.redo:
            sys.exit(f'release.py: {TAG} is already the tag of '
                     f'{tagged[:7]}, not of HEAD ({head[:7]}); --redo '
                     'moves it (and replaces the files of the releases)')
        else:
            self.plan('Move the tag to HEAD' if tagged else 'Tag HEAD',
                      'git', 'tag', '--force', '--annotate', TAG,
                      '--message', TAG)
        self.plan(f'Push {BRANCH}', 'git', 'push', self.args.remote,
                  BRANCH)
        #  Con --redo la etiqueta se sube siempre con --force: el remoto
        #  puede subir a varias forjas, y aquí solo se ve la primera
        if self.args.redo:
            self.plan('Push the tag (replacing it on the forges)', 'git',
                      'push', '--force', self.args.remote,
                      f'refs/tags/{TAG}')
            return
        remote = self.read('git', 'ls-remote', '--tags', self.args.remote,
                           f'refs/tags/{TAG}^{{}}', check=False)
        on_remote = remote.split()[0] if remote else ''
        if on_remote == head:
            return
        if on_remote:
            sys.exit(f'release.py: on {self.args.remote}, {TAG} is the tag '
                     f'of {on_remote[:7]}; --redo moves it')
        self.plan('Push the tag', 'git', 'push', self.args.remote,
                  f'refs/tags/{TAG}')

    def notes(self, github: bool) -> list[str]:
        if self.args.notes_file:
            return ['--notes-file' if github else '--note-file',
                    self.args.notes_file]
        if self.args.notes:
            return ['--notes' if github else '--note', self.args.notes]
        return ['--generate-notes'] if github else []

    def github(self, repo: str):
        exists = subprocess.run(
            ['gh', 'release', 'view', TAG, '--repo', repo],
            cwd=ROOT, capture_output=True).returncode == 0
        if exists:
            self.plan('GitHub: attach the files to the release (replacing '
                      'those there)', 'gh', 'release', 'upload', TAG,
                      *self.files, '--clobber', '--repo', repo)
        else:
            self.plan('GitHub: make the release', 'gh', 'release',
                      'create', TAG, *self.files, '--title', TAG,
                      '--verify-tag', *self.notes(True), '--repo', repo)

    def codeberg(self, repo: str):
        where = ['--repo', repo, '--login', self.args.tea_login]
        releases = self.tea_json('releases', 'ls', '--limit', '50', *where)
        exists = any(TAG in (r.get('tagname'), r.get('tag'))
                     for r in releases)
        if exists:
            names = {a.get('name') for a in self.tea_json(
                'releases', 'assets', 'ls', TAG, *where)}
            old = [os.path.basename(f) for f in self.files
                   if os.path.basename(f) in names]
            if old:
                self.plan('Codeberg: remove the files of the same name '
                          '(tea cannot replace them)', 'tea', 'releases',
                          'assets', 'delete', TAG, *old, '--confirm',
                          *where)
            self.plan('Codeberg: attach the files to the release', 'tea',
                      'releases', 'assets', 'create', TAG, *self.files,
                      *where)
        else:
            assets = [a for f in self.files for a in ('--asset', f)]
            self.plan('Codeberg: make the release', 'tea', 'releases',
                      'create', '--tag', TAG, '--title', TAG,
                      *self.notes(False), *assets, *where)

    def tea_json(self, *command) -> list[dict]:
        """The rows tea gives in JSON, with its keys made plain ("tag-_name"
        is tagname)."""
        out = self.read('tea', *command, '--output', 'json')
        try:
            rows = json.loads(out or '[]')
        except ValueError:
            sys.exit(f'release.py: tea {" ".join(command)}: not JSON: '
                     f'{out[:200]}')
        return [{re.sub('[^a-z]', '', k.lower()): v for k, v in r.items()}
                for r in rows]

    def copr(self):
        if self.args.no_build and not os.path.isfile(
                os.path.join(ROOT, srpm())):
            sys.exit(f'release.py: there is no {srpm()} (leave out '
                     '--no-build to make it)')
        self.plan(f'Copr: build the RPM (project {COPR_PROJECT})',
                  'copr-cli', 'build', COPR_PROJECT, srpm())

    # All --------------------------------------------------------------

    def installers(self):
        """--installers: those of Windows and macOS, from the release on
        GitHub (made by installers.yml) to the one on Codeberg."""
        self.forges = ['github', 'codeberg']
        self.files = CI_INSTALLERS
        for tool in ('gh', 'tea'):
            if not shutil.which(tool):
                sys.exit(f'release.py: {tool} is not installed')
        repos = self.repos()
        names = [os.path.basename(f) for f in CI_INSTALLERS]
        on_github = self.read('gh', 'release', 'view', TAG, '--repo',
                              repos['github'], '--json', 'assets', '--jq',
                              '.assets[].name', check=False).split('\n')
        missing = [n for n in names if n not in on_github]
        if missing:
            sys.exit(f'release.py: the release {TAG} on GitHub does not have '
                     f'{", ".join(missing)} (has installers.yml finished?)')
        patterns = [a for n in names for a in ('--pattern', n)]
        self.plan('Download the installers from GitHub', 'gh', 'release',
                  'download', TAG, *patterns, '--dir',
                  os.path.join('build', 'installers'), '--clobber',
                  '--repo', repos['github'])
        self.codeberg(repos['codeberg'])
        self.run_plan()

    def __call__(self):
        args = self.args
        if args.installers:
            self.installers()
            return
        self.forges = [args.only] if args.only else ['github', 'codeberg']
        self.files = [ZIP] + ([] if args.no_appimage else [APPIMAGE])
        if not args.no_installer:
            self.files.append(INSTALLER)
        if not args.no_deb:
            self.files += [DEB, DEB_SIGNATURE]
        if args.rpm:
            self.files += [rpm(), RPM_KEY]
        self.check()
        repos = self.repos()
        self.build()
        self.tag()
        for forge in self.forges:
            getattr(self, forge)(repos[forge])
        if args.rpm and not args.no_copr:
            self.copr()
        self.run_plan()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='tools/release.py',
        description=f'Publish {TAG} on GitHub and Codeberg, with the zip, '
                    'the AppImage, the installer for Linux, the .deb and '
                    '(--rpm) the RPM.')
    parser.add_argument('--redo', action='store_true',
                        help=f'move {TAG} to HEAD if it is on another commit '
                             '(here and on the remote), and replace the '
                             'files of the releases')
    notes = parser.add_mutually_exclusive_group()
    notes.add_argument('--notes', metavar='TEXT',
                       help='the notes of a new release')
    notes.add_argument('--notes-file', metavar='FILE',
                       help='the notes of a new release, from FILE')
    parser.add_argument('--no-build', action='store_true',
                        help='use the zip, the AppImage and the installer in '
                             'dist/, without making them again')
    parser.add_argument('--no-appimage', action='store_true',
                        help='without the AppImage')
    parser.add_argument('--no-installer', action='store_true',
                        help='without the installer for Linux '
                             '(tools/bundle-installer.py)')
    parser.add_argument('--no-deb', action='store_true',
                        help='without the .deb (packaging/build-deb.py '
                             '--sign)')
    parser.add_argument('--rpm', action='store_true',
                        help='also the signed RPM and its public key '
                             '(packaging/build-rpm.sh --sign), and a Copr '
                             'build of it')
    parser.add_argument('--no-copr', action='store_true',
                        help='with --rpm, do not send it to Copr')
    parser.add_argument('--installers', action='store_true',
                        help='only copy the installers for Windows and macOS '
                             f'from the release {TAG} on GitHub (made by '
                             'installers.yml) to the one on Codeberg')
    parser.add_argument('--only', choices=('github', 'codeberg'),
                        help='publish on one forge only')
    parser.add_argument('--remote', default='origin',
                        help='the remote to push to (default: origin)')
    parser.add_argument('--tea-login', default='codeberg',
                        help='the login of tea for Codeberg (default: '
                             'codeberg)')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='only show the commands')
    parser.add_argument('-y', '--yes', action='store_true',
                        help='do not ask before running them')
    args = parser.parse_args(argv)
    if args.notes_file:
        args.notes_file = os.path.abspath(args.notes_file)
    Release(args)()


if __name__ == '__main__':
    main()
