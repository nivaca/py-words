"""Tests of the second source, Logeion (logeion.py): the lemmas asked for,
the pages fetched and shown, the source kept, and the command line, the
window and the terminal interface with it.  Logeion itself is not asked:
a client of its pages here stands for it."""

import contextlib
import io
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: E402  (before anything that reads settings)

import logeion  # noqa: E402
import logeion_api as api  # noqa: E402
from lexicon import Lexicon  # noqa: E402
from logeion_render import Style  # noqa: E402
from session import Session  # noqa: E402
from settings import Settings  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')


def page(word: str, entry: str, short: str = '', gaffiot: str = '') -> dict:
    """A page as api.fetch_page gives it, with a Lewis and Short ENTRY (and
    one of Gaffiot)."""
    dicos = [{'dname': 'LewisShort', 'es': [entry]}]
    if gaffiot:
        dicos.append({'dname': 'Gaffiot 2016', 'es': [gaffiot]})
    return {'query': word, 'word': word, 'info': {},
            'detail': {'dicos': dicos,
                       'shortdef': [short] if short else []},
            'parses': [{'lemma': word}], 'lemmas': [word]}


PAGES = {
    'arma': page('arma', '<b>arma</b>, ōrum, n., <i>arms</i>; see '
                 '<a href="https://logeion.uchicago.edu/armo">armo</a> and '
                 '<a href="https://example.org/arms">more</a>.',
                 'arma, weapons', 'arma, ōrum, n., ustensiles, armes'),
    'armo': page('armo', 'armo, āvi, ātum, 1, <i>to arm</i>.',
                 'armo, to arm'),
}


class Client:
    """Logeion's pages, from PAGES (others are not found; armum's nearest
    headword is armus).  With DOWN, Logeion cannot be reached."""

    def __init__(self, pages=None, down=False):
        self.pages = PAGES if pages is None else pages
        self.down = down
        self.asked: list[str] = []

    def page(self, word):
        self.asked.append(word)
        if self.down:
            raise urllib.error.URLError('no network')
        if word in self.pages:
            return self.pages[word]
        raise api.NotFound(word, 'armus' if word == 'armum' else None)


def session() -> Session:
    if not hasattr(session, 'made'):
        session.made = Session(Lexicon.load(DATA), Settings())
    return session.made


class LemmaTests(unittest.TestCase):
    def lemmas(self, word):
        [found] = logeion.queries(session(), word)
        self.assertEqual(found.word, word)
        return found.lemmas

    def test_lemmas_of_the_analysis(self):
        self.assertEqual(self.lemmas('arma'), ['armum', 'armo'])
        self.assertEqual(self.lemmas('dixit'), ['dico'])
        self.assertEqual(self.lemmas('rosarum'), ['rodo', 'rosa'])
        self.assertEqual(self.lemmas('Romae'), ['Roma'])

    def test_i_for_j(self):
        self.assertIn('iuvo', self.lemmas('juvat'))

    def test_pronouns(self):
        self.assertEqual(self.lemmas('quae'), ['qui', 'quis'])
        self.assertEqual(self.lemmas('mihi'), ['ego'])
        self.assertEqual(self.lemmas('nobis'), ['nos'])
        self.assertEqual(self.lemmas('sibi'), ['sui'])
        self.assertEqual(self.lemmas('illa'), ['ille'])

    def test_a_word_not_found_is_asked_as_it_is(self):
        self.assertEqual(self.lemmas('xyzzyq'), ['xyzzyq'])

    def test_one_query_per_word(self):
        found = logeion.queries(session(), 'arma virumque cano')
        self.assertEqual([w.word for w in found],
                         ['arma', 'virumque', 'cano'])


