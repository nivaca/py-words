#!/usr/bin/env python3
"""Publica una versión de py-words en GitHub (con gh) y en Codeberg (con
tea): la etiqueta vVERSION (la versión de version.py), firmada, con el
zip, el AppImage, el instalador de Linux (.run), el .deb y el RPM firmado
adjuntos (el RPM se publica también en Copr), cada uno con su firma
(ARCHIVO.asc), con SHA256SUMS y su firma, y con la clave pública que las
comprueba todas.

Todo se firma con la clave del proyecto (SIGNING_KEY de
packaging/build-rpm.sh), y cada firma se comprueba, con la clave pública
que se publica, antes de publicar nada.

    python3 tools/release.py [--redo] [--notes TEXT | --notes-file FILE]
                             [--no-build] [--no-appimage] [--no-installer]
                             [--no-deb]
                             [--no-rpm | --no-copr]
                             [--only github|codeberg] [--remote REMOTE]
                             [--tea-login LOGIN] [--no-android]
                             [--dry-run] [--yes]
    python3 tools/release.py --installers [--dry-run] [--yes]

En orden, y cada paso solo si hace falta:

1. comprueba que el repositorio esté en main, sin nada por confirmar, y
   que gh, tea y gpg estén instalados (salvo con --no-rpm, también
   rpmbuild y, salvo --no-copr, copr-cli), y que la clave de firma esté en
   el llavero de gpg del computador;
2. hace el zip, el AppImage y el instalador de Linux en dist/
   (tools/bundle-zip.py, tools/bundle-appimage.py y
   tools/bundle-installer.py --system linux), salvo con --no-build
   (entonces usa los que hay en dist/); también el .deb, con su firma aparte (.deb.asc), en
   dist/ (packaging/build-deb.py --sign), y salvo con --no-rpm el RPM
   firmado en build/rpm/ (packaging/build-rpm.sh --sign, que comprueba su
   firma); gpg pide la frase de paso.  Después firma cada archivo
   (tools/sign_release.py: ARCHIVO.asc, dist/SHA256SUMS y su .asc) y
   comprueba cada firma con solo la clave pública que se publica
   (packaging/RPM-GPG-KEY-py-words);
3. pone la etiqueta vVERSION en HEAD, firmada con la misma clave (git tag
   --sign), y la comprueba (git tag --verify).  Si la etiqueta ya está en
   otro commit, se detiene, salvo que --redo la mueva;
4. sube main y la etiqueta al remoto (origin, que sube tanto a GitHub como
   a Codeberg; --redo sube la etiqueta con --force);
5. en cada forja, crea la versión de la etiqueta, o conserva la que
   exista, y le adjunta los archivos, reemplazando los del mismo nombre;
6. salvo con --no-rpm, manda el RPM fuente (firmado) a Copr (copr-cli build,
   proyecto nivaca/py-words), salvo con --no-copr.  Copr lo construye para
   cada Fedora del proyecto y lo firma con su propia clave; cada
   construcción necesita una versión-release mayor que la anterior, así
   que el spec debe haberse subido de versión (rpmdev-bumpspec, véase
   packaging/COPR.org);
7. salvo con --no-apt o --no-deb, añade el paquete de Debian al repositorio
   APT de estos programas, github.com/nivaca/apt, con su herramienta
   (../apt/tools/apt_repo.py: el índice firmado y comprobado);
8. al final, si hay un clon de py-words para Android (en
   ../../Android/py-words-android o ../../android/py-words-android, o donde
   diga PY_WORDS_ANDROID), corre su
   tools/update-py-words.py --tag vVERSION, que pone esta versión en la app
   y publica la versión de la app que la lleva; pregunta antes por su
   cuenta.  --no-android lo omite, igual que --only codeberg (el submódulo
   de la app trae py-words de GitHub).

Antes de hacer nada, muestra las órdenes que va a correr y pregunta; con
--yes no pregunta, y con --dry-run solo las muestra.  Las notas de una
versión nueva son las de --notes o --notes-file, o si no las que GitHub
hace a partir de los commits (en Codeberg, ninguna); una versión que ya
existe conserva sus notas.

Los repositorios se deducen de las direcciones de subida del remoto; tea
usa el login llamado codeberg, salvo que --tea-login nombre otro.

Cuando se sube la etiqueta, GitHub corre .github/workflows/appimage.yml,
que vuelve a hacer el AppImage, y .github/workflows/installers.yml, que
hace los instaladores de Windows y de macOS (que solo se pueden hacer en
esos sistemas), los prueba y los adjunta a la versión de GitHub, junto
con otra copia del de Linux.  Ninguno reemplaza el AppImage ni el
instalador de Linux que ya estén en la versión: se quedan los firmados
aquí.
Cuando ese workflow termina, --installers (sin nada más) los baja de la
versión de GitHub, los firma (ARCHIVO.asc, y sus sumas en
SHA256SUMS-installers, con su firma) y adjunta las firmas a las dos
versiones, y los instaladores a la de Codeberg, que de otro modo quedaría
sin ellos.

El depósito para Zenodo se reúne en dist/zenodo/ después de la etiqueta
(tools/zenodo.py collect: el árbol de la etiqueta, firmado, con SHA256SUMS y
la clave pública) y al final se sube a Zenodo y se publica, con un DOI nuevo
(con el token de $ZENODO_TOKEN o del llavero), salvo con --no-zenodo; con
--zenodo-draft queda como borrador, para publicarlo a mano.
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
#  Sus sumas, aparte de SHA256SUMS (hecho antes, sin ellos)
CI_SUMS = os.path.join('build', 'installers', 'SHA256SUMS-installers')
#  El .deb que hace packaging/build-deb.py (su REVISION es la 1) y su firma
DEB = os.path.join('dist', f'py-words_{VERSION}-1_all.deb')
# La herramienta del repositorio APT de estos programas: el proyecto apt,
# junto a este (github.com/nivaca/apt)
APT_TOOL = os.path.join(os.path.dirname(ROOT), 'apt', 'tools', 'apt_repo.py')
SPEC = os.path.join('packaging', 'py-words.spec')
# The public key published with every release, which checks every signature
PUBLIC_KEY = os.path.join('packaging', 'RPM-GPG-KEY-py-words')
SUMS = os.path.join('dist', 'SHA256SUMS')
#  El clon de py-words para Android, cuyo submódulo py-words/ sigue a este
#  repositorio (véase android() más abajo)
#  (la carpeta se escribe Android o android según el computador: vale la
#  que exista)
_PROJECTS = os.path.dirname(os.path.dirname(ROOT))
ANDROID = os.environ.get('PY_WORDS_ANDROID') or next(
    (path for path in (os.path.join(_PROJECTS, folder, 'py-words-android')
                       for folder in ('Android', 'android'))
     if os.path.isdir(path)),
    os.path.join(_PROJECTS, 'android', 'py-words-android'))
COPR_PROJECT = 'py-words'       # (del usuario de copr-cli, nivaca)


def zenodo_token() -> bool:
    """Whether tools/zenodo.py finds a Zenodo token, in $ZENODO_TOKEN or
    in the desktop keyring (secret-tool)."""
    tool = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'tools', 'zenodo.py')
    done = subprocess.run([sys.executable, tool, 'check-token'],
                          capture_output=True, check=False)
    return done.returncode == 0


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
        tools = ('git', 'gpg') + tuple(
            t for t, f in (('gh', 'github'), ('tea', 'codeberg'))
            if f in self.forges)
        if self.args.rpm:
            tools += ('rpmbuild',) + (
                () if self.args.no_copr else ('copr-cli',))
        for tool in tools:
            if not shutil.which(tool):
                sys.exit(f'release.py: {tool} is not installed')
        self.check_key()
        branch = self.read('git', 'rev-parse', '--abbrev-ref', 'HEAD')
        if branch != BRANCH:
            sys.exit(f'release.py: on branch {branch}, not {BRANCH}')
        if self.read('git', 'status', '--porcelain'):
            message = 'there are changes not committed (see git status)'
            if not self.args.dry_run:
                sys.exit(f'release.py: {message}')
            print(f'release.py: (dry run) {message}', file=sys.stderr)

    def check_key(self):
        """The signing key in gpg, and the public key published with it."""
        #  Todo se firma, siempre: sin la clave no hay versión
        key = signing_key()
        if not key or subprocess.run(
                ['gpg', '--batch', '--list-secret-keys', key],
                capture_output=True).returncode != 0:
            sys.exit(f'release.py: the signing key {key or "(none)"} is '
                     "not in this machine's gpg keyring; import it "
                     'first (see packaging/COPR.org)')
        if not os.path.isfile(os.path.join(ROOT, PUBLIC_KEY)):
            sys.exit(f'release.py: there is no {PUBLIC_KEY}, the public '
                     'key published with the release')

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
        if self.args.rpm:
            self.plan('Make the signed RPM', os.path.join(
                'packaging', 'build-rpm.sh'), '--sign')

    def sign(self):
        """Every file published signed (FILE.asc), with SHA256SUMS and its
        signature, and each signature checked with only the public key
        published."""
        signed = [f for f in self.files if f != PUBLIC_KEY]
        self.plan('Sign the files, and check each signature with the '
                  'published key', sys.executable,
                  os.path.join('tools', 'sign_release.py'), '--key',
                  signing_key(), '--public', PUBLIC_KEY, '--sums', SUMS,
                  *signed)
        #  (la firma del .deb que hace build-deb.py se rehace aquí, igual)
        self.files = (signed + [f + '.asc' for f in signed]
                      + [SUMS, SUMS + '.asc', PUBLIC_KEY])

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
            self.plan('Move the tag to HEAD, signed' if tagged
                      else 'Tag HEAD, signed', 'git', 'tag', '--force',
                      '--sign', '--local-user', signing_key(), TAG,
                      '--message', TAG)
            self.plan('Check the signature of the tag', 'git', 'tag',
                      '--verify', TAG)
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
        GitHub (made by installers.yml) to the one on Codeberg, each
        signed here, with the signatures attached to both."""
        self.forges = ['github', 'codeberg']
        self.files = CI_INSTALLERS
        for tool in ('gh', 'tea', 'gpg'):
            if not shutil.which(tool):
                sys.exit(f'release.py: {tool} is not installed')
        self.check_key()
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
        #  Se firman aquí, como los demás archivos de la versión, con sus
        #  propias sumas; las firmas van a las dos forjas
        self.plan('Sign the installers, and check each signature with the '
                  'published key', sys.executable,
                  os.path.join('tools', 'sign_release.py'), '--key',
                  signing_key(), '--public', PUBLIC_KEY, '--sums', CI_SUMS,
                  *CI_INSTALLERS)
        signatures = ([f + '.asc' for f in CI_INSTALLERS]
                      + [CI_SUMS, CI_SUMS + '.asc'])
        self.plan('GitHub: attach their signatures to the release', 'gh',
                  'release', 'upload', TAG, *signatures, '--clobber',
                  '--repo', repos['github'])
        self.files = CI_INSTALLERS + signatures
        self.codeberg(repos['codeberg'])
        self.run_plan()

    def apt(self):
        """The Debian package added to the APT repository of these programs
        (github.com/nivaca/apt), by its own tool, which keeps only the newest
        version, signs the index and checks it before uploading."""
        if not os.path.isfile(APT_TOOL):
            sys.exit(f'release.py: {APT_TOOL} is not there (clone '
                     'github.com/nivaca/apt beside this project, or use '
                     '--no-apt)')
        self.plan('APT: add the Debian package to github.com/nivaca/apt',
                  sys.executable, APT_TOOL, 'add', DEB)

    def zenodo_collect(self):
        """The deposit of the release for Zenodo, in dist/zenodo/ (tools/zenodo.py): the tree of the tag, signed,
        with SHA256SUMS and the public key, each signature checked with only that key."""
        self.plan('Zenodo: collect the deposit in dist/zenodo/', sys.executable, 'tools/zenodo.py', 'collect',
                  '--tag', TAG)

    def zenodo_upload(self):
        """Unless --no-zenodo, dist/zenodo/ uploaded to Zenodo and published (with
        --zenodo-draft, only as a draft, published there by hand)."""
        if self.args.no_zenodo:
            return
        # (sin token se para aquí, antes de hacer nada, y no al final de la versión)
        if not zenodo_token() and not self.args.dry_run:
            sys.exit('release.py: the upload to Zenodo needs a token (see tools/zenodo.py check-token); '
                     '--no-zenodo leaves it out')
        publish = [] if self.args.zenodo_draft else ['--publish']
        what = ' as a draft (not published)' if self.args.zenodo_draft else ' and publish it'
        self.plan('Zenodo: upload the deposit' + what, sys.executable, 'tools/zenodo.py', 'upload', *publish)

    def __call__(self):
        args = self.args
        if args.installers:
            self.installers()
            return
        self.forges = [args.only] if args.only else ['github', 'codeberg']
        self.files = [ZIP] + ([] if args.no_appimage else [APPIMAGE])
        if not args.no_installer:
            self.files.append(INSTALLER)
        args.rpm = not args.no_rpm      # (the signed RPM, unless --no-rpm)
        if not args.no_deb:
            self.files.append(DEB)
        if args.rpm:
            self.files.append(rpm())
        self.files.append(PUBLIC_KEY)
        self.check()
        repos = self.repos()
        self.build()
        self.sign()
        self.tag()
        self.zenodo_collect()
        for forge in self.forges:
            getattr(self, forge)(repos[forge])
        if args.rpm and not args.no_copr:
            self.copr()
        if not args.no_deb and not args.no_apt:
            self.apt()
        self.zenodo_upload()
        self.run_plan()
        self.android()

    def android(self):
        """Put this version in py-words for Android and release the app,
        with that project's own script, if there is a clone of it."""
        script = os.path.join(ANDROID, 'tools', 'update-py-words.py')
        if self.args.no_android or 'github' not in self.forges:
            return
        if not os.path.isfile(script):
            print(f'\n(No py-words for Android at {ANDROID}; the app is '
                  'not updated.)')
            return
        command = [sys.executable, script, '--tag', TAG]
        if self.args.dry_run:
            command.append('--dry-run')
        elif self.args.yes:
            command.append('--yes')
        print(f'\n==> py-words for Android\n  {shlex.join(command)}',
              flush=True)
        if subprocess.run(command, cwd=ANDROID).returncode != 0:
            if self.args.dry_run:
                sys.exit('release.py: py-words for Android would not be '
                         'updated (see above)')
            sys.exit(f'release.py: {TAG} is released, but py-words for '
                     'Android was not updated; after fixing the cause, run '
                     f'{shlex.join(command)} again')


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='tools/release.py',
        description=f'Publish {TAG} on GitHub and Codeberg, with the zip, '
                    'the AppImage, the installer for Linux, the .deb and '
                    'the RPM (also on Copr), all signed.')
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
                        help='(the signed RPM, and a Copr build of it, are '
                             'made always now: kept for older scripts)')
    parser.add_argument('--no-rpm', action='store_true',
                        help='without the RPM (nor its Copr build)')
    parser.add_argument('--no-copr', action='store_true',
                        help='do not send the RPM to Copr')
    parser.add_argument('--no-apt', action='store_true',
                        help='do not add the Debian package to the APT '
                             'repository (github.com/nivaca/apt)')
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
    parser.add_argument('--no-android', action='store_true',
                        help='do not put this version in py-words for '
                             'Android afterwards (its '
                             'tools/update-py-words.py)')
    parser.add_argument('--no-zenodo', action='store_true',
                        help='do not upload dist/zenodo/ to Zenodo (by default it is uploaded and '
                             'published, with the token in $ZENODO_TOKEN or the keyring)')
    parser.add_argument('--zenodo-draft', action='store_true',
                        help='upload it to Zenodo as a draft, not published')
    parser.add_argument('--zenodo', action='store_true',
                        help='(the upload to Zenodo is made always now, unless '
                             '--no-zenodo: kept for older scripts)')
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
