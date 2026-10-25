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
from session import Session
from settings import Settings
import model
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
        r = self.analyze('adcenabimus')
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

    def test_medieval_spellings(self):
        # several changes at once: y, h, ae, ph, ch for h
        for word, stem in (('hystorie', 'histori'),
                           ('phylosophia', 'philosophi'),
                           ('dyabolus', 'diabol'), ('michi', 'ego'),
                           ('ecclesie', 'ecclesi'), ('ympnus', 'hymn')):
            r = self.analyze(word)
            self.assertEqual(r.readings[0].origin, Origin.TRICK, word)
            self.assertIn('medieval spelling', r.notes[Origin.TRICK])
            self.assertEqual(r.readings[1].source.stems[0], stem, word)

    def test_medieval_spellings_need_the_setting(self):
        self.az.settings.medieval_spellings = False
        self.az.reset()
        self.assertTrue(self.analyze('hystorie').unknown)

    def test_doubled_letters_in_an_ending_are_not_medieval(self):
        r = self.analyze('amicuss')
        self.assertNotIn('medieval', r.notes.get(Origin.TRICK, ''))

    def test_prodelision(self):
        for word, stem in (('factumst', 'faci'), ('bonast', 'bon'),
                           ('opust', 'opus'), ('omnist', 'omn')):
            r = self.analyze(word)
            self.assertEqual(r.readings[0].origin, Origin.TRICK, word)
            self.assertEqual(r.readings[1].source.fix, 'est', word)
            self.assertIn(stem, [rd.source.stems[0]
                                 for rd in r.readings[2:]], word)

    def test_prodelision_makes_a_compound_tense(self):
        r, used = self.az.analyze_word('amatust', 'non')
        self.assertFalse(used)
        self.assertEqual(r.readings[0].origin, Origin.TRICK)
        compound = [p for rd in r.readings for p in rd.forms
                    if p.origin == Origin.COMPOUND]
        self.assertEqual(compound[0].form.tvm,
                         (Tense.PERF, Voice.PASSIVE, Mood.IND))

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
        self.az.settings.use_affixes = False
        self.az.settings.use_tricks = False
        self.az.reset()
        self.assertTrue(self.analyze('adcenabimus').unknown)

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

    def test_long_marks(self):
        """Long marks, breves, diaereses and ligatures do not split a word
        (amīcus was read as "am" and "cus")."""
        self.assertEqual(split_line('Rōmānī ītē, ămīcŭs poëta.'),
                         ['Romani', 'ite', 'amicus', 'poeta.'])
        self.assertEqual(split_line('cælum pœna Æneas CÆLUM AMĪCUS'),
                         ['caelum', 'poena', 'Aeneas', 'CAELUM', 'AMICUS'])
        results = Analyzer(lexicon(), Settings()).analyze_line('amīcus')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].word, 'amicus')
        self.assertFalse(results[0].unknown)

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


class FindingsTests(unittest.TestCase):
    """How findings (forms, and the marks of how they were found) are
    combined (results.py)."""

    def setUp(self):
        from model import Inflection, Form
        from results import Parse, trick_mark
        self.p = [Parse(s, Inflection(Form(Pos.N)), Origin.GENERAL)
                  for s in ('a', 'b', 'c')]
        self.m = [trick_mark(s) for s in ('x', 'y')]

    def test_chain(self):
        from results import Found, chain, found, marked, shown, parses_of
        a, b, c = self.p
        x, y = self.m
        # forms without marks join the finding before them
        self.assertEqual(chain(found([a]), found([b])), [Found((a, b))])
        self.assertEqual(chain(marked(x, found([a])), found([b])),
                         [Found((a, b), (x,))])
        # marks without forms go with the finding after them
        self.assertEqual(chain([Found((), (x,))], marked(y, found([c]))),
                         [Found((c,), (x, y))])
        # a marked finding stays apart
        both = chain(found([a]), marked(x, found([b, c])))
        self.assertEqual(both, [Found((a,)), Found((b, c), (x,))])
        self.assertEqual(shown(both), [a, x, b, c])
        self.assertEqual(parses_of(both), [a, b, c])
        # empty findings vanish
        self.assertEqual(chain([Found(())], found([a])), [Found((a,))])

    def test_marked(self):
        from results import Found, found, marked
        a, b, _ = self.p
        x, y = self.m
        self.assertEqual(marked(x, marked(y, found([a]))),
                         [Found((a,), (x, y))])
        # only the first finding gets the mark (the others have their own)
        self.assertEqual(marked(x, [Found((a,)), Found((b,), (y,))]),
                         [Found((a,), (x,)), Found((b,), (y,))])

    def test_marks_in_the_result(self):
        """inamicus: the prefix in- is a reading of its own, before the
        adjective it was found on."""
        result, _ = Analyzer(lexicon(), Settings()).analyze_word('inamicus')
        self.assertEqual([r.origin for r in result.readings][:2],
                         [Origin.ADDON, Origin.GENERAL])
        self.assertEqual(result.readings[0].forms[0].stem, 'in')


