"""Tests of the languages of the meanings (languages.py, the language
files, the stable ids they refer to, and the search to Latin)."""

import os
import shutil
import sys
import tempfile
import unittest
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

import languages  # noqa: E402
import words_check  # noqa: E402
import xmldata  # noqa: E402
from editor import Editor  # noqa: E402
from lexicon import Lexicon  # noqa: E402
from model import NumeralSort, Pos  # noqa: E402
from session import Session  # noqa: E402
from settings import Settings  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n'


def write(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(HEAD + text)


class LanguageTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.lexicon = Lexicon.load(DATA)
        entries = cls.lexicon.entries
        cls.friend = next(e for e in entries if e.stems[0] == 'amic' and
                          e.meaning.startswith('friend, ally'))
        cls.heart = next(e for e in entries if e.stems[:2] == ('cor', 'cord')
                         and e.part.pos == Pos.N)
        cls.tackon = next(a for a in cls.lexicon.tackons if a.fix == 'que')
        # a Spanish file, in a data folder of its own
        cls.tmp = tempfile.TemporaryDirectory()
        folder = os.path.join(cls.tmp.name, languages.FOLDER)
        os.mkdir(folder)
        write(os.path.join(folder, 'es.xml'), f'''\
<language code="es" name="Spanish" native="Español">
  <noise>el la</noise>
  <common pos="PREP">de a</common>
  <numeral sort="CARD">{{n}} (cardinal)</numeral>
  <meaning entry="{cls.friend.uid}">amigo, aliado; la persona querida;\
</meaning>
  <meaning entry="{cls.heart.uid}" source="m">El corazón;</meaning>
  <meaning addon="{cls.tackon.uid}">-que = y (enclítico);</meaning>
  <meaning builtin="esse">ser; existir;</meaning>
  <text en="noun">sustantivo</text>
  <text en="2nd   declension">2.ª declinación</text>
  <text en="perfect">perfecto</text>
  <text en="{{1}} {{2}} participle">participio {{1}} {{2}}</text>
  <text en="Word mod {{1}}/{{2}}">Modificador de palabra {{1}}/{{2}}</text>
</language>
''')

        write(os.path.join(cls.tmp.name, 'sources.xml'), '''\
<sources>
  <source code="m" name="De Miguel, Nuevo diccionario latino-español"/>
</sources>
''')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def lex(self):
        """The lexicon, with the Spanish file's data folder."""
        lex = Lexicon.load(DATA)
        lex.datadir = self.tmp.name
        return lex

    def session(self, code='es'):
        settings = Settings()
        settings.language = code
        return Session(self.lex(), settings, write=lambda text: None)

    def test_english(self):
        en = self.lexicon.language()
        self.assertTrue(en.is_reference)
        self.assertEqual(en.name, 'English')
        self.assertEqual(en.meaning(self.friend), self.friend.meaning)
        self.assertIn('the', en.data.noise)
        self.assertEqual(en.numeral(NumeralSort.CARD, 3),
                         "3 - (CARD answers 'how many');")
        self.assertEqual(self.lexicon.language_names()['en'], 'English')

    def test_names(self):
        self.assertEqual(languages.names(self.tmp.name),
                         {'en': 'English', 'es': 'Spanish'})

    def test_translated_and_not(self):
        es = self.lex().language('es')
        self.assertEqual(es.meaning(self.friend),
                         'amigo, aliado; la persona querida;')
        self.assertEqual(es.translated(self.heart), 'El corazón;')
        self.assertEqual(es.meaning(self.heart), 'El corazón; (De Miguel)')
        self.assertIsNone(es.translated(self.lexicon.entries[0]))
        self.assertTrue(es.meaning(self.lexicon.entries[0]).startswith(
            languages.ENGLISH_MARK))
        self.assertEqual(es.numeral(NumeralSort.CARD, 1), '1 (cardinal)')
        self.assertEqual(es.numeral(NumeralSort.ORD, 2),
                         languages.ENGLISH_MARK + "2th - (ORD, 'in series')"
                         "; (a/the) 2th (part) (fract w/pars?);")

    def test_texts(self):
        es = self.lex().language('es')
        self.assertEqual(es.text('noun'), 'sustantivo')
        self.assertEqual(es.text('2nd declension'), '2.ª declinación')
        self.assertEqual(es.text('Word mod pre/prae'),
                         'Modificador de palabra pre/prae')
        self.assertEqual(es.text('Word mod h/'), 'Modificador de palabra h/')
        self.assertEqual(es.text('perfect passive participle'),
                         'participio perfecto passive')     # (its parts too)
        self.assertEqual(es.text('verb'), 'verb')            # (not there)
        self.assertEqual(self.lexicon.language().text('noun'), 'noun')
        session = self.session()
        session.settings.use_glosses = False
        text = session.lookup('amicorum')
        self.assertIn('amicus, amici  sustantivo, 2.ª declinación, '
                      'masculine', text)

    def test_lookup(self):
        text = self.session().lookup('amicorum')
        self.assertIn('amigo, aliado; la persona querida;', text)
        self.assertIn('[en] friendly, dear', text)          # the adjective
        text = self.session().lookup('amicique')
        self.assertIn('-que = y (enclítico);', text)
        self.assertIn('ser; existir;', self.session().lookup('est'))
        self.assertIn('1 (cardinal)', self.session().lookup('unus'))

    def test_reverse(self):
        session = self.session()
        self.assertIn('Spanish to Latin', session.set_language('E'))
        for word in ('amigo', 'Amigo', 'corazon', 'CORAZÓN'):
            text = session.lookup(word)
            self.assertNotIn('(no match)', text, word)
        self.assertIn('amicus, amici', session.lookup('amigo'))
        self.assertIn('(no match)', session.lookup('friend'))
        self.assertIn('(no match)', session.lookup('la'))      # noise

    def test_unknown_language(self):
        session = self.session('xx')
        self.assertEqual(session.language.code, 'en')
        self.assertIn('there is no language xx', session.notice)

    def test_bad_files(self):
        path = os.path.join(self.tmp.name, 'bad.xml')
        for body, message in (
                ('<meaning entry="1">a</meaning><meaning entry="1">b'
                 '</meaning>', 'already on line'),
                ('<meaning entry="x">a</meaning>', 'must be the id'),
                ('<meaning entry="1" unique="1">a</meaning>', 'one of the'),
                ('<meaning builtin="sum">a</meaning>', 'is not one of'),
                ('<meaning entry="1"></meaning>', 'empty'),
                ('<numeral sort="ZZ">a</numeral>', 'is not one of'),
                ('<common pos="NOUN">a</common>', 'parts of speech'),
                ('<text en="a {1}">b</text>', 'must have the {1}'),
                ('<text en="a">b</text><text en=" a ">c</text>',
                 'already on line')):
            write(path, f'<language code="xx" name="X">{body}</language>')
            with self.assertRaises(xmldata.DataError) as e:
                xmldata.read_language(path)
            self.assertIn(message, e.exception.message)
        write(path, '<language code="English" name="X"/>')
        with self.assertRaises(xmldata.DataError):
            xmldata.read_language(path)

    def test_settings(self):
        settings = Settings()
        self.assertEqual(settings.apply_config(
            {'parameters': {'language': 'es'}}), [])
        self.assertEqual(settings.language, 'es')
        self.assertEqual(settings.config_section('parameters')['language'],
                         'es')
        self.assertTrue(settings.apply_config(
            {'parameters': {'language': 'Spanish!'}}))
        self.assertEqual(settings.language, 'es')


class IdTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_ids_are_read_and_written(self):
        path = os.path.join(self.tmp.name, 'dictionary.xml')
        entry = ('<entry {}pos="INTERJ"><stem>eia</stem>'
                 '<meaning>hey!</meaning></entry>')
        write(path, '<dictionary>' + entry.format('id="7" ') +
              entry.format('') + '</dictionary>')
        (first, _), (second, _) = xmldata.read_dictionary(path)
        self.assertEqual((first.id, first.uid), (1, 7))
        self.assertEqual((second.id, second.uid), (2, 2))  # (its position)
        self.assertIn(' id="7" ', xmldata.entry_xml(first))
        self.assertTrue(xmldata.entry_lines(second)[0].startswith(
            '<entry id="2" '))

    def test_the_data_files_have_ids(self):
        for read, name in ((xmldata.read_dictionary, 'dictionary.xml'),
                           (xmldata.read_uniques, 'uniques.xml'),
                           (xmldata.read_addons, 'addons.xml')):
            with open(os.path.join(DATA, name), encoding='utf-8') as f:
                text = f.read()
            items = read(os.path.join(DATA, name))
            self.assertEqual(text.count(' id="'), len(items), name)
            self.assertEqual(len({r.uid for r, _ in items}), len(items))

    def test_editor_keeps_and_gives_ids(self):
        path = os.path.join(self.tmp.name, 'dictionary.xml')
        entry = ('<entry id="{}" pos="INTERJ"><stem>{}</stem>'
                 '<meaning>hey!</meaning></entry>')
        write(path, '<dictionary>' + entry.format(5, 'eia') +
              entry.format(9, 'heia') + '</dictionary>')
        shutil.copy(os.path.join(DATA, 'inflections.xml'), self.tmp.name)
        editor = Editor(self.tmp.name)
        eia, heia = editor.entries
        changed = editor.replace(eia, replace(eia, meaning='ho!', uid=0))
        self.assertEqual(changed.uid, 5)
        new = editor.add(replace(eia, stems=('io', '', '', ''), uid=0))
        self.assertEqual(new.uid, 10)
        editor.save()
        self.assertEqual([e.uid for e, _ in xmldata.read_dictionary(path)],
                         [5, 9, 10])

    def test_check(self):
        datadir = self.tmp.name
        write(os.path.join(datadir, 'dictionary.xml'),
              '<dictionary><entry id="3" pos="INTERJ"><stem>eia</stem>'
              '<meaning>hey!</meaning></entry><entry id="3" pos="INTERJ">'
              '<stem>io</stem><meaning>hey!</meaning></entry></dictionary>')
        folder = os.path.join(datadir, languages.FOLDER)
        os.mkdir(folder)
        write(os.path.join(folder, 'fr.xml'),
              '<language code="es" name="Spanish">\n'
              '<meaning entry="3">¡eh!</meaning>\n'
              '<meaning entry="4">¡oh!</meaning>\n</language>\n')
        checker = words_check.Checker({}, None,
                                      words_check.data_ids(datadir))
        for path in words_check.data_files(datadir):
            checker.check_file(path)
        out = '\n'.join(checker.out)
        self.assertIn('error: the id 3 is already used', out)
        self.assertIn('should be in es.xml, not fr.xml', out)
        self.assertIn('fr.xml:4: warning: there is no entry with the id 4',
                      out)


if __name__ == '__main__':
    unittest.main()