class FetchTests(unittest.TestCase):
    def test_the_form_its_lemmas_and_what_is_missing(self):
        client = Client()
        [word] = logeion.Logeion(client).look_up(session(), 'arma')
        #  arma is a headword of Logeion's: its page first, then those of
        #  the lemmas (armum has none)
        self.assertEqual(client.asked, ['arma', 'armum', 'armo'])
        self.assertEqual([p.lemma for p in word.pages],
                         ['arma', 'armum', 'armo'])
        self.assertEqual(word.pages[1].entry, None)
        self.assertEqual(word.pages[1].problem, 'Logeion has no entry for '
                         'armum (the nearest: armus).')
        #  (Logeion's own analysis of the lemma, which the page has, is
        #  not shown)
        self.assertEqual([s.code for s in word.pages[2].entry.sections],
                         ['short', 'ls'])

    def test_a_form_that_is_not_a_headword_is_left_out(self):
        pages = {'armo': PAGES['armo'],
                 'armat': {**PAGES['armo'], 'query': 'armat'}}
        [word] = logeion.Logeion(Client(pages)).look_up(session(), 'armat')
        self.assertEqual([p.lemma for p in word.pages], ['armo'])

    def test_a_page_once(self):
        pages = {'a': PAGES['armo'], 'b': PAGES['armo']}
        words = [logeion.Word('a', ['a', 'b'])]
        logeion.Logeion(Client(pages)).fetch(words)
        self.assertEqual([p.lemma for p in words[0].pages], ['a'])

    def test_no_network(self):
        client = Client(down=True)
        words = logeion.Logeion(client).look_up(session(), 'arma amo')
        self.assertEqual(client.asked, ['arma'])    # (and no more)
        self.assertEqual(len(words[0].pages), 1)
        self.assertEqual(words[0].pages[0].problem,
                         'Logeion could not be reached: no network')
        self.assertEqual(words[1].pages, [])


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.words = logeion.Logeion(Client()).look_up(session(), 'arma')

    def test_text(self):
        lines = logeion.text(self.words).split('\n')
        self.assertEqual(lines[0], 'arma  →  armum, armo')
        text = '\n'.join(lines)
        self.assertIn('Lewis & Short', text)
        self.assertIn('arma, weapons', text)
        self.assertIn('Logeion has no entry for armum', text)
        self.assertNotIn('\033', text)

    def test_kinds_and_styles(self):
        lines = logeion.render(self.words, Style(True), 60)
        self.assertEqual(lines[0][0], logeion.HEAD)
        self.assertTrue(all(kind == logeion.PAGE for kind, _ in lines[1:]))
        text = '\n'.join(line for _, line in lines)
        self.assertIn('\033]8;;https://logeion.uchicago.edu/armo', text)
        self.assertIn('\033[1;36mLewis & Short', text)

    def test_width(self):
        long = page('arma', ' '.join(['arms'] * 100))
        words = logeion.Logeion(Client({'arma': long})).look_up(session(),
                                                                'arma')
        for width in (40, 70):
            text = logeion.text(words, width)
            self.assertLessEqual(max(map(len, text.split('\n'))), width)


class DictionaryTests(unittest.TestCase):
    def setUp(self):
        self.words = logeion.Logeion(Client()).look_up(session(), 'arma')

    def test_codes_and_names(self):
        code = logeion.dictionary_code
        self.assertEqual(code('ls'), 'ls')
        self.assertEqual(code('Lewis & Short'), 'ls')
        self.assertEqual(code('lewis'), 'lewis')       # (not ls)
        self.assertEqual(code('Gaffiot 2016'), 'gaffiot')
        self.assertEqual(code('du cange'), 'ducange')
        self.assertEqual(code('geo'), 'georges')
        self.assertEqual(code('all'), logeion.ALL)
        self.assertIsNone(code('lsj'))
        self.assertEqual(list(logeion.DICTIONARIES)[:3],
                         [logeion.ALL, 'ls', 'lewis'])

    def test_one_dictionary(self):
        text = logeion.text(self.words, dictionary='gaffiot')
        self.assertIn('Gaffiot 2016', text)
        self.assertIn('ustensiles', text)
        self.assertNotIn('\nLewis & Short\n', text)    # (its section)
        self.assertIn('arma, weapons', text)    # (the short definition)
        self.assertIn('Gaffiot 2016 has no entry for armo (it is in: Lewis '
                      '& Short).', text)
        everything = logeion.text(self.words)
        self.assertIn('Lewis & Short', everything)
        self.assertIn('Gaffiot 2016', everything)

    def test_a_dictionary_without_the_lemma(self):
        text = logeion.text(self.words, dictionary='georges')
        self.assertIn('Georges has no entry for arma (it is in: Lewis & '
                      'Short, Gaffiot 2016).', text)
        self.assertIn('Georges has no entry for armo (it is in: Lewis & '
                      'Short).', text)
        self.assertNotIn('ustensiles', text)

    def test_kept(self):
        import config
        self.addCleanup(config.update, logeion.SECTION, {})
        self.assertEqual(logeion.saved_dictionary(), logeion.ALL)
        logeion.save_source(logeion.LOGEION)
        self.assertEqual(logeion.save_dictionary('gaffiot'), '')
        self.assertEqual(logeion.saved_dictionary(), 'gaffiot')
        self.assertEqual(logeion.saved_source(), logeion.LOGEION)
        config.update(logeion.SECTION, {'dictionary': 'lsj'})
        self.assertEqual(logeion.saved_dictionary(), logeion.ALL)


