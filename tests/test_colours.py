"""Tests of the colours of the results in a terminal (colours.py), and of
where they are used: the command line's results in a terminal, and
Logeion's analysis lines."""

import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

import colours  # noqa: E402
from lexicon import Lexicon  # noqa: E402
from session import Session  # noqa: E402
from settings import Settings  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
ANSI = '\033['


class Terminal(io.StringIO):
    def isatty(self):
        return True


class LineTests(unittest.TestCase):
    def test_word(self):
        self.assertEqual(colours.line('amicus'), '\033[1mamicus\033[0m')

    def test_entry(self):
        line = colours.line('  amicus, amici  noun, 2nd declension  '
                            '[XXXBO]')
        self.assertTrue(line.startswith('\033[1m  \033[0m'
                                        '\033[1;31mamicus\033[0m'), line)
        self.assertIn('\033[2m[XXXBO]\033[0m', line)
        self.assertIn('\033[1m, amici  noun, 2nd declension  \033[0m',
                      line)

    def test_form(self):
        self.assertEqual(colours.line('    amīc-us        NOM.SG'),
                         '    amīc-us        \033[34mNOM.SG\033[0m')

    def test_meaning_note_and_blank(self):
        self.assertEqual(colours.line('    a friend'), '    a friend')
        self.assertEqual(colours.line('  (unknown)'),
                         '\033[2m  (unknown)\033[0m')
        self.assertEqual(colours.line(''), '')

    def test_the_text_is_the_same(self):
        text = '\n'.join(['amicus', '  amicus, amici  noun  [XXXBO]',
                          '    a friend', '    amīc-us        NOM.SG'])
        import re
        plain = re.sub(r'\033\[[0-9;]*m', '', colours.results(text))
        self.assertEqual(plain, text)


class EnabledTests(unittest.TestCase):
    def test_only_a_terminal(self):
        with mock.patch.dict(os.environ, {'TERM': 'xterm'}, clear=False):
            os.environ.pop('NO_COLOR', None)
            self.assertTrue(colours.enabled(Terminal()))
            self.assertFalse(colours.enabled(io.StringIO()))

    def test_no_color_and_dumb(self):
        with mock.patch.dict(os.environ, {'NO_COLOR': '1'}):
            self.assertFalse(colours.enabled(Terminal()))
            self.assertFalse(colours.enabled())
        with mock.patch.dict(os.environ, {'TERM': 'dumb'}):
            os.environ.pop('NO_COLOR', None)
            self.assertFalse(colours.enabled(Terminal()))


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lexicon = Lexicon.load(DATA)

    def test_plain_unless_asked(self):
        session = Session(self.lexicon, Settings())
        self.assertNotIn(ANSI, session.lookup('amicus'))
        session.colour = True
        coloured = session.lookup('amicus')
        self.assertIn('\033[1;31mamicus\033[0m', coloured)
        session.reverse = True
        self.assertIn(ANSI, session.lookup('friend'))

    def test_not_with_the_pearse_codes(self):
        session = Session(self.lexicon, Settings(pearse_codes=True))
        session.colour = True
        self.assertNotIn(ANSI, session.lookup('amicus'))

    def test_logeion_analysis(self):
        import logeion
        [word] = logeion.queries(Session(self.lexicon, Settings()), 'arma')
        styled = logeion.text([word], styled=True)
        self.assertIn('\033[1;31marmum\033[0m', styled)
        self.assertIn('\033[34mNOM.PL\033[0m', styled)
        plain = logeion.render([word], logeion.Style(True), 78)
        self.assertNotIn(ANSI, ''.join(line for kind, line in plain
                                       if kind == logeion.ANALYSIS))

    def test_command_line(self):
        import contextlib
        import words
        out = Terminal()
        with mock.patch.object(sys, 'stdout', out), \
                mock.patch.dict(os.environ, {'TERM': 'xterm',
                                             'PAGER': 'cat'}), \
                contextlib.redirect_stderr(io.StringIO()):
            os.environ.pop('NO_COLOR', None)
            words.main(['--datadir', DATA, '--local', 'amicus'])
        self.assertIn('\033[1;31mamicus\033[0m', out.getvalue())


if __name__ == '__main__':
    unittest.main()
