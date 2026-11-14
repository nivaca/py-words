#!/usr/bin/env python3
"""Publishes a release of py-words on GitHub (with gh) and on Codeberg
(with tea): the tag vVERSION (the version of version.py), with the zip and
the AppImage attached, and (--rpm) the signed RPM, also published on
Copr.

    python3 tools/release.py [--redo] [--notes TEXT | --notes-file FILE]
                             [--no-build] [--no-appimage] [--rpm [--no-copr]]
                             [--only github|codeberg] [--dry-run] [--yes]

In order, each step only if it is needed:

1. checks that the repository is on main, with nothing left to commit,
   and that gh and tea are installed;
2. makes the zip and the AppImage in dist/ (tools/bundle-zip.py and
   tools/bundle-appimage.py), unless --no-build (then those in dist/ are used);
   with --rpm, also the signed RPM and its public key in build/rpm/
   (packaging/build-rpm.sh --sign; gpg asks for the passphrase);
3. tags HEAD as vVERSION.  If the tag is there already on another commit,
   it stops, unless --redo moves it;
4. pushes main and the tag to the remote (origin, which pushes to both
   GitHub and Codeberg; --redo pushes the tag with --force);
5. on each forge, makes the release of the tag, or keeps the one there
   is, and attaches the files to it, replacing those of the same name;
6. with --rpm, sends the (signed) source RPM to Copr (copr-cli build,
   project nivaca/py-words), unless --no-copr.  Copr builds it for each
   Fedora of the project and signs it with its own key; each build needs
   a higher version-release than the last, so the spec must have been
   bumped (rpmdev-bumpspec, see packaging/COPR.org).

Before doing anything, it shows the commands it will run and asks; --yes
does not ask, --dry-run only shows them.  The notes of a new release are
--notes, --notes-file, or else made by GitHub from the commits (on
Codeberg, none); a release that is there keeps its notes.

The repositories are found from the push addresses of the remote; tea
uses the login named codeberg unless --tea-login says another.

When the tag is pushed, GitHub runs .github/workflows/appimage.yml, which
makes the AppImage again and replaces the one attached here (same
commit, same file name).
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
SPEC = os.path.join('packaging', 'py-words.spec')
RPM_KEY = os.path.join('build', 'rpm', 'RPM-GPG-KEY-py-words')
COPR_PROJECT = 'py-words'       # (of the copr-cli user, nivaca)


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

    # Running ----------------------------------------------------------

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

    # Checks -----------------------------------------------------------

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
        if self.args.rpm:
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
        #  With --redo the tag is always pushed with --force: the remote
        #  may push to several forges, and only the first is seen here
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

    def __call__(self):
        args = self.args
        self.forges = [args.only] if args.only else ['github', 'codeberg']
        self.files = [ZIP] + ([] if args.no_appimage else [APPIMAGE])
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
                    'the AppImage and (--rpm) the RPM.')
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
                        help='use the zip and AppImage in dist/, without '
                             'making them again')
    parser.add_argument('--no-appimage', action='store_true',
                        help='only the zip')
    parser.add_argument('--rpm', action='store_true',
                        help='also the signed RPM and its public key '
                             '(packaging/build-rpm.sh --sign), and a Copr '
                             'build of it')
    parser.add_argument('--no-copr', action='store_true',
                        help='with --rpm, do not send it to Copr')
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
