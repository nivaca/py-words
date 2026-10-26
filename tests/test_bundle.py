"""Tests of bundle-zip.py, which makes the zip of the distribution."""

import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)
import importlib.util  # noqa: E402

import version  # noqa: E402
from version import VERSION  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BundleTests(unittest.TestCase):

    def bundle(self, *args) -> list[str]:
        """Runs bundle-zip.py; returns the names in the zip it made."""
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable,
                            os.path.join(ROOT, 'bundle-zip.py'), '-o', tmp,
                            *args], check=True, capture_output=True)
            self.assertEqual(os.listdir(tmp), [f'py-words-v.{VERSION}.zip'])
            with zipfile.ZipFile(os.path.join(tmp, os.listdir(tmp)[0])) as z:
                return z.namelist()

    def test_the_distribution(self):
        names = self.bundle()
        top = f'py-words-v.{VERSION}/'
        self.assertTrue(all(n.startswith(top) for n in names))
        for needed in ('words.py', 'words_gui.py', 'README.md',
                       'LICENCE.txt', 'data/dictionary.xml',
                       'data/languages/es.xml', 'data/interface/es.xml'):
            self.assertIn(top + needed, names)
        for n in names:
            parts = n[len(top):].split('/')
            self.assertFalse(any(p.startswith('.') for p in parts), n)
            self.assertNotIn('__pycache__', parts)
            self.assertFalse(n.endswith(('.bak', '.tmp', '.pyc', '.zip')), n)
            self.assertNotEqual(parts[0], 'tests', n)

    def test_what_is_not_part_of_it(self):
        #  (in a folder of its own, made for the test)
        spec = importlib.util.spec_from_file_location(
            'bundle_zip', os.path.join(ROOT, 'bundle-zip.py'))
        bundle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bundle)
        with tempfile.TemporaryDirectory() as tmp:
            for f in ('words.py', 'TAGS', 'site/index.html',
                      'local-only/notes.org', 'data/dictionary.xml',
                      'data/site/x.xml', 'data/TAGS'):
                os.makedirs(os.path.dirname(os.path.join(tmp, f)),
                            exist_ok=True)
                open(os.path.join(tmp, f), 'w').close()
            bundle.HERE = tmp
            self.assertEqual(
                [f.replace(os.sep, '/') for f in bundle.files()],
                ['words.py', 'data/TAGS', 'data/dictionary.xml',
                 'data/site/x.xml'])

    def test_with_the_tests(self):
        names = self.bundle('--tests')
        self.assertIn(f'py-words-v.{VERSION}/tests/test_bundle.py', names)

    def test_the_commit(self):
        """The zip says the commit it was made from, for "About"."""
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, GITHUB_SHA='a' * 40)
            subprocess.run([sys.executable,
                            os.path.join(ROOT, 'bundle-zip.py'), '-o', tmp],
                           check=True, capture_output=True, env=env)
            with zipfile.ZipFile(os.path.join(tmp, os.listdir(tmp)[0])) as z:
                self.assertEqual(
                    z.read(f'py-words-v.{VERSION}/COMMIT').decode(),
                    'a' * 40 + '\n')


class CommitTests(unittest.TestCase):
    """The commit in "About": that of the file COMMIT, or of git."""

    def test_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(version.commit(tmp))      # (not a clone)
            with open(os.path.join(tmp, 'COMMIT'), 'w') as f:
                f.write('b' * 40 + '\n')
            self.assertEqual(version.commit(tmp), 'b' * 40)
            with open(os.path.join(tmp, 'COMMIT'), 'w') as f:
                f.write('not a commit\n')
            self.assertIsNone(version.commit(tmp))

    def test_about(self):
        old = version.commit
        version.commit = lambda: 'c' * 40
        try:
            lines = version.about().split('\n')
        finally:
            version.commit = old
        self.assertEqual(lines[1], version.URL)
        self.assertEqual(lines[2],
                         f'Commit: {version.URL}/commit/' + 'c' * 40)


if __name__ == '__main__':
    unittest.main()
