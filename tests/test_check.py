"""Tests for the data checker (words_check.py)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the package, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

import words_check as check, xmldata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

GOOD = ('<entry pos="N" decl="2 1" gender="M" kind="T" area="E" freq="E" '
        'source="W"><stem>blogg</stem><stem>blogg</stem>'
        '<meaning>blog; online journal;</meaning></entry>')


class CheckerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.decls = check.inflection_decls(
            ir for ir, _ in xmldata.read_inflections(
                os.path.join(DATA, 'inflections.xml')))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def problems(self, body, root='dictionary', sources=None):
        path = os.path.join(self.tmp.name, 'test.xml')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<{root}>\n'
                    f'{body}\n</{root}>\n')
        checker = check.Checker(self.decls, sources)
        checker.check_file(path)
        return [item.split(': ', 2)[1:] for item in checker.out]

    def kinds(self, body, root='dictionary'):
        return [kind for kind, _ in self.problems(body, root)]

    def test_good_entry(self):
        self.assertEqual(self.problems(GOOD), [])

    def test_real_data_is_clean(self):
        checker = check.Checker(self.decls, set(
            check.lexicon.source_names(DATA)))
        for name in ('dictionary.xml', 'inflections.xml', 'uniques.xml',
                     'addons.xml', 'sources.xml', 'gloss.xml'):
            checker.check_file(os.path.join(DATA, name))
        self.assertEqual((checker.errors, checker.warnings), (0, 0),
                         checker.out[:5])

    def test_several_sources(self):
        """source="O M": the main source, then the others; each must be a
        known code, none repeated, and X (general) only alone."""
        good = GOOD.replace('source="W"', 'source="O M"')
        self.assertEqual(self.problems(good), [])
        [(entry, _)] = xmldata.read_dictionary(os.path.join(
            self.tmp.name, 'test.xml'))
        self.assertEqual(str(entry.codes), 'XEXEO+M')
        self.assertEqual([s.name for s in entry.codes.sources], ['O', 'M'])
        self.assertIn('source="O M"', xmldata.entry_xml(entry))
        for bad, says in (('O O', 'repeats the source O'),
                          ('X M', 'has X'),
                          ('O OX', 'is not one of')):
            [(kind, message)] = self.problems(
                GOOD.replace('source="W"', f'source="{bad}"'))
            self.assertEqual(kind, 'error')
            self.assertIn(says, message)
        [(kind, message)] = self.problems(good, sources={'O'})
        self.assertEqual(kind, 'warning')
        self.assertIn('source code M is not listed', message)

    def test_sources(self):
        good = '<source code="O" name="Oxford Latin Dictionary"/>'
        self.assertEqual(self.problems(good, 'sources'), [])
        for bad, says in (
                ('<source code="O" name=" "/>', 'has no name'),
                ('<source code="OX" name="two letters"/>', 'is not one of'),
                ('<source name="no code"/>', 'needs a code attribute'),
                (good + '\n' + good, 'is already on line 3')):
            [(kind, message)] = self.problems(bad, 'sources')
            self.assertEqual(kind, 'error')
            self.assertIn(says, message)

    def test_unlisted_source(self):
        [(kind, message)] = self.problems(GOOD, sources={'X', 'O'})
        self.assertEqual(kind, 'warning')
        self.assertEqual(message,
                         'the source code W is not listed in sources.xml')
        self.assertEqual(self.problems(GOOD, sources={'W'}), [])

    def test_glosses(self):
        good = ('<gloss category="case" code="GEN" abbreviation="GEN" '
                'meaning="genitive" leipzig="yes"/>')
        self.assertEqual(self.problems(good, 'glosses'), [])
        for bad, says in (
                (good.replace('"case"', '"colour"'), 'category="colour"'),
                (good.replace('code="GEN"', 'code="GENITIVE"'),
                 'code="GENITIVE" is not one of'),
                (good.replace('abbreviation="GEN"', 'abbreviation="gen"'),
                 'must be capital letters'),
                (good.replace('"yes"', '"maybe"'), 'must be yes or no'),
                (good + '\n' + good, 'is already on line 3')):
            [(kind, message)] = self.problems(bad, 'glosses')
            self.assertEqual(kind, 'error')
            self.assertIn(says, message)

    def test_malformed_xml(self):
        self.assertEqual(self.kinds(GOOD.replace('</entry>', '')), ['error'])

    def test_wrong_root(self):
        self.assertEqual(self.kinds(GOOD, root='words'), ['error'])

    def test_bad_stem(self):
        for stem in ('caf\xe9', 'two words', 'x' * 19, ' blogg'):
            body = GOOD.replace('<stem>blogg</stem>', f'<stem>{stem}</stem>',
                                1)
            self.assertIn('error', self.kinds(body), stem)

    def test_bad_codes(self):
        for old, new in (('pos="N"', 'pos="NOUN"'),
                         ('pos="N"', 'pos="TACKON"'),
                         ('gender="M"', 'gender="Q"'),
                         ('freq="E"', 'freq="Q"'),
                         ('decl="2 1"', 'decl="2"'),
                         ('decl="2 1" ', ''),
                         (' kind="T"', ' kind="T" tense="PRES"')):
            self.assertIn('error', self.kinds(GOOD.replace(old, new)), new)

    def test_two_meanings(self):
        body = GOOD.replace('</entry>', '<meaning>x</meaning></entry>')
        self.assertIn('error', self.kinds(body))

    def test_errors_are_all_reported(self):
        bad = GOOD.replace('gender="M"', 'gender="Q"')
        self.assertEqual(self.kinds('\n'.join([bad, GOOD, bad])),
                         ['error', 'error'])

    def test_no_endings(self):
        body = GOOD.replace('decl="2 1"', 'decl="6 1"')
        self.assertIn('warning', self.kinds(body))

    def test_missing_stem(self):
        body = GOOD.replace('<stem>blogg</stem>', '', 1)
        self.assertIn('warning', self.kinds(body))

    def test_long_meaning(self):
        body = GOOD.replace('blog; online journal;', 'a' * 90)
        self.assertIn('warning', self.kinds(body))

    def test_duplicate(self):
        self.assertEqual(self.kinds(GOOD + '\n' + GOOD), ['warning'])

    def test_other_files(self):
        self.assertEqual(self.kinds(
            '<inflection pos="N" decl="1 1" case="NOM" number="S" '
            'gender="C" key="1" ending="a" age="X" freq="A"/>',
            root='inflections'), [])
        self.assertEqual(self.kinds(
            '<inflection pos="N" decl="1 1" case="NOM" number="S" '
            'gender="C" key="12" ending="a"/>', root='inflections'),
            ['error'])
        self.assertEqual(self.kinds(
            '<prefix fix="ab" root="V" target="V"><meaning>away</meaning>'
            '</prefix><suffix fix="x"/>', root='addons'), ['error'])


if __name__ == '__main__':
    unittest.main()