class GlossTests(unittest.TestCase):
    """The analyses in glossing abbreviations (gloss.xml)."""

    def gloss(self, word, deponent=False, **kw):
        from forms import gloss_form
        from model import Form
        return gloss_form(Form(**kw), lexicon().glosses, deponent)

    def test_glosses_are_loaded(self):
        g = lexicon().glosses
        self.assertEqual(g['case', 'GEN'], 'GEN')
        self.assertEqual(g['mood', 'SUB'], 'SBJV')
        self.assertEqual(g['tense', 'FUTP'], 'FUT.PRF')

    def test_forms(self):
        from model import Gender, Mood, Decl, Comparison
        self.assertEqual(self.gloss('amicorum', pos=Pos.N, decl=Decl(2, 1),
                                    case=Case.GEN, number=Number.P,
                                    gender=Gender.M), 'GEN.PL')
        self.assertEqual(self.gloss('amavisti', pos=Pos.V, person=2,
                                    number=Number.S, tense=Tense.PERF,
                                    voice=Voice.ACTIVE, mood=Mood.IND),
                         '2SG.PRF.ACT.IND')
        self.assertEqual(self.gloss('hortatus', True, pos=Pos.V, person=3,
                                    number=Number.S, tense=Tense.PRES,
                                    voice=Voice.PASSIVE, mood=Mood.SUB),
                         '3SG.PRS.SBJV')       # (deponent: no voice)
        self.assertEqual(self.gloss('laudatus', pos=Pos.VPAR,
                                    tense=Tense.PERF, voice=Voice.PASSIVE,
                                    mood=Mood.PPL, case=Case.NOM,
                                    number=Number.S, gender=Gender.M),
                         'PRF.PASS.PTCP.NOM.SG.M')
        self.assertEqual(self.gloss('amatu', pos=Pos.SUPINE, case=Case.ABL),
                         'SUP.ABL')
        self.assertEqual(self.gloss('altissimis', pos=Pos.ADJ,
                                    case=Case.DAT, number=Number.P,
                                    comparison=Comparison.SUPER),
                         'DAT.PL.SPRL')
        self.assertEqual(self.gloss('amare', pos=Pos.V, tense=Tense.PRES,
                                    voice=Voice.ACTIVE, mood=Mood.INF),
                         'PRS.ACT.INF')

    def test_in_the_output(self):
        from session import Session
        out = Session(lexicon(), Settings()).lookup_latin('amicorum')
        self.assertIn('amīc-ōrum      GEN.PL', out)

    def test_words_without_gloss_xml(self):
        from session import Session
        lex = lexicon()
        saved, lex.glosses = lex.glosses, {}
        try:
            out = Session(lex, Settings()).lookup_latin('amicorum')
        finally:
            lex.glosses = saved
        self.assertIn('amīc-ōrum      genitive plural', out)


class EnglishTests(unittest.TestCase):

    def test_search(self):
        hits = lexicon().reverse().search('friend')
        self.assertEqual(hits[0].entry.stems[0], 'amic')
        self.assertEqual(hits[0].entry.part.pos, Pos.N)

    def test_part_of_speech(self):
        hits = lexicon().reverse().search('friendly', Pos.ADJ)
        self.assertTrue(hits)
        self.assertTrue(all(h.entry.part.pos == Pos.ADJ for h in hits))

    def test_common_words_are_not_indexed_from_phrases(self):
        self.assertFalse(any(h.kind == 0 for h in
                             lexicon().reverse().search('the')))


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


class LongVowelTests(unittest.TestCase):
    """The long vowels of the stems (data/quantities.xml) and of the
    endings (data/inflections.xml)."""

    def test_marked_like(self):
        self.assertEqual(model.unmarked('amīc'), 'amic')
        self.assertEqual(model.marked_like('amic', 'amīc'), 'amīc')
        self.assertEqual(model.marked_like('Iulian', 'jūliān'), 'Iūliān')
        self.assertEqual(model.marked_like('amic', 'rēg'), 'amic')

    def test_the_data(self):
        marked = {e.stems[:2]: lexicon().long_stems[e.uid]
                  for e in lexicon().entries
                  if e.uid in lexicon().long_stems}
        self.assertEqual(marked[('amic', 'amic')][:2], ('amīc', 'amīc'))
        self.assertEqual(marked[('am', 'am')][2:], ('amāv', 'amāt'))
        #  not by position: cor, cordis
        self.assertNotIn(('cor', 'cord'), marked)

    def test_in_the_forms(self):
        settings = Settings()
        session = Session(lexicon(), settings, write=lambda text: None)
        self.assertIn('amīc-us', session.lookup('amicus'))
        settings.show_long_vowels = False
        self.assertIn('amic-us', session.lookup('amicus'))
        self.assertNotIn('amīc', session.lookup('amicus'))

    def test_endings(self):
        """The long vowels of the endings (long in inflections.xml)."""
        longs = {(i.form.pos, i.form.case, i.ending): i.long
                 for es in lexicon().endings.values() for i in es
                 if i.form.decl.which == 1 and i.long}
        self.assertEqual(longs[(Pos.N, model.Case.ABL, 'a')], 'ā')
        self.assertEqual(longs[(Pos.N, model.Case.GEN, 'arum')], 'ārum')
        settings = Settings()
        session = Session(lexicon(), settings, write=lambda text: None)
        self.assertIn('am-ābat', session.lookup('amabat'))
        self.assertIn('am-āns', session.lookup('amans'))
        settings.show_long_vowels = False
        self.assertIn('am-abat', session.lookup('amabat'))


if __name__ == '__main__':
    unittest.main()
