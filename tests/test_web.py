"""Tests of the dictionary in the browser (words_web.py), through its WSGI
application."""

import io
import os
import sys
import unittest
from wsgiref.util import setup_testing_defaults

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

import words_web  # noqa: E402
from lexicon import default_datadir  # noqa: E402


class WebTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = words_web.WebApp(default_datadir(),
                                   {'localhost', '127.0.0.1'})

    def call(self, path='/', query='', method='GET', body='',
             host='127.0.0.1:8000'):
        env = {'PATH_INFO': path, 'QUERY_STRING': query,
               'REQUEST_METHOD': method, 'HTTP_HOST': host,
               'CONTENT_LENGTH': str(len(body.encode())),
               'wsgi.input': io.BytesIO(body.encode())}
        setup_testing_defaults(env)
        got = {}

        def start(status, headers):
            got['status'], got['headers'] = status, dict(headers)
        out = b''.join(self.app(env, start)).decode()
        return got['status'], got['headers'], out

    def test_dark_mode(self):
        """The box of the page: ticked, dark, if not, light (until it is
        used, as the system); kept in the configuration file, which the
        windows share."""
        import config
        token = self.app.token
        box = '<input type="checkbox" name="dark" value="1"'
        try:
            page = self.call()[2]
            self.assertIn('<html lang="en">', page)    # (as the system)
            self.assertIn(box + '>', page)
            self.assertIn('<label title="Dark mode">\n', page)  # (a moon)
            for body, saved, attribute, checked in (
                    (f'token={token}&dark=1', True, 'dark', ' checked'),
                    (f'token={token}', False, 'light', '')):
                status, _, _ = self.call('/appearance', method='POST',
                                         body=body)
                self.assertEqual(status, '303 See Other')
                self.assertEqual(config.section('appearance'),
                                 {'dark_mode': saved})
                page = self.call()[2]
                self.assertIn(f'<html lang="en" data-theme="{attribute}">',
                              page)
                self.assertIn(box + checked + '>', page)
            self.assertEqual(self.call('/appearance', method='POST',
                                       body='token=no&dark=1')[0],
                             '403 Forbidden')
        finally:
            config.update('appearance', {})

    def test_fuzzy_search(self):
        """The "Fuzzy search" box, beside "Meanings in": it changes the
        setting (kept in the configuration file), and the search is made
        again; it is not among the settings below."""
        import config
        token = self.app.token
        box = '<input type="checkbox" name="fuzzy" value="1"'
        try:
            page = self.call(query='q=amicuss')[2]
            self.assertIn(box + ' checked>', page)
            self.assertIn('(near spellings: amicus)', page)
            self.assertNotIn('value="fuzzy_search"', page)
            status, headers, _ = self.call(
                '/fuzzy', method='POST', body=f'token={token}&q=amicuss')
            self.assertEqual(status, '303 See Other')
            self.assertEqual(headers['Location'], '/?q=amicuss')
            self.assertIs(config.section('parameters')['fuzzy_search'],
                          False)
            page = self.call(query='q=amicuss')[2]
            self.assertIn(box + '>', page)
            self.assertNotIn('(near spellings: amicus)', page)
            #  (the settings below leave it as it is)
            self.call('/settings', method='POST',
                      body=f'token={token}&on=trim_output')
            self.assertFalse(self.app.saved.fuzzy_search)
            self.call('/fuzzy', method='POST',
                      body=f'token={token}&fuzzy=1')
            self.assertTrue(self.app.session.settings.fuzzy_search)
            self.assertEqual(self.call('/fuzzy', method='POST',
                                       body='token=no')[0], '403 Forbidden')
        finally:
            self.app.change({name: getattr(words_web.Settings(), name)
                             for name in words_web.SHOWN + ('fuzzy_search',)})

    def test_styled_results(self):
        """Each line in an element of its kind (see layout.py), the codes
        and analyses explained, the forms whole for a double click."""
        page = self.call(query='q=arma')[2]
        self.assertIn('<span class="k-word"><strong>arma</strong></span>',
                      page)
        self.assertIn('<span class="k-entry">  <a href="/?q=armum">armum'
                      '</a>, armi', page)
        self.assertIn('<abbr class="codes" title="X  age: in use '
                      'throughout', page)
        self.assertIn('<span class="form" data-q="arma">arm-a</span>', page)
        self.assertIn('<abbr class="an" title="NOM  nominative', page)
        self.assertIn('<span class="k-meaning">', page)
        self.assertNotIn('data-to-latin', page)
        page = self.call(query='q=friend&lang=en')[2]
        self.assertIn('<pre class="results" data-to-latin="1">', page)

    def test_home_page_link(self):
        page = self.call()[2]
        self.assertIn('<a class="home" href="https://nicolasvaughan.org" '
                      'target="_blank" rel="noopener">nicolasvaughan.org</a>',
                      page)

    def test_welcome_examples(self):
        page = self.call()[2]
        self.assertIn('<a href="/?q=amicorum">amicorum</a>', page)
        self.assertIn('<a href="/?q=friend&amp;lang=en">friend (to Latin)'
                      '</a>', page)

    def test_pearse_codes_as_they_are(self):
        try:
            self.app.change({'pearse_codes': True})
            page = self.call(query='q=arma')[2]
            self.assertNotIn('<span class="k-entry">', page)
        finally:
            self.app.change({'pearse_codes': False})

    def test_lookup(self):
        status, _, page = self.call(query='q=amicorum')
        self.assertEqual(status, '200 OK')
        self.assertIn('<a href="/?q=amicus">amicus</a>, amici', page)

    def test_escaped(self):
        _, _, page = self.call(query='q=%3Cscript%3Ex')
        self.assertNotIn('<script>x', page)
        self.assertIn('&lt;script&gt;x', page)

    def test_other_host_refused(self):
        self.assertEqual(self.call(host='evil.example')[0],
                         '400 Bad Request')

    def test_form_needs_token(self):
        self.assertEqual(self.call('/settings', method='POST',
                                   body='token=no')[0], '403 Forbidden')

    def test_settings_change(self):
        token = self.app.token
        status, headers, _ = self.call(
            '/settings', method='POST', body=f'token={token}&q=est')
        self.assertEqual(status, '303 See Other')
        self.assertIn('q=est', headers['Location'])
        self.assertFalse(self.app.saved.trim_output)
        self.call('/settings', method='POST', body=f'token={token}&usual=1')
        self.assertTrue(self.app.saved.trim_output)

    def test_history(self):
        self.call(query='q=rosa')
        self.assertIn('>rosa</a>', self.call()[2])
        self.call('/history/clear', method='POST',
                  body=f'token={self.app.token}')
        self.assertIn('None yet.', self.call()[2])


