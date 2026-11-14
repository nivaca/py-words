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


def forget_choices(test: unittest.TestCase):
    """The source, dictionary and direction kept are forgotten after TEST
    (the tests share one configuration file)."""
    import config
    from session import SEARCH
    for section in (logeion.SECTION, SEARCH):
        test.addCleanup(config.update, section, {})


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


class AnalysisTests(unittest.TestCase):
    """The analysis shown before Logeion's entries."""

    def test_forms_without_meanings(self):
        [word] = logeion.queries(session(), 'dixi')
        text = '\n'.join(word.analysis)
        self.assertIn('  dico, dicere, dixi, dictus  verb, 3rd conjugation',
                      text)
        self.assertRegex(text, r'\n    dix-ī +1SG\.PRF\.ACT\.IND')
        self.assertNotIn('to say', text)        # (Logeion's, not ours)
        #  (the entries of dico that only the meanings tell apart: once)
        self.assertEqual(len(word.analysis), len(set(word.analysis)))
        self.assertNotIn('dixi', word.analysis[0].split()[:1])

    def test_alike_entries_together(self):
        #  (quae: eight entries of qui and quis, four kinds of pronoun;
        #  some of them without forms of their own in this program's
        #  results, which leaves them to the next one that has the same)
        [word] = logeion.queries(session(), 'quae')
        heads = [line for line in word.analysis if line.startswith('  p')]
        self.assertEqual(heads, ['  pronoun, relative',
                                 '  pronoun, interrogative',
                                 '  pronoun, indefinite',
                                 '  pronoun, adjectival'])
        indefinite = word.analysis[word.analysis.index(heads[2]) + 1:
                                   word.analysis.index(heads[3])]
        self.assertEqual(len(indefinite), len(set(indefinite)))
        self.assertTrue(any('ACC.PL.N' in f for f in indefinite))

    def test_no_codes_or_flags(self):
        #  (dico: four entries, one of them medieval, one line)
        settings = Settings(show_codes=True, show_entry_source=True)
        [word] = logeion.queries(Session(Lexicon.load(DATA), settings),
                                 'dixi')
        self.assertEqual(word.analysis[0],
                         '  dico, dicere, dixi, dictus  verb, 3rd '
                         'conjugation')
        self.assertEqual(len(word.analysis), 2)

    def test_unknown(self):
        [word] = logeion.queries(session(), 'xyzzyq')
        self.assertEqual(word.analysis, ['  (unknown)'])

    def test_shown_first(self):
        words = logeion.Logeion(Client()).look_up(session(), 'arma')
        lines = logeion.text(words).split('\n')
        self.assertEqual(lines[:3], [
            'arma  →  armum, armo',
            '  armum, armi  noun, 2nd declension, neuter',
            '    arm-a          NOM.PL'])
        self.assertLess(lines.index('    arm-ā          2SG.PRS.ACT.IMP'),
                        lines.index('Lewis & Short'))

    def test_wrapped(self):
        words = logeion.queries(session(), 'arma')
        for _, line in logeion.render(words, Style(False), 30):
            self.assertLessEqual(len(line), 30, line)
        long = [line for kind, line in logeion.render(
            words, Style(False), 30, wrap_analysis=False)
            if kind == logeion.ANALYSIS]
        self.assertGreater(max(map(len, long)), 30)


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

    def test_a_form_without_lewis_and_short_is_left_out(self):
        #  (dixi: Gaffiot has it, only to send to dico)
        pages = {'dixi': {**page('dixi', ''), 'detail': {'dicos': [{
                     'dname': 'Gaffiot 2016',
                     'es': ['dīxī, parf. de dico.']}]}},
                 'dico': page('dico', 'dīco, dixi, dictum, 3, to say.')}
        client = Client(pages)
        [word] = logeion.Logeion(client).look_up(session(), 'dixi')
        self.assertEqual(client.asked, ['dixi', 'dico'])
        self.assertEqual([p.lemma for p in word.pages], ['dico'])

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
        kinds = [kind for kind, _ in lines]
        self.assertEqual(kinds[0], logeion.HEAD)
        #  (the analysis, then the pages)
        n = kinds.index(logeion.PAGE)
        self.assertGreater(n, 1)
        self.assertEqual(set(kinds[1:n]), {logeion.ANALYSIS})
        self.assertEqual(set(kinds[n:]), {logeion.PAGE})
        self.assertNotIn('\033', ''.join(line for _, line in lines[1:n]))
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
        forget_choices(self)

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
        self.assertIn('[logeion]\n# Where the programs look words up', text)
        self.assertIn('source = "logeion"', text)
        from session import save_to_latin
        save_to_latin(True)
        with open(config.config_path(), encoding='utf-8') as f:
            text = f.read()
        self.assertIn('[search]\n# The direction of the last search', text)
        self.assertIn('to_latin = true', text)


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        forget_choices(self)

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


