"""Tests of the fuzzy search: near spellings of unknown Latin words, and
near words in the search to Latin."""

import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

import fuzzy  # noqa: E402
import reverse  # noqa: E402
from analyzer import Analyzer  # noqa: E402
from lexicon import Lexicon  # noqa: E402
from model import Pos  # noqa: E402
from session import Session  # noqa: E402
from settings import Settings  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

LEXICON = None


def lexicon():
    global LEXICON
    if LEXICON is None:
        LEXICON = Lexicon.load(DATA)
    return LEXICON


def session(fuzzy_search=True, **settings):
    s = Settings(fuzzy_search=fuzzy_search, **settings)
    return Session(lexicon(), s, write=lambda text: None)


class EditTests(unittest.TestCase):

    def test_edits(self):
        self.assertEqual(fuzzy.edits('ab', 'ab'),
                         {'a', 'b', 'ba', 'bb', 'aa', 'aab', 'abb', 'bab',
                          'aba'})

    def test_letters(self):
        self.assertNotIn('v', fuzzy.latin_letters('amicus'))
        self.assertIn('v', fuzzy.latin_letters('dominvs'))

    def test_likely(self):
        self.assertEqual(fuzzy.likely('amcius', 'amicus'), 0)   # swapped
        self.assertEqual(fuzzy.likely('magnifcus', 'magnificus'), 1)
        self.assertEqual(fuzzy.likely('freind', 'friend'), 0)   # swapped
        self.assertEqual(fuzzy.likely('amicuss', 'amicus'), 0)  # doubled
        self.assertEqual(fuzzy.likely('puela', 'puella'), 0)    # undoubled
        self.assertEqual(fuzzy.likely('puela', 'puera'), 1)


class LatinTests(unittest.TestCase):

    def test_near_spellings(self):
        az = Analyzer(lexicon(), Settings())
        self.assertEqual(az.near_spellings('amicuss'), ['amicus'])
        self.assertEqual(az.near_spellings('Magnifcus'), ['magnificus'])
        near = az.near_spellings('amcius')
        self.assertEqual(near[0], 'amicus')
        self.assertLessEqual(len(near), 3)
        self.assertEqual(az.near_spellings('xq'), [])   # (too short)
        #  (the hundreds of spellings tried are not kept)
        self.assertLess(len(az._cache), 20)

    def test_on_by_default(self):
        self.assertTrue(Settings().fuzzy_search)

    def test_off(self):
        out = session(False).lookup('amicuss')
        self.assertIn('(unknown)', out)
        self.assertNotIn('near spellings', out)
        self.assertNotIn('amicus, amici', out)

    def test_on(self):
        out = session().lookup('amicuss')
        self.assertIn('(unknown)', out)
        self.assertIn('(near spellings: amicus)', out)
        self.assertIn('amicus, amici', out)

    def test_only_when_nothing_is_found(self):
        out = session().lookup('amicus')
        self.assertNotIn('near spellings', out)
        out = session().lookup('puela')        # (a spelling trick finds it)
        self.assertNotIn('near spellings', out)

    def test_names(self):
        self.assertNotIn('near spellings', session().lookup('Marcuss'))
        out = session(ignore_unknown_names=False).lookup('Amicuss')
        self.assertIn('(near spellings: amicus)', out)

    def test_unknowns_only(self):
        out = session(unknowns_only=True).lookup('amicuss est')
        self.assertIn('(near spellings: amicus)', out)
        self.assertNotIn('amicus, amici', out)


class ReverseTests(unittest.TestCase):

    def lookup(self, line, fuzzy_search=True, **settings):
        s = session(fuzzy_search, **settings)
        s.set_language('E')
        return s.lookup(line)

    def test_near(self):
        index = lexicon().reverse()
        self.assertEqual(index.near('freind'), ['friend'])
        self.assertEqual(index.near('wolfs')[0], 'wolf')
        self.assertEqual(index.near('xyzzy'), [])
        self.assertEqual(index.near('is'), [])          # (too short)
        self.assertTrue(index.near('wolfs', Pos.ADJ))
        self.assertEqual(index.near('wolfs', Pos.PREP), [])

    def test_lookup(self):
        out = self.lookup('freind')
        self.assertIn('(no match)', out)
        self.assertIn('(near words: friend)', out)
        self.assertIn('amicus, amici', out)
        self.assertNotIn('near words', self.lookup('freind', False))
        self.assertNotIn('near words', self.lookup('friend'))

    def test_noise(self):
        self.assertNotIn('near words', self.lookup('the'))

    def test_spelled(self):
        self.assertEqual(reverse.spelled('corazon', 'corazón; mente, alma;'),
                         'corazón')
        self.assertEqual(reverse.spelled('wellwisher',
                                         'Well-wisher, friend;'),
                         'wellwisher')
        self.assertEqual(reverse.spelled('xyz', 'friend'), 'xyz')

    def test_spanish(self):
        out = self.lookup('corazn', language='es')
        #  (spelled as the meanings spell it: De Miguel's "corazon")
        self.assertIn('(palabras cercanas: corazon', out)


class CommandLineTests(unittest.TestCase):

    def run_words(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, 'words.py'),
                               '--datadir', DATA, '--interface', 'en',
                               '--language', 'en', *args],
                              capture_output=True, text=True,
                              check=True).stdout

    def test_flag(self):
        self.assertIn('(near spellings: amicus)',
                      self.run_words('--fuzzy', 'amicuss'))
        self.assertNotIn('near spellings',
                         self.run_words('--no-fuzzy', 'amicuss'))
        self.assertIn('(near words: friend)',
                      self.run_words('--fuzzy', '-e', 'freind'))


if __name__ == '__main__':
    unittest.main()
