"""Tests of the settings files, the command line, the interactive mode and
the converter."""

import io
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the package, when run from anywhere
os.environ['WHITAKERS_WORDS_CACHE'] = ''   # (leave the user's cache alone)

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

    def test_round_trip(self):
        s = Settings(trim_output=False, do_examples=True, omit_archaic=False,
                     start_file_character='%')
        s.save_modes()
        s.save_dev_modes()
        t = Settings()
        messages = t.load('/nonexistent')
        self.assertEqual(len(messages), 2)
        self.assertEqual(t, s)

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

    def test_bad_line(self):
        with open('WORD.MOD', 'w') as f:
            f.write('TRIM_OUTPUT   maybe\nDO_FIXES   N\n')
        s = Settings()
        problems = s.read('WORD.MOD')
        self.assertEqual(len(problems), 1)
        self.assertTrue(s.trim_output)
        self.assertFalse(s.do_fixes)


def run(*args, stdin=''):
    return subprocess.run([sys.executable, os.path.join(ROOT, 'words.py'),
                           '--datadir', DATA] + list(args),
                          input=stdin.encode(), capture_output=True,
                          check=False)


class CommandLineTests(InTempDir):

    def test_words(self):
        out = run('amicus').stdout.decode()
        self.assertIn('amicus, amici  noun, 2nd declension', out)
        self.assertIn('amic-us', out)

    def test_meanings_only(self):
        out = run('-m', 'amicus').stdout.decode()
        self.assertIn('friend, ally', out)
        self.assertNotIn('amic-us', out)

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
        self.assertIn('https://github.com/nivaca/py-whitaker-words', out)

    def test_bad_data_directory(self):
        result = run('--datadir', self.tmp.name, 'rem')
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'dictionary.xml', result.stderr)


class InteractiveTests(InTempDir):

    def session(self):
        out = io.StringIO()
        return Session(lexicon(), Settings(pause_in_screen_output=False),
                       write=out.write), out

    def repl(self, *lines):
        session, out = self.session()
        replies = iter(lines)

        def ask(prompt):
            out.write(prompt)
            try:
                return next(replies)
            except StopIteration:
                raise EOFError
        cli.repl(session, ask, out.write)
        return session, out.getvalue()

    def test_lookup_and_quit(self):
        _, out = self.repl('amicus', '', '', 'never read')
        self.assertTrue(out.startswith('py-words'))
        self.assertIn('amicus, amici', out)
        self.assertIn('another empty line quits', out)

    def test_language(self):
        _, out = self.repl('~E', 'friend', '~L', 'amicus')
        self.assertIn('English to Latin', out)
        self.assertIn('amic-us', out)

    def test_file(self):
        with open('words.txt', 'w') as f:
            f.write('rem\n')
        _, out = self.repl('@words.txt', '@missing.txt')
        self.assertIn('res, rei', out)
        self.assertIn('Cannot read missing.txt', out)

    def test_parameters_dialogue(self):
        # trim_output: N; have_output_file: Enter; then a space skips
        session, out = self.repl('#', 'n', '', ' ')
        self.assertFalse(session.settings.trim_output)
        self.assertFalse(os.path.exists('WORD.MOD'))

    def test_parameters_help_and_save(self):
        # trim_output (after ?), then the others but write_output_to_file
        replies = ['#', '?', 'y'] + [''] * (len(MODES) - 2) + ['y']
        session, out = self.repl(*replies)
        self.assertIn('Leave out the least likely results', out)
        with open('WORD.MOD') as f:
            self.assertIn('TRIM_OUTPUT', f.read())

    def test_developer_modes_and_files(self):
        # have_statistics_file: Y, write_statistics_file: Y, then stop
        session, out = self.repl('!', 'y', 'y', ' ', 'amasti')
        self.assertTrue(session.settings.write_statistics_file)
        session.close()
        with open('WORD.STA') as f:
            self.assertIn('SYNCOPE', f.read())

    def test_unknowns_file(self):
        session, out = self.session()
        session.settings.write_unknowns_to_file = True
        session.settings_changed()
        session.process('rem xqzv')
        session.close()
        with open('WORD.UNK') as f:
            self.assertIn('xqzv', f.read())

    def test_output_file(self):
        session, out = self.session()
        session.settings.have_output_file = True
        session.settings.write_output_to_file = True
        session.settings_changed()
        session.process('rem')
        session.close()
        self.assertEqual(out.getvalue(), '')
        with open('WORD.OUT') as f:
            self.assertIn('res, rei', f.read())


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
