"""Tests of the help (guide.py) and of where the programs show it."""

import io
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

import guide  # noqa: E402
import interface  # noqa: E402
import words  # noqa: E402
from lexicon import Lexicon  # noqa: E402
from session import Session  # noqa: E402
from settings import Settings  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

LEXICON = None


def session(**settings):
    global LEXICON
    if LEXICON is None:
        LEXICON = Lexicon.load(DATA)
    return Session(LEXICON, Settings(**settings), write=lambda text: None)


class GuideTests(unittest.TestCase):

    def tearDown(self):
        interface.use('en')

    def text(self, **settings):
        return guide.text(guide.blocks(session(**settings),
                                       guide.paragraphs(guide.WINDOW)))

    def test_sections(self):
        text = self.text()
        for heading in ('Searching', 'Using this program',
                        'Reading the results', 'The codes in brackets',
                        'The abbreviations of the analyses', 'Settings'):
            self.assertIn(heading + '\n' + '-' * len(heading), text)
        flat = ' '.join(text.split())
        self.assertIn('The menus have the rest: Dictionary', flat)
        self.assertIn('double-click any word', flat)
        self.assertIn('"Fuzzy search", beside it', flat)

    def test_example(self):
        text = self.text()
        self.assertIn('This is what py-words shows for amicorum:', text)
        self.assertIn('amicus, amici  noun, 2nd declension, masculine  '
                      '[XXXBO]', text)
        self.assertIn('amīc-orum      GEN.PL', text)
        #  (in words, if the glosses are off)
        self.assertIn('genitive plural', self.text(use_glosses=False))

    def test_codes(self):
        text = self.text()
        self.assertIn('X  age        in use throughout', text)
        self.assertIn('B  frequency  frequent', text)
        self.assertIn('O  source     Oxford Latin Dictionary', text)
        self.assertIn('    W  war, the army, the navy', text)
        self.assertIn('    S  Lewis and Short', text)
        self.assertNotIn('(unused)', text)

    def test_other_sources(self):
        """[XXXCO+M]: the other sources explained after the five
        letters."""
        text = guide.explain_codes('XXXCO+M', DATA)
        self.assertIn('O  source: Oxford Latin Dictionary', text)
        self.assertTrue(text.endswith('M  other source: Latham, Medieval '
                                      'Word List / DMLBS'), text)

    def test_glosses(self):
        text = self.text()
        self.assertIn('Case: NOM nominative, GEN genitive', text)
        self.assertIn('SUP* supine', text)          # (not Leipzig)

    def test_width(self):
        for line in self.text().split('\n'):
            if not line.startswith('  ') or line.startswith('  * '):
                self.assertLessEqual(len(line), 76, line)

    def test_spanish(self):
        interface.use('es')
        text = self.text(language='es')
        self.assertIn('Los códigos entre corchetes', text)
        self.assertIn('B  frecuencia  frecuente', text)
        self.assertIn('Caso: NOM nominativo, GEN genitivo', text)
        self.assertIn('Persona: 1 primera persona', text)
        self.assertIn('amigo, aliado', text)
        self.assertIn('X  general o desconocida', text)

    def test_html(self):
        page = guide.html([('h', 'A & B'), ('p', 'x < y'), ('li', 'one'),
                           ('li', 'two'), ('pre', 'a\n b')])
        self.assertEqual(page, '<h3>A &amp; B</h3>\n<p>x &lt; y</p>\n<ul>\n'
                               '<li>one</li>\n<li>two</li>\n</ul>\n'
                               '<pre>a\n b</pre>')


class ProgramTests(unittest.TestCase):

    def test_command_line(self):
        out = subprocess.run([sys.executable, os.path.join(ROOT, 'words.py'),
                              '--datadir', DATA, '--interface', 'en',
                              '--guide'], capture_output=True, text=True,
                             check=True).stdout
        self.assertIn('The codes in brackets', out)
        self.assertIn('~H         the help', out)

    def test_interactive(self):
        said = []
        words.command(session(), '~H', None, said.append)
        self.assertIn('Reading the results', said[0])
        said = []
        words.command(session(), '?', None, said.append)
        self.assertIn('~H', said[0])

    def test_web_page(self):
        import words_web
        app = words_web.WebApp(DATA)
        environ = {'REQUEST_METHOD': 'GET', 'PATH_INFO': '/',
                   'QUERY_STRING': '', 'HTTP_HOST': '127.0.0.1:8000',
                   'wsgi.input': io.BytesIO()}
        page = b''.join(app(environ, lambda *a: None)).decode()
        self.assertNotIn('help-button', page)       # (only the section)
        self.assertIn('<details id="help"><summary>Help</summary>', page)
        self.assertIn('&quot;Help&quot; and &quot;About&quot;, below', page)
        self.assertIn('<h3>The codes in brackets</h3>', page)
        self.assertIn('At the foot, "Earlier searches" lists', page)
        app.close()


if __name__ == '__main__':
    unittest.main()
