"""Pruebas de la página web (words_web.py), mediante su aplicación
WSGI."""

import io
import json
import os
import sys
import unittest
from wsgiref.util import setup_testing_defaults

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # el programa, desde cualquier carpeta
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

    def test_about_commit(self):
        """In "About", the commit is a link that shows its short hash."""
        import version
        old = version.commit
        version.commit = lambda: 'c' * 40
        try:
            page = self.call()[2]
        finally:
            version.commit = old
        self.assertIn(f'Commit: <a href="{version.URL}/commit/' + 'c' * 40 +
                      '" target="_blank" rel="noopener">' + 'c' * 7 + '</a>',
                      page)
        self.assertIn('William Whitaker', page)

    def test_footer(self):
        """At the foot of the page, the university's logo (drawn in the
        colour of the text, for both themes) and its legal notice."""
        page = self.call()[2]
        footer = page[page.index('<footer>'):page.index('</footer>')]
        self.assertIn('<svg role="img" aria-label="Universidad de los Andes',
                      footer)
        self.assertIn('fill="currentColor"', footer)
        self.assertIn('Vigilada Mineducación', footer)
        self.assertIn('Resolución 000194 del 16 de enero del 2025.', footer)

    def test_no_consent(self):
        """The local page (no cookies, no internet) has no cookie
        consent."""
        _, headers, page = self.call()
        self.assertNotIn('usercentrics', page)
        self.assertNotIn('usercentrics', headers['Content-Security-Policy'])

    def test_dark_mode(self):
        """The box of the page: ticked, dark, if not, light (until it is
        used, following the system); kept in the configuration file, which the
        windows share."""
        import config
        token = self.app.token
        box = '<input type="checkbox" name="dark" value="1"'
        try:
            page = self.call()[2]
            self.assertIn('<html lang="en">', page)    # (según el sistema)
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
            #  (los ajustes de abajo lo dejan como está)
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


class PublicTests(unittest.TestCase):
    """public_app(), for everyone: each visitor's choices in their own
    cookies, and nothing saved on the server."""

    @classmethod
    def setUpClass(cls):
        cls.app = words_web.public_app()

    @classmethod
    def tearDownClass(cls):
        import interface
        interface.use('en')

    def call(self, jar, path='/', query='', method='GET', body='',
             accept=''):
        """A request of the visitor whose cookies are JAR (changed as the
        browser would)."""
        from urllib.parse import quote
        env = {'PATH_INFO': path, 'QUERY_STRING': query,
               'REQUEST_METHOD': method, 'HTTP_HOST': 'example.org',
               'CONTENT_LENGTH': str(len(body.encode())),
               'wsgi.input': io.BytesIO(body.encode()),
               'HTTP_COOKIE': '; '.join(f'{k}={quote(v, safe="")}'
                                        for k, v in jar.items())}
        if accept:
            env['HTTP_ACCEPT_LANGUAGE'] = accept
        setup_testing_defaults(env)
        got = {}

        def start(status, headers):
            got['status'] = status
            got['headers'] = headers
        out = b''.join(self.app(env, start)).decode()
        from urllib.parse import unquote
        for name, value in got['headers']:
            if name == 'Set-Cookie':
                pair, *attributes = value.split('; ')
                key, _, value = pair.partition('=')
                if 'Max-Age=0' in attributes:
                    jar.pop(key, None)
                else:
                    jar[key] = unquote(value)
        self.headers = dict(got['headers'])
        return got['status'], out

    def post(self, jar, path, fields=''):
        self.call(jar)                          # (la página: su token)
        body = f'token={jar["words_token"]}' + (f'&{fields}' if fields
                                                else '')
        return self.call(jar, path, method='POST', body=body)

    def test_consent(self):
        """The university's cookie consent (Usercentrics): its script,
        with the page's nonce, and its servers allowed by the CSP."""
        page = self.call({})[1]
        csp = self.headers['Content-Security-Policy']
        nonce = csp.split("'nonce-")[1].split("'")[0]
        self.assertIn(f'<script id="usercentrics-cmp" nonce="{nonce}" '
                      'src="https://app.usercentrics.eu/browser-ui/latest/'
                      'loader.js" data-settings-id="Lqn7YUJNI-tBas" async>'
                      '</script>', page)
        for directive in ('script-src', 'connect-src', 'img-src'):
            policy = csp.split(directive, 1)[1].split(';')[0]
            self.assertIn('https://*.usercentrics.eu', policy)

    def test_visitors_apart(self):
        """What a visitor changes is theirs only, and is not saved on the
        server."""
        import config
        from history import History
        a, b = {}, {}
        before = History().items
        self.assertEqual(self.post(a, '/appearance', 'dark=1')[0],
                         '303 See Other')
        self.post(a, '/interface', 'interface=es')
        self.post(a, '/settings', 'on=show_codes')
        self.call(a, query='q=amicus')
        page_a = self.call(a)[1]
        self.assertIn('<html lang="es" data-theme="dark">', page_a)
        self.assertIn('href="/?q=amicus"', page_a)
        self.assertEqual(a['words_interface'], 'es')
        self.assertEqual(a['words_language'], 'es')
        page_b = self.call(b)[1]
        self.assertIn('<html lang="en">', page_b)
        self.assertNotIn('href="/?q=amicus"', page_b)
        self.assertIn('Changes are kept in this browser', page_b)
        self.assertEqual(config.section('appearance'), {})
        self.assertEqual(History().items, before)
        self.assertIn('<html lang="es" data-theme="dark">', self.call(a)[1])

    def test_interface_switch(self):
        """The round button with the code of the language of the
        interface, beside the moon: its list marks the current language,
        and choosing another changes the interface."""
        jar = {}
        page = self.call(jar)[1]
        self.assertIn('aria-label="Language of the interface">EN</summary>',
                      page)
        self.assertIn('value="en" lang="en" aria-current="true">English'
                      '</button>', page)
        self.assertIn('value="la" lang="la">Latina</button>', page)
        self.assertLess(page.index('id="interface"'), page.index('id="dark"'))
        self.assertEqual(self.post(jar, '/interface',
                                   'interface=es&switch=1')[0],
                         '303 See Other')
        page = self.call(jar)[1]
        self.assertIn('>ES</summary>', page)
        self.assertIn('value="es" lang="es" aria-current="true">Español'
                      '</button>', page)
        self.assertEqual(jar['words_interface'], 'es')

    def test_history(self):
        """The earlier searches, newest first, in a cookie; cleared, the
        cookie goes."""
        jar = {}
        for q in ('amo', 'amicus', 'amo'):
            self.call(jar, query='q=' + q)
        self.assertEqual(json.loads(jar['words_history']),
                         ['amicus', 'amo'])
        page = self.call(jar)[1]
        self.assertLess(page.index('href="/?q=amo"'),
                        page.index('href="/?q=amicus"'))
        self.post(jar, '/history/clear')
        self.assertNotIn('words_history', jar)
        #  el mensaje, una vez, solo a este visitante
        self.assertIn('The history of the searches is cleared.',
                      self.call(jar)[1])
        self.assertNotIn('is cleared', self.call(jar)[1])

    def test_browser_language(self):
        """With no cookies, the interface and the meanings in the
        browser's language (if there are files for it)."""
        self.assertIn('<html lang="es">',
                      self.call({}, accept='es-CO,es;q=0.9,en;q=0.8')[1])
        self.assertIn('<html lang="en">', self.call({}, accept='fr')[1])

    def test_token(self):
        """A form needs the token of the visitor's own cookie."""
        jar = {}
        self.call(jar)
        self.assertEqual(self.call({}, '/appearance', method='POST',
                                   body=f'token={jar["words_token"]}')[0],
                         '403 Forbidden')
        self.assertEqual(self.call(jar, '/appearance', method='POST',
                                   body='token=no')[0], '403 Forbidden')


