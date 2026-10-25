"""Tests of the results in the window (gui_results.py) and of its menus."""

import gc
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

from gui_results import kind_of  # noqa: E402
from test_gui_settings import DATA, _display  # noqa: E402


class KindTests(unittest.TestCase):
    """The kind of each line, from the layout of the results."""

    def test_kinds(self):
        for line, kind in (
                ('arma', 'word'),
                ('  armum, armi  noun, 2nd declension, neuter  [XWXAO]',
                 'entry'),
                ('  -que  enclitic', 'entry'),
                ('  (unknown)', 'note'),
                ('  (near spellings: amicus)', 'note'),
                ('  spelling: Word mod l -> ll', 'note'),
                ('    arms (pl.), weapons, armor, shield;', 'meaning'),
                ('    arm-a          NOM.PL', 'form'),
                ('    amicius        CMPR', 'form'),
                ('      PERF PASSIVE PPL + verb TO_BE', 'detail'),
                ('', 'blank')):
            self.assertEqual(kind_of(line), kind, line)


@unittest.skipUnless(_display(), 'needs a display')
class WindowTests(unittest.TestCase):

    def setUp(self):
        import tkinter as tk
        import words_gui
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ['PY_WORDS_CONFIG']
        os.environ['PY_WORDS_CONFIG'] = self.tmp.name
        self.root = tk.Tk()
        self.app = words_gui.App(self.root, DATA)
        self.wait(lambda: self.app.session is not None)

    def tearDown(self):
        self.root.destroy()
        del self.root, self.app
        gc.collect()        # (Tk must be freed here, not by another thread)
        os.environ['PY_WORDS_CONFIG'] = self.old
        self.tmp.cleanup()

    def wait(self, ready, times=800):
        for _ in range(times):
            if ready():
                return
            self.root.update()
            self.root.after(25)
        self.fail('timed out')

    def look_up(self, query, to_latin=False):
        self.app.look_up(query, to_latin)
        self.wait(lambda: query in self.app.text.get('1.0', '2.0') and
                  str(self.app.button['state']) == 'normal')

    def test_menus(self):
        bar = self.app.menu_bar
        labels = [bar.entrycget(i, 'label')
                  for i in range(bar.index('end') + 1)]
        self.assertEqual(labels, ['Dictionary', 'View', 'Help'])

    def test_styled_results(self):
        self.look_up('arma')
        t = self.app.text
        self.assertIn('word', t.tag_names('1.0'))
        self.assertIn('headword', t.tag_names('2.3'))
        codes = t.tag_ranges('codes')
        self.assertEqual(t.get(codes[0], codes[1]), '[XWXAO]')
        analysis = t.tag_ranges('analysis')
        self.assertEqual(t.get(analysis[0], analysis[1]), 'NOM.PL')
        #  (the text is that of the command line)
        self.assertEqual(t.get('1.0', 'end-1c'),
                         self.app.shown[0])

    def test_links_and_double_clicks(self):
        self.look_up('arma')
        links = list(self.app.results.links.values())
        self.assertIn(('armum', False), links)
        asked = []
        self.app.results.on_lookup = lambda q, r: asked.append((q, r))
        t = self.app.text
        lines = t.get('1.0', 'end').split('\n')
        meaning = lines.index(next(x for x in lines if x.startswith(
            '    arms'))) + 1
        form = lines.index(next(x for x in lines if x.startswith(
            '    arm-a'))) + 1
        self.assertEqual(self.app.results._word_at(f'{meaning}.6'),
                         ('arms', True))         # (a meaning: to Latin)
        self.assertEqual(self.app.results._word_at(f'{form}.5'),
                         ('arma', False))        # (the whole form)

    def test_explanations(self):
        self.assertIn('frequency: frequent',
                      self.app.explain_codes('XXXBO'))
        self.assertIn('GEN  genitive',
                      self.app.explain_analysis('GEN.PL'))

    def test_find(self):
        self.look_up('arma')
        self.app.find()
        r = self.app.results
        r.find_entry.insert(0, 'arm-a')
        r._search()
        self.assertTrue(r.matches)
        self.assertTrue(self.app.text.tag_ranges('found_now'))
        r.hide_find()
        self.assertFalse(self.app.text.tag_ranges('found'))

    def test_welcome_examples(self):
        examples = list(self.app.results.links.values())
        self.assertIn(('amicorum', False), examples)
        self.assertIn(('friend', True), examples)

    def test_pearse_codes_are_shown_as_they_are(self):
        self.app.change_setting('pearse_codes', True)
        self.look_up('arma')
        self.assertFalse(self.app.text.tag_ranges('headword'))
