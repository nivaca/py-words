"""Tests of the analysis of Latin words and of English lookups."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the package, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

from analyzer import Analyzer, split_line, form_of_sum
from lexicon import Lexicon
from model import (Pos, Case, Number, Tense, Voice,
                                     Mood, Decl)
from results import Origin
from settings import Settings
import tricks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

LEXICON = None


def lexicon():
    global LEXICON
    if LEXICON is None:
        LEXICON = Lexicon.load(DATA)
    return LEXICON


class AnalyzerTests(unittest.TestCase):

    def setUp(self):
        self.az = Analyzer(lexicon(), Settings())

    def analyze(self, word, next_word=''):
        result, _ = self.az.analyze_word(word, next_word)
        return result

    def forms(self, word):
        """(first stem of the entry, pos, case, number) of each form."""
        out = []
        for r in self.analyze(word).readings:
            for p in r.forms:
                stem = p.entry.stems[0] if p.entry else p.stem
                out.append((stem, p.form.pos, p.form.case, p.form.number))
        return out

    def test_noun(self):
        self.assertIn(('amic', Pos.N, Case.NOM, Number.S),
                      self.forms('amicus'))
        self.assertIn(('r', Pos.N, Case.ACC, Number.S), self.forms('rem'))

    def test_verb(self):
        r = self.analyze('tetigisti')
        f = r.readings[0].forms[0].form
        self.assertEqual((f.pos, f.tense, f.voice, f.mood, f.person,
                          f.number),
                         (Pos.V, Tense.PERF, Voice.ACTIVE, Mood.IND, 2,
                          Number.S))

    def test_u_and_v_are_the_same_letter(self):
        self.assertEqual(self.forms('volnus'), self.forms('uolnus'))

    def test_capitals(self):
        self.assertEqual(self.forms('Amicus'), self.forms('amicus'))

    def test_unique(self):
        r = self.analyze('memento')
        self.assertTrue(any(rd.origin == Origin.UNIQUE for rd in r.readings))

    def test_enclitic(self):
        r = self.analyze('virumque')
        self.assertEqual(r.readings[0].source.fix, 'que')
        self.assertTrue(any(p.entry and p.entry.stems[0] == 'vir'
                            for rd in r.readings for p in rd.forms))

    def test_qu_pronoun_and_packon(self):
        r = self.analyze('quicumque')
        self.assertEqual(r.readings[0].source.fix, 'cumque')
        self.assertEqual(r.readings[1].pos, Pos.PRON)

    def test_esse(self):
        forms = self.forms('est')
        self.assertIn(('s', Pos.V, Case.X, Number.S), forms)

    def test_prefix(self):
        r = self.analyze('adcubitabimur')
        self.assertEqual(r.readings[0].source.fix, 'ad')

    def test_compound_tense(self):
        r, used = self.az.analyze_word('laudatus', 'est')
        self.assertTrue(used)
        compound = [p for rd in r.readings for p in rd.forms
                    if p.origin == Origin.COMPOUND]
        self.assertEqual(compound[0].form.tvm,
                         (Tense.PERF, Voice.PASSIVE, Mood.IND))
        self.assertIn(Origin.COMPOUND, r.notes)

    def test_adverb_from_adjective(self):
        r = self.analyze('pulchre')
        self.assertTrue(any(p.form.pos == Pos.ADV for rd in r.readings
                            for p in rd.forms))

    def test_syncope(self):
        r = self.analyze('amasti')
        self.assertEqual(r.readings[0].origin, Origin.SYNCOPE)
        self.assertEqual(r.readings[1].forms[0].form.tense, Tense.PERF)

    def test_trick(self):
        r = self.analyze('philosofia')
        self.assertEqual(r.readings[0].origin, Origin.TRICK)
        self.assertIn(Origin.TRICK, r.notes)

    def test_roman_numeral(self):
        r = self.analyze('MCMXCIV')
        self.assertEqual(r.readings[0].origin, Origin.ROMAN)
        self.assertIn('1994', r.notes[Origin.ROMAN])

    def test_unknown(self):
        self.assertTrue(self.analyze('xqzv').unknown)

    def test_trimming(self):
        self.assertTrue(self.analyze('acu').trimmed)
        self.az.settings.trim_output = False
        self.az.reset()
        self.assertFalse(self.analyze('acu').trimmed)

    def test_settings_switch_off_fixes(self):
        self.az.settings.do_fixes = False
        self.az.settings.do_tricks = False
        self.az.reset()
        self.assertTrue(self.analyze('adcubitabimur').unknown)

    def test_line(self):
        results = self.az.analyze_line('Gallia est omnis divisa -- comment')
        self.assertEqual([r.word for r in results],
                         ['Gallia', 'est', 'omnis', 'divisa'])

    def test_compound_uses_next_word(self):
        results = self.az.analyze_line('laudatus est')
        self.assertEqual([r.word for r in results], ['laudatus'])


class HelperTests(unittest.TestCase):

    def test_split_line(self):
        self.assertEqual(split_line('Arma virumque cano, Troiae qui.'),
                         ['Arma', 'virumque', 'cano', 'Troiae', 'qui.'])
        self.assertEqual(split_line('rem -- acu'), ['rem'])

    def test_form_of_sum(self):
        f = form_of_sum('erant')
        self.assertEqual((f.tense, f.mood, f.person, f.number),
                         (Tense.IMPF, Mood.IND, 3, Number.P))
        self.assertIsNone(form_of_sum('amat'))

    def test_roman_numbers(self):
        for text, value in (('IV', 4), ('XLII', 42), ('MCMXCIV', 1994),
                            ('mmxxvi', 2026), ('IIII', 4)):
            self.assertEqual(tricks.roman_number(text), value, text)
        for bad in ('IIX', 'VV', 'CCD', 'IC', ''):
            self.assertEqual(tricks.roman_number(bad), 0, bad)
        self.assertEqual(tricks.bad_roman_number('IIX'), 8)

    def test_decl_fits(self):
        self.assertTrue(Decl(2, 1).fits(Decl(2, 1)))
        self.assertTrue(Decl(2, 1).fits(Decl(2, 0)))
        self.assertTrue(Decl(2, 1).fits(Decl(0, 0)))
        self.assertFalse(Decl(9, 8).fits(Decl(0, 0)))
        self.assertFalse(Decl(2, 1).fits(Decl(3, 0)))


class EnglishTests(unittest.TestCase):

    def test_search(self):
        hits = lexicon().english.search('friend')
        self.assertEqual(hits[0].entry.stems[0], 'amic')
        self.assertEqual(hits[0].entry.part.pos, Pos.N)

    def test_part_of_speech(self):
        hits = lexicon().english.search('friendly', Pos.ADJ)
        self.assertTrue(hits)
        self.assertTrue(all(h.entry.part.pos == Pos.ADJ for h in hits))

    def test_common_words_are_not_indexed_from_phrases(self):
        self.assertFalse(any(h.kind == 0 for h in
                             lexicon().english.search('the')))


class LexiconTests(unittest.TestCase):

    def test_esse_is_built_in(self):
        esse = lexicon().entries[-1]
        self.assertEqual(esse.stems, ('s', '', 'fu', 'fut'))
        self.assertIn(esse, [r.entry for r in lexicon().lookup('')])

    def test_lookup_folds_u_v_i_j(self):
        self.assertEqual(lexicon().lookup('iuuen'), lexicon().lookup('juven'))

    def test_neighbours(self):
        near = lexicon().neighbours('amicx')
        self.assertTrue(near)
        self.assertTrue(all(e.stems[0].lower().startswith('ami')
                            for e in near))

    def test_comparison_stems(self):
        refs = [r for r in lexicon().lookup('meli')
                if r.part.pos == Pos.ADJ]
        self.assertEqual([r.key for r in refs], [3])     # bonus, melior


if __name__ == '__main__':
    unittest.main()