class LogeionTests(unittest.TestCase):
    """"Search in": Logeion's entries for the lemmas of the words (asked of
    a fake Logeion, see test_logeion.Client), kept in the configuration
    file."""

    call = WebTests.call

    @classmethod
    def setUpClass(cls):
        import logeion
        from test_logeion import Client
        cls.app = words_web.WebApp(default_datadir(),
                                   {'localhost', '127.0.0.1'})
        cls.client = Client()
        cls.app.logeion = logeion.Logeion(cls.client)

    def setUp(self):
        import config
        import logeion
        from test_logeion import forget_choices
        forget_choices(self)
        #  (todos los diccionarios: las páginas falsas no tienen DMLBS)
        config.update(logeion.SECTION, {'dictionary': logeion.ALL})

    def choose(self, fields: str):
        return self.call('/source', method='POST',
                         body=f'token={self.app.token}&q=arma&{fields}')

    def test_logeion(self):
        """Chosen, it is kept; the words are analysed here and Logeion's
        entries follow; what Logeion cannot do is greyed out."""
        import logeion
        page = self.call(query='q=arma')[2]
        self.assertIn('<option value="local" selected>py-words</option>', page)
        self.assertNotIn('name="dictionary"', page)
        self.assertNotIn(' disabled', page)
        status, headers, _ = self.choose('source=logeion')
        self.assertEqual(status, '303 See Other')
        self.assertEqual(headers['Location'], '/?q=arma')
        self.assertEqual(logeion.saved_source(), logeion.LOGEION)
        page = self.call(query='q=arma')[2]
        self.assertIn('<option value="logeion" selected>Logeion</option>',
                      page)
        self.assertIn('<select name="dictionary"', page)
        self.assertIn('<select name="language" disabled>', page)
        self.assertIn('name="fuzzy" value="1" checked disabled>', page)
        self.assertIn('value="en" disabled>', page)
        results = page[page.index('<pre class="results"'):
                       page.index('</pre>')]
        #  el análisis, como los resultados de este programa, luego las
        #  entradas
        self.assertIn('<span class="lg-b">arma</span><span class="lg-d">  '
                      '→  armum, armo</span>', results)
        self.assertIn('<a href="/?q=armum">armum</a>, armi  noun', results)
        self.assertIn('<span class="form" data-q="arma">arm-a</span>',
                      results)
        self.assertLess(results.index('NOM.PL'),
                        results.index('Lewis &amp; Short'))
        self.assertIn('<span class="lg-i">arms</span>', results)
        #  un enlace a una palabra de Logeion la busca aquí; otros, una
        #  pestaña nueva
        self.assertIn('see <a href="/?q=armo">armo</a>', results)
        self.assertIn('<a href="https://example.org/arms" target="_blank" '
                      'rel="noopener">more</a>', results)
        self.assertIn('Logeion has no entry for armum (the nearest: armus).',
                      results)
        #  (each line a block, wrapped by the browser, hanging)
        self.assertIn('<span class="ln" style="padding-left:4ch;'
                      'text-indent:-4ch">  • arma, weapons</span>', results)

    def test_dictionary(self):
        """The list beside "Search in": only that dictionary of Logeion."""
        import logeion
        self.choose('source=logeion&dictionary=gaffiot')
        self.assertEqual(logeion.saved_dictionary(), 'gaffiot')
        page = self.call(query='q=arma')[2]
        results = page[page.index('<pre class="results"'):
                       page.index('</pre>')]
        self.assertIn('ustensiles, armes', results)
        self.assertNotIn('lg-s">Lewis &amp; Short', results)
        self.assertIn('Gaffiot 2016 has no entry for armo (it is in: Lewis '
                      '&amp; Short).', results)
        self.assertIn('<option value="gaffiot" selected>', page)
        self.choose('dictionary=nonsense')          # (left as it was)
        self.assertEqual(logeion.saved_dictionary(), 'gaffiot')

    def test_to_latin(self):
        """Logeion searches in Latin only: a search to Latin is made in
        this dictionary, which is then kept (as the window does); choosing
        Logeion goes back to Latin."""
        import logeion
        self.choose('source=logeion')
        page = self.call(query='q=friend&lang=en')[2]
        self.assertIn('amicus', page)
        self.assertEqual(logeion.saved_source(), logeion.LOCAL)
        _, headers, _ = self.call(
            '/source', method='POST',
            body=f'token={self.app.token}&q=arma&lang=en&source=logeion')
        self.assertEqual(headers['Location'], '/?q=arma')

    def test_unreachable(self):
        """If Logeion cannot be reached, the page says so."""
        import logeion
        from test_logeion import Client
        self.choose('source=logeion')
        self.app.logeion = logeion.Logeion(Client(down=True))
        try:
            page = self.call(query='q=arma')[2]
        finally:
            self.app.logeion = logeion.Logeion(self.client)
        self.assertIn('Logeion could not be reached: no network', page)
        self.assertIn('NOM.PL', page)           # (the analysis, still)

    def test_only_some_words(self):
        """Logeion is asked for the first LOGEION_WORDS words only."""
        from unittest import mock
        self.choose('source=logeion')
        with mock.patch.object(words_web, 'LOGEION_WORDS', 1):
            del self.client.asked[:]
            page = self.call(query='q=arma+dixi')[2]
        self.assertNotIn('dico', self.client.asked)
        self.assertIn('(Logeion is asked only for the first 1 words.)', page)

    def test_need_token(self):
        self.assertEqual(self.call('/source', method='POST',
                                   body='token=no&source=logeion')[0],
                         '403 Forbidden')