class InteractiveTests(unittest.TestCase):
    """~G and ~D in interactive mode and in files (words.py)."""

    def setUp(self):
        forget_choices(self)
        self.session = Session(Lexicon.load(DATA), Settings())
        self.session.settings.pause_in_screen_output = False
        patch = mock.patch.object(api, 'Client', lambda: Client())
        patch.start()
        self.addCleanup(patch.stop)

    def run_lines(self, *lines):
        import words
        answers = iter(lines + ('', ''))
        out = []
        words.repl(self.session, ask=lambda prompt: (
            out.append(prompt), next(answers))[1], write=out.append)
        return ''.join(out)

    def test_switch(self):
        out = self.run_lines('arma', '~G', 'arma', '~G', 'arma')
        first, rest = out.split('Searching in Logeion (All dictionaries)', 1)
        self.assertIn('~G: Local → Logeion\n', first)
        self.assertIn('armum, armi  noun', first)        # (this dictionary)
        on, off = rest.split('Searching in this dictionary.', 1)
        self.assertIn('arma  →  armum, armo', on)
        self.assertIn('Lewis & Short', on)
        self.assertIn('armum, armi  noun', off)
        self.assertNotIn('Lewis & Short', off)

    def test_dictionary(self):
        out = self.run_lines('~D gaffiot', 'arma', '~D', '2', 'arma',
                             '~D lsj', '~D', '')
        self.assertIn('Searching in Logeion: Gaffiot 2016.', out)
        first, rest = out.split('Searching in Logeion: Lewis & Short.', 1)
        self.assertIn('\nGaffiot 2016\n', first)
        self.assertNotIn('\nLewis & Short\n', first)
        self.assertIn('   2  ls        Lewis & Short', first)
        self.assertIn('\nLewis & Short\n', rest)
        self.assertNotIn('\nGaffiot 2016\n', rest)
        self.assertIn('There is no dictionary lsj in Logeion', rest)
        #  (Enter keeps the one there is: marked in the list)
        self.assertIn('*  2  ls', rest)
        self.assertIn('Logeion: Lewis & Short.', rest.rsplit('*  2', 1)[1])

    def test_starting_with_logeion(self):
        import words
        self.session.logeion = words.LogeionLookup(self.session,
                                                   io.StringIO(), 'ls')
        self.session.other_source = self.session.logeion
        out = self.run_lines()
        self.assertIn('~G: Logeion → Local   ~D: the dictionary (Lewis & '
                      'Short)', out)

    def test_file(self):
        import words
        out = []
        self.session.write = out.append
        words.feed(self.session, ['arma', '~G', 'arma', '~D gaffiot',
                                  'arma', '~G', 'arma'], out.append)
        text = ''.join(out)
        parts = text.split('Searching in')
        #  (local, Logeion, its Gaffiot, local again)
        self.assertEqual(len(parts), 4)
        self.assertIn('armum, armi  noun', parts[0])
        self.assertIn('\nLewis & Short\n', parts[1])
        self.assertIn('\nGaffiot 2016\n', parts[2])
        self.assertNotIn('\nLewis & Short\n', parts[2])
        self.assertTrue(parts[3].startswith(' this dictionary.'))
        self.assertIn('armum, armi  noun', parts[3])



