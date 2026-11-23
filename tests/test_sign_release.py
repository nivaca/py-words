"""Pruebas de tools/sign_release.py, que firma los archivos de una versión:
cada archivo y SHA256SUMS firmados, y cada firma comprobada con solo la
clave pública publicada; un archivo cambiado después, u otra clave, no se
comprueban.

Firman con una clave hecha aquí, sin frase de paso, en un GNUPGHOME
temporal de la prueba: nunca con la del usuario ni en su llavero.
"""

import contextlib
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import sign_release  # noqa: E402

PATH = '/usr/bin:/bin'


def make_key(home, name):
    """A key without a passphrase in HOME: its fingerprint, and the file
    of its public key."""
    os.makedirs(home, mode=0o700)
    env = {'GNUPGHOME': home, 'PATH': PATH}
    subprocess.run(['gpg', '--batch', '--passphrase', '', '--quick-gen-key',
                    f'{name} <{name}@example.org>', 'ed25519', 'sign',
                    'never'], env=env, check=True, capture_output=True)
    out = subprocess.run(['gpg', '--batch', '--with-colons',
                          '--list-secret-keys'], env=env, check=True,
                         capture_output=True, text=True).stdout
    fpr = next(line.split(':')[9] for line in out.splitlines()
               if line.startswith('fpr'))
    public = os.path.join(os.path.dirname(home), f'{name}.asc')
    with open(public, 'wb') as f:
        f.write(subprocess.run(['gpg', '--batch', '--armor', '--export',
                                fpr], env=env, check=True,
                               capture_output=True).stdout)
    return fpr, public


def kill_agents(home):
    #  (los gpg-agent y keyboxd de la prueba, antes de borrar su carpeta)
    subprocess.run(['gpgconf', '--kill', 'all'],
                   env={'GNUPGHOME': home, 'PATH': PATH},
                   capture_output=True)


@unittest.skipUnless(shutil.which('gpg') and shutil.which('gpgconf')
                     and sys.platform != 'win32', 'needs gpg')
class SignRelease(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='sign-release-test-')
        self.addCleanup(shutil.rmtree, self.dir, True)
        home = os.path.join(self.dir, 'gnupg')
        self.fpr, self.public = make_key(home, 'release')
        self.addCleanup(kill_agents, home)
        #  sign_release firma con el GNUPGHOME del entorno: el de la prueba
        patch = mock.patch.dict(os.environ, {'GNUPGHOME': home})
        patch.start()
        self.addCleanup(patch.stop)
        self.sums = os.path.join(self.dir, 'SHA256SUMS')

    def write(self, name, data):
        path = os.path.join(self.dir, name)
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def run_main(self, *args):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            code = sign_release.main(list(args))
        return code, err.getvalue()

    def test_every_file_signed_and_checked(self):
        files = [self.write(name, data) for name, data in (
            ('py-words-v.1.0.zip', b'zip'), ('py-words_1.0-1_all.deb', b'deb'),
            ('py-words-1.0-1.fc45.noarch.rpm', b'rpm'))]
        code, err = self.run_main('--key', self.fpr, '--public', self.public,
                                  '--sums', self.sums, *files)
        self.assertEqual(code, 0, err)
        with open(self.sums, encoding='utf-8') as f:
            sums = f.read()
        expected = ''
        for path in files:
            with open(path, 'rb') as f:
                expected += (f'{hashlib.sha256(f.read()).hexdigest()}  '
                             f'{os.path.basename(path)}\n')
        self.assertEqual(sums, expected)
        for path in files + [self.sums]:
            with open(path + '.asc', encoding='ascii') as f:
                self.assertTrue(f.read().startswith(
                    '-----BEGIN PGP SIGNATURE-----'))
        self.assertEqual(sign_release.verify(files + [self.sums],
                                             self.public), [])
        # A file changed after it was signed: its signature is bad
        with open(files[0], 'ab') as f:
            f.write(b', changed')
        bad = sign_release.verify(files, self.public)
        self.assertEqual(len(bad), 1)
        self.assertTrue(bad[0].startswith('py-words-v.1.0.zip:'), bad)

    def test_another_key_does_not_check(self):
        """The key published must be the one that signed: with another,
        nothing verifies, and the release stops."""
        other_home = os.path.join(self.dir, 'other-gnupg')
        _, other = make_key(other_home, 'other')
        self.addCleanup(kill_agents, other_home)
        path = self.write('py-words-v.1.0.zip', b'zip')
        code, err = self.run_main('--key', self.fpr, '--public', other,
                                  '--sums', self.sums, path)
        self.assertEqual(code, 1)
        self.assertIn('do not verify', err)

    def test_missing_files_are_named(self):
        missing = os.path.join(self.dir, 'nothing.zip')
        code, err = self.run_main('--key', self.fpr, '--public', self.public,
                                  '--sums', self.sums, missing)
        self.assertEqual(code, 1)
        self.assertIn('missing', err)
        self.assertFalse(os.path.exists(self.sums))

    def test_two_files_of_the_same_name_are_refused(self):
        os.makedirs(os.path.join(self.dir, 'a'))
        os.makedirs(os.path.join(self.dir, 'b'))
        first = self.write(os.path.join('a', 'x.zip'), b'1')
        second = self.write(os.path.join('b', 'x.zip'), b'2')
        code, err = self.run_main('--key', self.fpr, '--public', self.public,
                                  '--sums', self.sums, first, second)
        self.assertEqual(code, 1)
        self.assertIn('same name', err)


if __name__ == '__main__':
    unittest.main()