class LanguageTests(unittest.TestCase):
    """The pull-down of the languages of the meanings."""

    def setUp(self):
        import tempfile
        import spanish
        self.tmp = tempfile.TemporaryDirectory()
        self.app = words_web.WebApp(spanish.datadir(self.tmp.name),
                                    {'127.0.0.1'})

    def tearDown(self):
        self.app.change({'language': 'en'})     # (the tests' own config)
        self.tmp.cleanup()

    call = WebTests.call

    def test_choose(self):
        page = self.call(query='q=est')[2]
        self.assertIn('<option value="es">Spanish</option>', page)
        self.assertIn('<option value="en" selected>English</option>', page)
        status, headers, _ = self.call(
            '/language', method='POST',
            body=f'token={self.app.token}&language=es&q=friend&lang=en')
        self.assertEqual(status, '303 See Other')
        self.assertIn('lang=es', headers['Location'])   # (still reverse)
        self.assertEqual(self.app.saved.language, 'es')
        page = self.call(query='q=est')[2]
        self.assertIn('ser; existir;', page)
        self.assertIn('Latin → Spanish', page)
        self.assertEqual(self.call('/language', method='POST',
                                   body='language=en')[0], '403 Forbidden')


if __name__ == '__main__':
    unittest.main()


class SiteTests(unittest.TestCase):
    """The static site (pages/build.py): what app.js expects to find."""

    def test_languages_downloaded_when_chosen(self):
        import importlib.util
        import tempfile
        import zipfile
        import languages
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location(
            'build', os.path.join(root, 'pages', 'build.py'))
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        with tempfile.TemporaryDirectory() as out:
            build.build(out)
            beside = sorted(os.listdir(os.path.join(out, 'languages')))
            with zipfile.ZipFile(os.path.join(out, 'py-words.zip')) as z:
                z.extractall(os.path.join(out, 'unpacked'))
                names = set(z.namelist())
            data = os.path.join(out, 'unpacked', 'data')
            self.assertIn('words.py', names)
            self.assertIn('data/dictionary.xml', names)
            for code, path in languages.files(data).items():
                with open(path, encoding='utf-8') as f:
                    text = f.read()
                if code in build.IN_ZIP:
                    self.assertNotIn(build.STUB, text)
                    self.assertNotIn(code + '.xml', beside)
                else:               # (only the start, with the name)
                    self.assertIn(build.STUB, text)
                    self.assertIn(code + '.xml', beside)
            self.assertEqual(languages.names(data)['fr'], 'French')