class KeptTests(InteractiveTests):
    """The source, dictionary and direction last chosen, for the next
    start (words.py: restore)."""

    def started(self) -> Session:
        """A session as interactive mode starts it."""
        import words
        new = Session(Lexicon.load(DATA), Settings())
        words.restore(new, io.StringIO(), interactive=True)
        return new

    def test_interactive_commands(self):
        import words
        from session import saved_to_latin
        self.run_lines('~D gaffiot')
        self.assertEqual((logeion.saved_source(), logeion.saved_dictionary()),
                         (logeion.LOGEION, 'gaffiot'))
        new = self.started()
        self.assertIs(new.other_source, new.logeion)
        self.assertEqual(new.logeion.dictionary, 'gaffiot')
        self.assertIn('~G: Logeion → Local   ~D: the dictionary (Gaffiot '
                      '2016)', words.banner(new))
        self.run_lines('~G', '~E')
        self.assertEqual(logeion.saved_source(), logeion.LOCAL)
        self.assertTrue(saved_to_latin())
        new = self.started()
        self.assertIsNone(new.other_source)
        self.assertTrue(new.reverse)
        self.run_lines('~L')
        self.assertFalse(self.started().reverse)

    def test_files_change_them_only_while_read(self):
        import words
        from session import saved_to_latin
        words.feed(self.session, ['~G', '~D ls', '~E'], lambda text: None)
        self.assertEqual(logeion.saved_source(), logeion.LOCAL)
        self.assertEqual(logeion.saved_dictionary(), logeion.ALL)
        self.assertFalse(saved_to_latin())

    def test_words_given_use_the_source_kept(self):
        import contextlib
        import words
        from session import save_to_latin

        def run(*args):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                words.main(['--datadir', DATA, *args])
            return out.getvalue()
        logeion.save_source(logeion.LOGEION)
        logeion.save_dictionary('gaffiot')
        save_to_latin(True)             # (not for words given: Latin)
        out = run('arma')
        self.assertIn('\nGaffiot 2016\n', out)
        self.assertNotIn('\nLewis & Short\n', out)
        self.assertIn('armum, armi  noun', run('--local', 'arma'))
        self.assertIn('\nLewis & Short\n', run('--dictionary', 'ls', 'arma'))
        self.assertEqual(logeion.saved_dictionary(), 'gaffiot')  # (kept)
        with self.assertRaises(SystemExit), \
                contextlib.redirect_stderr(io.StringIO()):
            run('--local', '--logeion', 'arma')


@unittest.skipUnless(isolate.display(), 'needs a display')
class WindowTests(unittest.TestCase):

    def setUp(self):
        import gc
        import tkinter as tk
        import config
        import words_gui
        self.root = tk.Tk()
        forget_choices(self)
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
        #  (the analysis, styled as this program's results)
        self.assertEqual(t.get('2.0', '2.end'),
                         '  armum, armi  noun, 2nd declension, neuter')
        self.assertIn('headword', t.tag_names('2.3'))
        self.assertIn('analysis', t.tag_names('3.end-2c'))
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

    def test_direction_kept(self):
        import words_gui
        from session import saved_to_latin
        self.app.to_latin.invoke()              # (a click)
        self.assertTrue(saved_to_latin())
        other = words_gui.App(self.root, DATA)
        self.assertTrue(other.reverse.get())
        #  (words given to look up have their own direction, not kept)
        given = words_gui.App(self.root, DATA, 'amicus')
        self.assertFalse(given.reverse.get())
        given.look_up('friend', True)
        self.app.to_language.invoke()
        self.assertFalse(saved_to_latin())

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