class PublicLogeionTests(unittest.TestCase):
    """Public, "Search in" is each visitor's, in their cookies."""

    call = PublicTests.call
    post = PublicTests.post

    @classmethod
    def setUpClass(cls):
        import logeion
        from test_logeion import Client
        cls.app = words_web.public_app()
        cls.app.logeion = logeion.Logeion(Client())

    @classmethod
    def tearDownClass(cls):
        import interface
        interface.use('en')

    def test_visitors_apart(self):
        import logeion
        a, b = {}, {}
        self.post(a, '/source', 'source=logeion&dictionary=gaffiot')
        self.assertEqual(a['words_source'], 'logeion')
        self.assertEqual(a['words_dictionary'], 'gaffiot')
        self.assertEqual(logeion.saved_source(), logeion.LOCAL)
        self.assertIn('ustensiles, armes', self.call(a, query='q=arma')[1])
        page = self.call(b, query='q=arma')[1]
        self.assertNotIn('ustensiles', page)
        self.assertIn('<option value="local" selected>', page)
        #  (en Logeion, el DMLBS hasta que se elija otro diccionario)
        self.post(b, '/source', 'source=logeion')
        page = self.call(b, query='q=arma')[1]
        self.assertIn('<option value="dmlbs" selected>', page)
        self.assertIn('DMLBS has no entry for arma', page)


if __name__ == '__main__':
    unittest.main()
