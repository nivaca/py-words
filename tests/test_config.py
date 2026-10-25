"""Tests of the configuration file (config.py)."""

import os
import sys
import tempfile
import tomllib
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

import config  # noqa: E402
import lexicon  # noqa: E402


class ConfigTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = dict(os.environ)
        os.environ['PY_WORDS_CONFIG'] = self.tmp.name
        os.environ.pop('PY_WORDS_DATADIR', None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)
        self.tmp.cleanup()

    def test_where(self):
        self.assertEqual(config.config_path(),
                         os.path.join(self.tmp.name, 'config.toml'))
        del os.environ['PY_WORDS_CONFIG']
        if sys.platform not in ('win32', 'darwin'):
            os.environ['XDG_CONFIG_HOME'] = '/somewhere'
            self.assertEqual(config.config_path(),
                             '/somewhere/py-words/config.toml')
            del os.environ['XDG_CONFIG_HOME']
            self.assertEqual(config.config_path(), os.path.expanduser(
                '~/.config/py-words/config.toml'))

    def test_none_yet(self):
        self.assertEqual(config.read(), {})
        self.assertEqual(config.section('fonts'), {})
        self.assertIsNone(config.data_folder())

    def test_update_keeps_the_other_sections(self):
        config.update('fonts', {'text_size': 14,
                                'text_family': 'A "quoted" \\ name'})
        config.update('parameters', {'trim_output': False})
        with open(config.config_path(), 'rb') as f:
            data = tomllib.load(f)          # (valid TOML)
        self.assertEqual(data['fonts'], {'text_size': 14,
                                         'text_family': 'A "quoted" \\ name'})
        self.assertEqual(data['parameters'], {'trim_output': False})
        self.assertEqual(data['data'], {'folder': ''})
        config.update('fonts', {})
        self.assertNotIn('text_size', config.read().get('fonts', {}))
        self.assertEqual(config.section('parameters'), {'trim_output': False})

    def test_comments(self):
        config.update('parameters', {'trim_output': True})
        with open(config.config_path()) as f:
            text = f.read()
        self.assertIn('# Leave out the least likely results', text)
        self.assertIn('[fonts]', text)      # (shown, though empty)

    def test_data_folder(self):
        self.assertEqual(lexicon.default_datadir(), lexicon.DATA_DIR)
        config.update('data', {'folder': '~/latin'})
        self.assertEqual(lexicon.default_datadir(),
                         os.path.expanduser('~/latin'))
        os.environ['PY_WORDS_DATADIR'] = '/env'
        self.assertEqual(lexicon.default_datadir(), '/env')

    def test_old_variable_names(self):
        """$WHITAKERS_WORDS_... of earlier versions still count; the new
        $PY_WORDS_... comes first."""
        del os.environ['PY_WORDS_CONFIG']
        os.environ['WHITAKERS_WORDS_CONFIG'] = '/old'
        self.assertEqual(config.config_dir(), '/old')
        os.environ['PY_WORDS_CONFIG'] = '/new'
        self.assertEqual(config.config_dir(), '/new')
        os.environ.pop('PY_WORDS_HISTORY', None)
        os.environ['WHITAKERS_WORDS_HISTORY'] = ''
        self.assertEqual(config.env('HISTORY'), '')

    def test_unreadable(self):
        with open(config.config_path(), 'w') as f:
            f.write('[fonts\n')
        with self.assertRaises(config.ConfigError):
            config.read()
        self.assertEqual(config.section('fonts'), {})
        with self.assertRaises(config.ConfigError):
            config.update('fonts', {'text_size': 12})
        with open(config.config_path()) as f:
            self.assertEqual(f.read(), '[fonts\n')     # (left alone)


if __name__ == '__main__':
    unittest.main()
