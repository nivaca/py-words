"""Runs the regression tests in regression/ against the program.

Each test feeds regression/NN_name/input.txt to `words -f`, with the developer
modes of regression/WORD.MDV_template, and compares the output with
regression/NN_name/expected.txt.  A test can change the settings with its
own regression/NN_name/config.toml (the configuration file, see config.py),
which comes first.  Each run has a configuration folder of its own, so no
test's settings reach another.  After an intended change to the output,
regenerate the expected files with

    UPDATE_GOLDEN=1 python3 -m unittest discover -s tests

and review the differences (git diff tests/regression/) before committing them.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import isolate  # noqa: F401  (before anything that reads settings)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
TEST_DIR = os.path.join(HERE, 'regression')
#  Tras un cambio a propósito en la salida: UPDATE_GOLDEN=1, y revisar el
#  git diff de los esperados antes del commit.  Siempre.
UPDATE = bool(os.environ.get('UPDATE_GOLDEN'))


def run_words(args, workdir, config=None):
    """Runs words in WORKDIR, with a cache there (the first run fills it,
    the others read it), a new configuration folder, and CONFIG (a
    config.toml) in it if given."""
    folder = tempfile.mkdtemp(dir=workdir, prefix='config-')
    if config:
        shutil.copy(config, os.path.join(folder, 'config.toml'))
    env = dict(os.environ,
               WHITAKERS_WORDS_CACHE=os.path.join(workdir, 'cache'),
               WHITAKERS_WORDS_CONFIG=folder)
    env.pop('WHITAKERS_WORDS_DATADIR', None)
    return subprocess.run(
        [sys.executable, os.path.join(ROOT, 'words.py'), '--datadir', DATA]
        + args,
        cwd=workdir, env=env, capture_output=True, stdin=subprocess.DEVNULL,
        check=False)


class RegressionTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        shutil.copy(os.path.join(TEST_DIR, 'WORD.MDV_template'),
                    os.path.join(cls.tmp.name, 'WORD.MDV'))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def compare(self, args, expected_path, config=None):
        result = run_words(args, self.tmp.name, config)
        self.assertEqual(result.stderr, b'')
        self.assertEqual(result.returncode, 0)
        if UPDATE:
            with open(expected_path, 'wb') as f:
                f.write(result.stdout)
            return
        with open(expected_path, 'rb') as f:
            expected = f.read()
        self.assertEqual(result.stdout.decode().splitlines(),
                         expected.decode().splitlines())

    def check(self, name):
        config = os.path.join(TEST_DIR, name, 'config.toml')
        self.compare(['-f', os.path.join(TEST_DIR, name, 'input.txt')],
                     os.path.join(TEST_DIR, name, 'expected.txt'),
                     config if os.path.isfile(config) else None)

    def test_multusque(self):
        self.check('05_multusque')

    def test_aeneid(self):
        self.check('10_aeneid')

    def test_ius(self):
        self.check('20_ius')

    def test_qualdupes(self):
        self.check('30_qualdupes')

    def test_english(self):
        self.check('40_english')

    def test_forms(self):
        """Dictionary forms of every kind, with the English examples."""
        self.check('50_forms')

    def test_developer_modes(self):
        self.check('60_developer_modes')

    def test_no_dictionary_forms(self):
        self.check('70_no_dictionary_forms')

    def test_unknowns_only(self):
        self.check('75_unknowns_only')

    def test_command_line(self):
        self.compare(['rem', 'acu', 'tetigisti'],
                     os.path.join(TEST_DIR, 'expected.txt'))


if __name__ == '__main__':
    unittest.main()