class SourceTests(unittest.TestCase):
    def setUp(self):
        import config
        self.addCleanup(config.update, logeion.SECTION, {})

    def test_kept(self):
        import config
        self.assertEqual(logeion.saved_source(), logeion.LOCAL)
        self.assertEqual(logeion.save_source(logeion.LOGEION), '')
        self.assertEqual(logeion.saved_source(), logeion.LOGEION)
        config.update(logeion.SECTION, {'source': 'elsewhere'})
        self.assertEqual(logeion.saved_source(), logeion.LOCAL)

    def test_the_configuration_file_says_what_it_is(self):
        import config
        logeion.save_source(logeion.LOGEION)
        with open(config.config_path(), encoding='utf-8') as f:
            text = f.read()
        self.assertIn('[logeion]\n# Where the window', text)
        self.assertIn('source = "logeion"', text)


class CommandLineTests(unittest.TestCase):
    def run_words(self, *args):
        import words
        out = io.StringIO()
        with mock.patch.object(api, 'Client', lambda: Client()), \
                contextlib.redirect_stdout(out):
            words.main(['--datadir', DATA, *args])
        return out.getvalue()

    def test_logeion(self):
        out = self.run_words('--logeion', 'arma')
        self.assertTrue(out.startswith('arma  →  armum, armo\n'), out)
        self.assertIn('Lewis & Short', out)
        self.assertNotIn('\033', out)           # (not a terminal)

    def test_local_still(self):
        out = self.run_words('arma')
        self.assertIn('armum, armi  noun', out)
        self.assertNotIn('Lewis & Short', out)

    def test_dictionary(self):
        out = self.run_words('--dictionary', 'Gaffiot', 'arma')
        self.assertTrue(out.startswith('arma  →  armum, armo\n'), out)
        self.assertIn('\nGaffiot 2016\n', out)
        self.assertNotIn('\nLewis & Short\n', out)

    def test_dictionaries(self):
        out = self.run_words('--dictionaries')
        self.assertIn('ls        Lewis & Short', out)
        self.assertIn('ducange   Du Cange', out)

    def test_no_such_dictionary(self):
        with self.assertRaises(SystemExit) as e:
            self.run_words('--dictionary', 'lsj', 'arma')
        self.assertIn('there is no dictionary lsj', str(e.exception.code))

    def test_to_latin_is_local(self):
        out = self.run_words('--logeion', '-e', 'friend')
        self.assertIn('amicus', out)


