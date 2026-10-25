"""Tests of the settings files, the command line, the interactive mode and
the converter."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the package, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

import config
import words as cli, words_convert as convert, xmldata
from lexicon import Lexicon
from session import Session
from settings import Settings, MODES

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')

LEXICON = None


def lexicon():
    global LEXICON
    if LEXICON is None:
        LEXICON = Lexicon.load(DATA)
    return LEXICON


class InTempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.tmp.cleanup()


class SettingsTests(InTempDir):

    def setUp(self):
        super().setUp()
        self.old_config = os.environ['PY_WORDS_CONFIG']
        os.environ['PY_WORDS_CONFIG'] = os.path.join(self.tmp.name,
                                                            'config')

    def tearDown(self):
        os.environ['PY_WORDS_CONFIG'] = self.old_config
        super().tearDown()

    def test_round_trip(self):
        s = Settings(trim_output=False, explain_codes=True, trim_medieval=True,
                     start_file_character='%')
        path = s.save('parameters')
        self.assertEqual(s.save('developer'), path)
        t = Settings()
        messages = t.load('/nonexistent')
        self.assertEqual(messages, [f'Using the settings in {path}'])
        self.assertEqual(t, s)

    def test_config_comes_first(self):
        """An old WORD.MOD is read, but the configuration file wins."""
        with open('WORD.MOD', 'w') as f:
            f.write('TRIM_OUTPUT   N\nDO_FIXES   N\n')
        Settings(trim_output=True, use_affixes=True,
                 explain_codes=True).save('parameters')
        s = Settings()
        messages = s.load('/nonexistent')
        # both were read, and [developer] was added to the file
        self.assertEqual(len(messages), 3)
        self.assertTrue(any(m.startswith('Completed the configuration')
                            for m in messages))
        self.assertTrue(s.trim_output and s.use_affixes and s.explain_codes)

    def test_bad_config(self):
        os.makedirs(os.environ['PY_WORDS_CONFIG'])
        path = os.path.join(os.environ['PY_WORDS_CONFIG'],
                            'config.toml')
        with open(path, 'w') as f:
            f.write('[parameters]\ntrim_output = "no"\ndo_fixes = false\n'
                    'colour = true\n[developer]\n'
                    'start_file_character = "a"\n')
        s = Settings()
        [message] = s.load('/nonexistent')
        self.assertIn('trim_output: must be true or false', message)
        self.assertIn('[parameters] colour: unknown setting', message)
        self.assertIn('start_file_character: must be one punctuation',
                      message)
        self.assertTrue(s.trim_output)
        self.assertFalse(s.use_affixes)
        self.assertEqual(s.start_file_character, '@')
        with open(path, 'w') as f:
            f.write('[parameters\n')
        [message] = Settings().load('/nonexistent')
        self.assertIn('its settings are not used', message)

    def test_old_files(self):
        """Files written by the Ada program, with modes that no longer
        exist."""
        with open(os.path.join(HERE, 'regression', 'WORD.MDV_template')) as f:
            text = f.read()
        with open('WORD.MDV', 'w') as f:
            f.write(text.replace('PAUSE_IN_SCREEN_OUTPUT            N',
                                 'PAUSE_IN_SCREEN_OUTPUT            Y'))
        s = Settings(pause_in_screen_output=False)
        self.assertEqual(s.read('WORD.MDV'), [])
        self.assertTrue(s.pause_in_screen_output)

    def test_removed_settings(self):
        """The settings of the files WORD.OUT, WORD.UNK and WORD.STA,
        which no longer exist, are passed over in silence, and dropped
        when the section is saved again."""
        import config
        os.makedirs(os.environ['PY_WORDS_CONFIG'])
        with open(config.config_path(), 'w') as f:
            f.write('[parameters]\nhave_output_file = true\n'
                    'trim_output = false\n[developer]\n'
                    'write_statistics_file = true\n')
        s = Settings()
        self.assertEqual(s.load('/nonexistent'),
                         [f'Using the settings in {config.config_path()}'])
        self.assertFalse(s.trim_output)
        s.save('parameters', only=['trim_output'])
        self.assertNotIn('have_output_file', config.section('parameters'))

    def test_renamed_settings(self):
        """The names of earlier versions are read as the new ones (two
        made one: on if either is; the new name wins), and the file is
        written again with the new names."""
        import config
        os.makedirs(os.environ['PY_WORDS_CONFIG'])
        with open(config.config_path(), 'w') as f:
            f.write('[parameters]\ndo_fixes = false\nshow_age = false\n'
                    'show_frequency = true\ndo_tricks = false\n'
                    'use_tricks = true\n[developer]\n'
                    'show_dictionary_codes = false\nomit_archaic = false\n')
        s = Settings()
        self.assertEqual(s.load('/nonexistent'),
                         [f'Using the settings in {config.config_path()}'])
        self.assertFalse(s.use_affixes)
        self.assertTrue(s.explain_codes)
        self.assertTrue(s.use_tricks)
        self.assertFalse(s.show_codes)      # (now a parameter)
        saved = config.read()               # (written with the new names)
        self.assertEqual(saved['parameters'], {
            'use_tricks': True, 'use_affixes': False, 'explain_codes': True,
            'show_codes': False})
        self.assertEqual(saved['developer'], {})
        t = Settings()
        t.load('/nonexistent')
        self.assertEqual(t, s)

    def test_bad_line(self):
        with open('WORD.MOD', 'w') as f:
            f.write('TRIM_OUTPUT   maybe\nDO_FIXES   N\n')
        s = Settings()
        problems = s.read('WORD.MOD')
        self.assertEqual(len(problems), 1)
        self.assertTrue(s.trim_output)
        self.assertFalse(s.use_affixes)


def run(*args, stdin=''):
    return subprocess.run([sys.executable, os.path.join(ROOT, 'words.py'),
                           '--datadir', DATA] + list(args),
                          input=stdin.encode(), capture_output=True,
                          check=False)


class CommandLineTests(InTempDir):

    def test_words(self):
        out = run('amicus').stdout.decode()
        self.assertIn('amicus, amici  noun, 2nd declension', out)
        self.assertIn('amīc-us', out)

    def test_meanings_only(self):
        out = run('-m', 'amicus').stdout.decode()
        self.assertIn('A friend, patron', out)
        self.assertNotIn('amīc-us', out)

    def test_config_is_made_at_the_first_start(self):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, 'py-words', 'config.toml')
        env = dict(os.environ, PY_WORDS_CONFIG=os.path.dirname(path))
        command = [sys.executable, os.path.join(ROOT, 'words.py')]
        result = subprocess.run(command + ['amo'], env=env,
                                capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(os.path.isfile(path))       # (folder made too)
        with open(path) as f:
            text = f.read()
        self.assertIn('[parameters]\n', text)
        self.assertIn('trim_output = true', text)
        # --config shows it; a second start leaves it as it is
        result = subprocess.run(command + ['--config'], env=env,
                                capture_output=True)
        self.assertEqual(result.stdout.decode(),
                         f'The configuration file is {path}\n')
        os.utime(path, (0, 0))
        subprocess.run(command + ['amo'], env=env, capture_output=True)
        self.assertEqual(os.path.getmtime(path), 0)
        # the data folder can be given there
        os.environ['PY_WORDS_CONFIG'], old = os.path.dirname(path), \
            os.environ['PY_WORDS_CONFIG']
        try:
            data = config.read()
            data['data']['folder'] = '/nonexistent/py-words-data'
            config.write(data)
        finally:
            os.environ['PY_WORDS_CONFIG'] = old
        result = subprocess.run(command + ['amo'], env=env,
                                capture_output=True)
        self.assertIn(b'/nonexistent/py-words-data', result.stderr)

    def test_interactive_start_says_so(self):
        folder = tempfile.mkdtemp()
        os.environ['PY_WORDS_CONFIG'], old = folder, \
            os.environ['PY_WORDS_CONFIG']
        try:
            messages = Settings().load('/nonexistent')
            path = os.path.join(folder, 'config.toml')
            self.assertEqual(messages, [
                f'Created the configuration file {path}, with the settings '
                'in use'])
            self.assertEqual(Settings().load('/nonexistent'),
                             [f'Using the settings in {path}'])
            # a file with only the fonts (made by "Font…") is completed,
            # keeping them
            with open(path, 'w') as f:
                f.write('[fonts]\ntext_size = 12\n')
            messages = Settings(trim_output=False).load('/nonexistent')
            self.assertEqual(messages, [
                f'Completed the configuration file {path}, with the '
                'settings in use'])
            self.assertEqual(config.section('fonts'), {'text_size': 12})
            self.assertIs(config.section('parameters')['trim_output'],
                          False)
            self.assertIn('pearse_codes', config.section('developer'))
        finally:
            os.environ['PY_WORDS_CONFIG'] = old

    def test_glosses_or_words(self):
        """use_glosses (on by usual) and --glosses / --no-glosses."""
        self.assertIn('amāv-istī      2SG.PRF.ACT.IND',
                      run('amavisti').stdout.decode())
        self.assertIn('amāv-istī      2nd person singular perfect active '
                      'indicative', run('--no-glosses', 'amavisti')
                      .stdout.decode())
        config_dir = os.path.join(self.tmp.name, 'config')
        os.makedirs(config_dir)
        with open(os.path.join(config_dir, 'config.toml'), 'w') as f:
            f.write('[parameters]\nuse_glosses = false\n')
        old = os.environ['PY_WORDS_CONFIG']
        os.environ['PY_WORDS_CONFIG'] = config_dir
        try:
            self.assertIn('genitive plural', run('amicorum').stdout.decode())
            self.assertIn('GEN.PL', run('--glosses', 'amicorum')
                          .stdout.decode())
        finally:
            os.environ['PY_WORDS_CONFIG'] = old

    def test_english(self):
        out = run('-e', 'friend', '--pos', 'ADJ').stdout.decode()
        self.assertIn('adjective', out)
        self.assertNotIn('noun', out)

    def test_file_and_output(self):
        with open('in.txt', 'w') as f:
            f.write('rem acu\n~E\nfriend\n')
        result = run('-f', 'in.txt', '-o', 'out.txt')
        self.assertEqual(result.stdout, b'')
        with open('out.txt') as f:
            out = f.read()
        self.assertIn('res, rei', out)
        self.assertIn('amicus, amici', out)

    def test_standard_input(self):
        out = run(stdin='rem\n').stdout.decode()
        self.assertIn('res, rei', out)

    def test_version(self):
        out = run('--version').stdout.decode()
        self.assertIn('py-words', out)
        self.assertIn('William Whitaker', out)
        self.assertIn('nivaca@fastmail.com', out)
        self.assertIn('https://github.com/nivaca/py-words', out)
        self.assertIn('Associate Professor of Literature', out)
        self.assertIn('Universidad de los Andes, Bogotá, Colombia', out)

    def test_bad_data_directory(self):
        result = run('--datadir', self.tmp.name, 'rem')
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'dictionary.xml', result.stderr)


class InteractiveTests(InTempDir):

    def session(self):
        out = io.StringIO()
        return Session(lexicon(), Settings(pause_in_screen_output=False),
                       write=out.write), out

    def test_dictionary_line(self):
        """show_entry_source gives each entry's number in its
        dictionary file (not in the golden files: it changes whenever a
        word is added)."""
        session, out = self.session()
        session.settings.show_entry_source = True
        session.process('amicorum')
        amicus = next(e for e in lexicon().entries
                      if e.meaning.startswith('friend, ally, disciple'))
        self.assertIn(f'amicus, amici  noun, 2nd declension, masculine  '
                      f'[XXXBO]  (general dictionary)  (entry {amicus.id})',
                      out.getvalue())

    def repl(self, *lines):
        session, out = self.session()
        replies = iter(lines)

        def ask(prompt):
            """The next reply (KeyboardInterrupt: as if Ctrl-C was
            pressed)."""
            out.write(prompt)
            try:
                reply = next(replies)
            except StopIteration:
                raise EOFError
            if reply is KeyboardInterrupt:
                raise KeyboardInterrupt
            return reply
        cli.repl(session, ask, out.write)
        return session, out.getvalue()

    def test_about(self):
        _, out = self.repl('~a')
        self.assertIn('William Whitaker', out)
        self.assertIn('Associate Professor of Literature', out)

    def test_ctrl_c_at_the_prompt_does_not_quit(self):
        _, out = self.repl(KeyboardInterrupt, 'amicus')
        self.assertIn('Ctrl-C does not quit', out)
        self.assertIn('amicus, amici', out)         # (and it goes on)

    def test_ctrl_c_stops_a_dialogue(self):
        session, out = self.repl('#', 'n', KeyboardInterrupt, 'amicus')
        self.assertIn('(interrupted)', out)
        self.assertIn('A friend, patron', out)      # (without dictionary forms)
        self.assertFalse(session.settings.show_dictionary_forms)  # (done)
        self.assertNotEqual(config.section('parameters').get(
            'show_dictionary_forms'), False)        # (not saved)

    def test_ctrl_c_outside_interactive_mode(self):
        """Ctrl-C ends the program quietly (no traceback)."""
        from unittest import mock
        with mock.patch.object(cli, 'load', side_effect=KeyboardInterrupt), \
                self.assertRaises(SystemExit) as e, \
                contextlib.redirect_stderr(io.StringIO()):
            cli.main(['amicus'])
        self.assertEqual(e.exception.code, 130)

    def test_lookup_and_quit(self):
        _, out = self.repl('amicus', '', '', 'never read')
        self.assertTrue(out.startswith('Type a Latin word'))  # (no credits)
        self.assertIn('amicus, amici', out)
        self.assertIn('another empty line quits', out)

    def test_language(self):
        _, out = self.repl('~E', 'friend', '~L', 'amicus')
        self.assertIn('English to Latin', out)
        self.assertIn('amīc-us', out)

    def test_file(self):
        with open('words.txt', 'w') as f:
            f.write('rem\n')
        _, out = self.repl('@words.txt', '@missing.txt')
        self.assertIn('res, rei', out)
        self.assertIn('Cannot read missing.txt', out)

    def test_parameters_dialogue(self):
        # show_dictionary_forms: N; show_only_meanings: Enter; then a space
        # skips the rest
        session, out = self.repl('#', 'n', '', ' ')
        self.assertIn('What the results show:', out)
        self.assertFalse(session.settings.show_dictionary_forms)
        # (not saved: skipping the rest skips the question too)
        self.assertNotEqual(config.section('parameters').get(
            'show_dictionary_forms'), False)

    def test_parameters_help_and_save(self):
        # show_dictionary_forms (after ?), then the others, the interface
        # (Enter keeps it), and save
        replies = ['#', '?', 'y'] + [''] * (len(MODES) - 1) + ['', 'y']
        session, out = self.repl(*replies)
        self.assertIn('Show each entry with its principal parts', out)
        self.assertIn('How words are looked up:', out)
        self.assertIn(f'Saved in {config.config_path()}', out)
        self.assertIs(config.section('parameters')['show_dictionary_forms'],
                      True)
        os.remove(config.config_path())

    def test_developer_modes(self):
        # show_entry_source: Y, then stop
        session, out = self.repl('!', 'y', ' ', 'rem')
        self.assertTrue(session.settings.show_entry_source)
        self.assertFalse(os.path.exists('WORD.STA'))


class ConvertTests(InTempDir):
    DICTLINE = ('amic               amic                                   '
                '                    N      2 1 M P          X X X B O '
                'friend, ally;\r\n')
    INFLECTS = ('-- nouns\r\nN      2 1 NOM S M  1 2 us  X A   -- note\r\n')
    UNIQUES = 'memento\r\nV      0 0 FUTP ACTIVE  IMP 2 S TRANS     ' \
        'X X X B X\r\nremember!;\r\n'
    ADDONS = ('TACKON que\r\nX\r\n-que = and;\r\n'
              'PREFIX ad\r\nX X\r\n- to, towards;\r\n'
              'SUFFIX ic\r\nN 1 ADJ 1 1 POS 2\r\n-ic; of;\r\n')

    def test_convert(self):
        for name, text in (('DICTLINE.GEN', self.DICTLINE),
                           ('INFLECTS.LAT', self.INFLECTS),
                           ('UNIQUES.LAT', self.UNIQUES),
                           ('ADDONS.LAT', self.ADDONS)):
            with open(name, 'w', encoding='latin-1', newline='') as f:
                f.write(text)
        written = list(convert.convert('.', '.'))
        self.assertEqual(written, ['dictionary.xml', 'inflections.xml',
                                   'uniques.xml', 'addons.xml'])
        [(entry, _)] = xmldata.read_dictionary('dictionary.xml')
        self.assertEqual(entry.stems, ('amic', 'amic', '', ''))
        self.assertEqual(entry.meaning, 'friend, ally;')
        [(infl, _)] = xmldata.read_inflections('inflections.xml')
        self.assertEqual((infl.ending, infl.key), ('us', 1))
        with open('inflections.xml') as f:
            self.assertIn('<!-- note-->', f.read())
        [(u, _)] = xmldata.read_uniques('uniques.xml')
        self.assertEqual(u.word, 'memento')
        addons = [a for a, _ in xmldata.read_addons('addons.xml')]
        self.assertEqual([a.fix for a in addons], ['que', 'ad', 'ic'])
        self.assertEqual(addons[2].target.pos.name, 'ADJ')

    def test_error(self):
        with open('DICTLINE.GEN', 'w') as f:
            f.write(self.DICTLINE.replace('N      2 1', 'Q      2 1'))
        with self.assertRaises(convert.ConvertError):
            convert.convert_dictline('DICTLINE.GEN')


if __name__ == '__main__':
    unittest.main()