@unittest.skipUnless(isolate.display(), 'needs a display')
class WindowTests(unittest.TestCase):

    def setUp(self):
        import gc
        import tkinter as tk
        import config
        import words_gui
        self.root = tk.Tk()
        self.addCleanup(config.update, logeion.SECTION, {})
        self.app = words_gui.App(self.root, DATA)
        self.app.logeion = logeion.Logeion(Client())

        def close():
            self.root.destroy()
            del self.root, self.app
            gc.collect()        # (Tk must be freed here)
        self.addCleanup(close)
        self.wait(lambda: self.app.session is not None)

    def wait(self, ready, times=800):
        for _ in range(times):
            if ready():
                return
            self.root.update()
            self.root.after(25)
        self.fail('timed out')

    def choose(self, source):
        self.app.source.set(source)
        self.app.choose_source()

    def test_selector(self):
        app = self.app
        self.assertEqual(app.source.get(), logeion.LOCAL)
        self.assertEqual(str(app.to_latin['state']), 'normal')
        app.reverse.set(True)
        self.choose(logeion.LOGEION)
        self.assertFalse(app.reverse.get())
        for widget in (app.to_latin, app.fuzzy_box, app.language):
            self.assertEqual(str(widget['state']), 'disabled')
        #  (the editor edits this dictionary, not Logeion's)
        edit = app.dictionary_menu
        self.assertEqual(edit.entrycget(0, 'label'), 'Edit dictionary…')
        self.assertEqual(str(edit.entrycget(0, 'state')), 'disabled')
        with mock.patch('words_edit_gui.EditorWindow') as editor:
            app.edit_dictionary()
        editor.assert_not_called()
        self.assertEqual(logeion.saved_source(), logeion.LOGEION)
        self.choose(logeion.LOCAL)
        self.assertEqual(str(app.to_latin['state']), 'normal')
        self.assertEqual(str(app.language['state']), 'readonly')
        self.assertEqual(str(edit.entrycget(0, 'state')), 'normal')

    def test_results(self):
        app, t = self.app, self.app.text
        self.choose(logeion.LOGEION)
        app.look_up('arma')
        self.wait(lambda: app.shown_words is not None and
                  str(app.button['state']) == 'normal')
        self.assertEqual(t.get('1.0', '1.end'), 'arma  →  armum, armo')
        self.assertIn('word', t.tag_names('1.0'))
        text = t.get('1.0', 'end')
        self.assertIn('Lewis & Short', text)
        self.assertIn('Logeion has no entry for armum', text)
        self.assertIn('• arma, weapons', text)
        self.assertNotIn('\033', text)
        #  a link to a word of Logeion looks it up; another, the browser
        self.assertIn(('armo', False), app.results.links.values())
        self.assertEqual(list(app.results.urls.values()),
                         ['https://example.org/arms'])
        self.assertTrue(t.tag_ranges('lg_section'))
        self.assertTrue(t.tag_ranges('lg_italic'))
        #  a double click on a word looks it up, in Latin
        index = t.search('weapons', '1.0')
        self.assertEqual(app.results._word_at(f'{index}+2c'),
                         ('weapons', False))
        #  back to this dictionary
        self.choose(logeion.LOCAL)
        self.wait(lambda: app.shown is not None and
                  str(app.button['state']) == 'normal')
        self.assertIn('armum, armi  noun', t.get('1.0', 'end'))
        self.assertIsNone(app.results.logeion_words)

    def test_dictionary(self):
        app, t = self.app, self.app.text
        names = list(app.dictionaries['values'])
        self.assertEqual(names[:2], ['All dictionaries', 'Lewis & Short'])
        self.assertEqual(str(app.dictionaries['state']), 'disabled')
        self.choose(logeion.LOGEION)
        self.assertEqual(str(app.dictionaries['state']), 'readonly')
        app.look_up('arma')
        self.wait(lambda: app.shown_words is not None and
                  str(app.button['state']) == 'normal')
        self.assertIn('Lewis & Short', t.get('1.0', 'end'))
        asked = list(app.logeion.client.asked)
        app.dictionaries.set('Gaffiot 2016')
        app.choose_dictionary()
        text = t.get('1.0', 'end')
        self.assertIn('ustensiles', text)
        self.assertNotIn('\nLewis & Short\n', text)
        self.assertIn('Gaffiot 2016 has no entry for armo', text)
        self.assertEqual(app.logeion.client.asked, asked)   # (not again)
        self.assertEqual(logeion.saved_dictionary(), 'gaffiot')
        self.choose(logeion.LOCAL)
        self.assertEqual(str(app.dictionaries['state']), 'disabled')

    def test_wrapped_to_the_width(self):
        app = self.app
        long = page('arma', ' '.join(['arms'] * 100))
        app.logeion = logeion.Logeion(Client({'arma': long}))
        self.choose(logeion.LOGEION)
        app.look_up('arma')
        self.wait(lambda: app.shown_words is not None and
                  str(app.button['state']) == 'normal')
        width = app.results.logeion_width
        lines = app.text.get('1.0', 'end').split('\n')
        self.assertLessEqual(max(map(len, lines)), width)
        self.assertGreater(width, 30)


if __name__ == '__main__':
    unittest.main()
