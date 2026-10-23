#!/usr/bin/env python3
"""The dictionary in a web browser: python3 words_web.py

Starts a small web server on this computer and opens the browser at it:

    http://127.0.0.1:8000/                  the search page
    http://127.0.0.1:8000/?q=amicus+est     a search (Latin to English)
    http://127.0.0.1:8000/?q=friend&lang=en a search (English to Latin)

(lang= the language of the meanings, en or es ..., for a search from it
to Latin.)

The results are those of words.py; the settings, the configuration file
and the history of the searches are shared with it, the window and the
terminal.  The dictionary is read again when an editor changes it.

Only this computer can reach the server, unless --host says otherwise
(--host 0.0.0.0: every computer that can reach this one, as a phone on
the same network).  There are no passwords, so do that only on a network
you trust; the dictionary cannot be edited from the browser.
"""

from version import check_python
check_python()          # (before the modules that need it)

import argparse
import errno
import html
import ipaddress
import json
import os
import secrets
import socket
import sys
import threading
import webbrowser
from string import Template
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlencode
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import config
import guide
import interface
from config import ConfigError
from helptext import HELP
from history import History
from layout import CODES, FORM_LINE, HEADWORD, analysis_of, kind_of
from interface import N_, tr
from lexicon import DICTIONARY, Lexicon, default_datadir
from session import Session
from settings import (COMMAND_LINE, DEPENDS, DEV_MODES, MODES, ON_SCREEN,
                      Settings, ensure_config, first_sentence, label,
                      section_of)
from version import NAME, VERSION, about
from xmldata import DataError

HOST = '127.0.0.1'
PORT = 8000
MAX_QUERY = 2000                # (characters of a search)
MAX_FORM = 100_000              # (bytes of a form sent)
RECENT = 20                     # earlier searches listed
ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons',
                    'linux', 'icons', 'hicolor', '48x48', 'apps',
                    'py-words.png')

#  The author's web page, linked at the top right of the page
HOME_PAGE = 'https://nicolasvaughan.org'

#  The settings the page offers: those of the window (the pause and the
#  command characters only matter in the interactive command line)
SHOWN = tuple(n for n in MODES + DEV_MODES
              if n not in COMMAND_LINE + ON_SCREEN)



def from_language(params: dict) -> str:
    """The language a search is in, if not Latin: lang= in PARAMS."""
    lang = params.get('lang', [''])[0]
    return '' if lang == 'la' else lang


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def link(query: str, lang: str = '', **more) -> str:
    """The address of the search for QUERY (in LANG, a language of the
    meanings; '': in Latin)."""
    params = {'q': query} if query else {}
    if lang:
        params['lang'] = lang
    params.update(more)
    return '/?' + urlencode(params) if params else '/'


class WebApp:
    """The dictionary as a WSGI application: WebApp(datadir) can be given to
    any WSGI server (see main)."""

    def __init__(self, datadir: str, hosts: set[str] | None = None):
        """HOSTS: the names the server may be reached by (None: any), so
        that other web sites cannot use it through their own names."""
        self.datadir = datadir
        self.hosts = hosts
        settings = Settings()
        settings.load(datadir)
        #  the settings as saved (kept for the command line), and those
        #  used here, which do not pause
        self.saved = settings.copy()
        settings.pause_in_screen_output = False
        self.mtime = self._mtime()
        self.session = Session(Lexicon.load(datadir), settings)
        self.lock = threading.Lock()
        #  sent with every form, so that only this page can change things
        self.token = secrets.token_urlsafe(24)
        self.message = self.session.notice
        self._help: dict[tuple, str] = {}   # (the help, as HTML)
        #  (the explanations of the codes and analyses, by language)
        self._glosses: dict[str, dict[str, str]] = {}
        self._codes: dict[tuple, str] = {}

    def _mtime(self) -> float | None:
        try:
            return os.path.getmtime(os.path.join(self.datadir, DICTIONARY))
        except OSError:
            return None

    def _fresh(self):
        """Reads the dictionary again if it was changed since."""
        mtime = self._mtime()
        if mtime == self.mtime:
            return
        old = self.session
        self.session = Session(Lexicon.load(self.datadir), old.settings)
        self.mtime = mtime
        self.message = tr('The dictionary was changed, and read again.')

    # Requests -------------------------------------------------------------

    def __call__(self, environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET')
        path = environ.get('PATH_INFO') or '/'
        if not self._host_allowed(environ.get('HTTP_HOST', '')):
            return self._plain(start_response, '400 Bad Request',
                               tr('Unknown host name.'))
        routes = {'/': ('GET', self.page),
                  '/settings': ('POST', self.settings),
                  '/language': ('POST', self.choose_language),
                  '/interface': ('POST', self.choose_interface),
                  '/appearance': ('POST', self.choose_appearance),
                  '/fuzzy': ('POST', self.choose_fuzzy),
                  '/history/clear': ('POST', self.clear_history),
                  '/icon.png': ('GET', self.icon)}
        if path not in routes:
            return self._plain(start_response, '404 Not Found',
                               tr('There is no such page.'))
        allowed, handler = routes[path]
        if method == 'HEAD' and allowed == 'GET':
            handler(environ, start_response)
            return [b'']
        if method != allowed:
            return self._plain(start_response, '405 Method Not Allowed',
                               tr('Use {method}.', method=allowed),
                               [('Allow', allowed)])
        return handler(environ, start_response)

    def _host_allowed(self, host: str) -> bool:
        if self.hosts is None:
            return True
        if host.startswith('['):                        # [::1]:8000
            name = host[1:host.find(']')]
        else:
            name = host.rsplit(':', 1)[0]
        return name.lower() in self.hosts

    def _form(self, environ) -> dict[str, list[str]] | None:
        """The fields of a form sent, if it came from this page."""
        try:
            size = int(environ.get('CONTENT_LENGTH') or 0)
        except ValueError:
            return None
        if not 0 <= size <= MAX_FORM:
            return None
        body = environ['wsgi.input'].read(size).decode('utf-8', 'replace')
        form = parse_qs(body, keep_blank_values=True)
        token = form.get('token', [''])[0]
        if not secrets.compare_digest(token.encode(), self.token.encode()):
            return None
        return form

    @staticmethod
    def _plain(start_response, status: str, text: str, headers=()):
        start_response(status, [('Content-Type', 'text/plain; charset=utf-8'),
                                *headers])
        return [text.encode()]

    @staticmethod
    def _back(start_response, form: dict, **more):
        """Back to the search page (with the search the form came from)."""
        query = form.get('q', [''])[0]
        start_response('303 See Other',
                       [('Location', link(query, from_language(form),
                                          **more))])
        return [b'']

    def help_html(self) -> str:
        """The help (see guide.py), as HTML, in the languages in use (made
        once for each)."""
        s = self.session.settings
        key = (interface.code(), s.language, s.use_glosses,
               id(self.session.lexicon))
        if key not in self._help:
            self._help[key] = guide.html(guide.blocks(
                self.session, guide.paragraphs(guide.WEB)))
        return self._help[key]

    # Pages ----------------------------------------------------------------

    def page(self, environ, start_response):
        params = parse_qs(environ.get('QUERY_STRING', ''))
        query = ' '.join(params.get('q', [''])[0][:MAX_QUERY].split())
        reverse = bool(from_language(params))
        language = self.session.language
        history = History()
        if query:
            history.add(query)
            with self.lock:
                self._fresh()
                self.session.reverse = reverse
                try:
                    text = self.session.lookup(query)
                except Exception as e:          # show it, keep going
                    text = tr('(error: {error})', error=e)
                results = self.results(text.rstrip('\n') or
                                       tr('(no results)'))
        else:
            results = self.welcome(language.code)
        with self.lock:
            help_html = self.help_html()
        message, self.message = self.message, ''
        nonce = secrets.token_urlsafe(16)
        name = tr(language.name)
        body = PAGE.substitute(
            {key: esc(tr(text)) for key, text in PAGE_TEXTS.items()},
            **{key: json.dumps(tr(text)) for key, text in
               SCRIPT_TEXTS.items()},
            html_lang=esc(interface.code()),
            title=esc(f'{query} – {NAME}' if query else
                      tr('{name}: a Latin dictionary', name=NAME)),
            name=esc(NAME), version=esc(VERSION), about=esc(about()),
            home=esc(HOME_PAGE), home_name=esc(HOME_PAGE.split('//')[1]),
            query=esc(query), token=esc(self.token), nonce=nonce,
            la_checked='' if reverse else ' checked',
            en_checked=' checked' if reverse else '',
            lang=esc(language.code) if reverse else 'la',
            code=esc(language.code),
            to_language=esc(tr('Latin → {language}', language=name)),
            from_language=esc(tr('{language} → Latin', language=name)),
            placeholder=esc(tr('a word in {language} (and N, V, ADJ …)',
                               language=name))
            if reverse else esc(tr('Latin words or a line of Latin')),
            message=f'<p class="message">{esc(message)}</p>' if message
            else '',
            results=results,
            results_attrs=' data-to-latin="1"' if query and reverse else '',
            recent=self.recent(history,
                               language.code if reverse else ''),
            languages=self.language_options(language.code),
            interfaces=self.interface_options(),
            theme=self.theme_attribute(),
            dark_checked=' checked' if self.appearance() == 'dark' else '',
            fuzzy_checked=' checked' if self.saved.fuzzy_search else '',
            settings_open=' open' if params.get('s') else '',
            settings=self.settings_rows(),
            help=help_html)
        start_response('200 OK', [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store'),
            ('Content-Security-Policy',
             "default-src 'none'; img-src 'self'; style-src 'unsafe-inline';"
             f" script-src 'nonce-{nonce}'; form-action 'self';"
             " base-uri 'none'; frame-ancestors 'none'"),
            ('X-Content-Type-Options', 'nosniff'),
            ('Referrer-Policy', 'no-referrer')])
        return [body.encode()]

    def results(self, text: str) -> str:
        """The results as HTML (see layout.py): each line in an element of
        its kind, the words looked up in bold, each entry's first word a
        link to its search, and the codes and analyses explained by their
        title (and by the page's script, for a tap).  With the Pearse codes
        (a developer mode) the layout is another one: as it is."""
        if self.session.settings.do_pearse_codes:
            return esc(text)
        code = interface.code()
        if code not in self._glosses:
            self._glosses[code] = guide.gloss_table(self.session)
        table = self._glosses[code]
        out = []
        for line in text.split('\n'):
            kind = kind_of(line)
            if kind == 'blank':
                out.append('')
                continue
            if kind == 'word':
                body = f'<strong>{esc(line)}</strong>'
            elif kind == 'entry':
                body = self._entry(line)
            elif kind == 'form':
                body = self._form_line(line, table)
            else:
                body = esc(line)
            out.append(f'<span class="k-{kind}">{body}</span>')
        return '\n'.join(out)

    def _entry(self, line: str) -> str:
        """An entry: its first word a link, its codes explained."""
        m = HEADWORD.match(line)
        head, rest = ('', line) if m is None else (line[:m.end()],
                                                     line[m.end():])
        if m is not None:
            word = m.group(1)
            head = f'  <a href="{esc(link(word))}">{esc(word)}</a>'
        pieces, at = [], 0
        for c in CODES.finditer(rest):
            pieces.append(esc(rest[at:c.start()]))
            key = (interface.code(), c.group(1))
            if key not in self._codes:
                self._codes[key] = guide.explain_codes(c.group(1),
                                                       self.datadir)
            title = esc(self._codes[key])
            pieces.append(f'<abbr class="codes" title="{title}">'
                          f'{esc(c.group(0))}</abbr>')
            at = c.end()
        pieces.append(esc(rest[at:]))
        return head + ''.join(pieces)

    @staticmethod
    def _form_line(line: str, table: dict[str, str]) -> str:
        """A form: the form (whole, for a double click) and its analysis
        explained."""
        m = FORM_LINE.fullmatch(line)
        form, rest = m.group(2), m.group(4)
        out = (f'{m.group(1)}<span class="form" data-q="'
               f'{esc(form.replace("-", ""))}">{esc(form)}</span>'
               f'{m.group(3)}')
        analysis = analysis_of(rest)
        explained = guide.explain_analysis(analysis, table) if analysis \
            else ''
        if not explained:
            return out + esc(rest)
        return (out + f'<abbr class="an" title="{esc(explained)}">'
                f'{esc(analysis)}</abbr>' + esc(rest[len(analysis):]))

    def welcome(self, language: str) -> str:
        """What the page shows before the first search, with examples to
        click."""
        links = [f'<a href="{esc(link(query, language if to_latin else ""))}"'
                 f'>{esc(label)}</a>'
                 for label, query, to_latin in guide.examples(language)]
        return (esc(tr('Type a Latin word or line, and press Enter.  '
                       '"Help" and "About", below, explain the results and '
                       'show the credits.')) + '\n\n' +
                esc(tr('Try, for example:')) + '  ' + '  ·  '.join(links))

    def language_options(self, current: str) -> str:
        """The choices of the pull-down of the languages of the
        meanings."""
        return ''.join(
            f'<option value="{esc(code)}"'
            f'{" selected" if code == current else ""}>{esc(tr(name))}'
            '</option>'
            for code, name in self.session.lexicon.language_names().items())

    @staticmethod
    def interface_options() -> str:
        """The choices of the pull-down of the languages of the
        interface."""
        current = interface.code()
        return ''.join(
            f'<option value="{esc(code)}"'
            f'{" selected" if code == current else ""}>{esc(name)}</option>'
            for code, name in interface.names().items())

    @staticmethod
    def appearance() -> str:
        """The look of the page: 'dark' or 'light', as the setting
        dark_mode of the configuration file (shared with the windows) says,
        or 'system' if it says nothing (the browser follows the system)."""
        dark = config.section(APPEARANCE).get('dark_mode')
        return 'dark' if dark is True else 'light' if dark is False \
            else 'system'

    def theme_attribute(self) -> str:
        look = self.appearance()
        return '' if look == 'system' else f' data-theme="{look}"'

    def recent(self, history: History, lang: str) -> str:
        items = history.recent(RECENT)
        if not items:
            return f'<p class="note">{esc(tr("None yet."))}</p>'
        links = ''.join(f'<li><a href="{esc(link(item, lang))}">'
                        f'{esc(item)}</a></li>' for item in items)
        return f'<ul class="recent">{links}</ul>'

    def settings_rows(self) -> str:
        out = []
        for title, names in ((tr('Parameters'), MODES),
                             (tr('Developer modes'), DEV_MODES)):
            rows = []
            for name in names:
                if name not in SHOWN:
                    continue
                parent = DEPENDS.get(name)
                off = parent is not None and not getattr(self.saved, parent)
                text = tr(HELP.get(name, ''))
                rows.append(
                    f'<label class="setting{" off" if off else ""}" '
                    f'title="{esc(text)}"><input type="checkbox" name="on" '
                    f'value="{name}"'
                    f'{" checked" if getattr(self.saved, name) else ""}'
                    f'{" disabled" if off else ""}>'
                    f'<span>{esc(label(name))}</span>'
                    f'<small>{esc(first_sentence(text))}</small></label>')
            out.append(f'<fieldset><legend>{esc(title)}</legend>'
                       f'{"".join(rows)}</fieldset>')
        return ''.join(out)

    def icon(self, environ, start_response):
        try:
            with open(ICON, 'rb') as f:
                data = f.read()
        except OSError:
            return self._plain(start_response, '404 Not Found',
                               tr('No icon.'))
        start_response('200 OK', [('Content-Type', 'image/png'),
                                  ('Cache-Control', 'max-age=86400')])
        return [data]

    # Changes --------------------------------------------------------------

    def settings(self, environ, start_response):
        """The settings form: the boxes ticked are on, the others off
        (or all as usual)."""
        form = self._form(environ)
        if form is None:
            return self._plain(start_response, '403 Forbidden',
                               tr('Reload the page and try again.'))
        if form.get('usual'):
            usual = Settings()
            wanted = {name: getattr(usual, name) for name in SHOWN}
        else:
            on = set(form.get('on', []))
            wanted = {name: name in on for name in SHOWN}
        for child, parent in DEPENDS.items():
            if not wanted[parent]:
                wanted[child] = False
        self.change({name: value for name, value in wanted.items()
                     if getattr(self.saved, name) != value})
        return self._back(start_response, form, s='1')

    def choose_language(self, environ, start_response):
        """The pull-down of the languages of the meanings."""
        form = self._form(environ)
        if form is None:
            return self._plain(start_response, '403 Forbidden',
                               tr('Reload the page and try again.'))
        code = form.get('language', [''])[0]
        if code in self.session.lexicon.language_names():
            self.change({'language': code})
            if self.session.notice:
                self.message = self.session.notice
        if from_language(form):         # (the search is in the language)
            form['lang'] = [self.session.language.code]
        return self._back(start_response, form)

    def choose_interface(self, environ, start_response):
        """The pull-down of the languages of the interface (the meanings
        follow it, if the dictionary has the language)."""
        form = self._form(environ)
        if form is None:
            return self._plain(start_response, '403 Forbidden',
                               tr('Reload the page and try again.'))
        code = form.get('interface', [''])[0]
        if code in interface.names():
            interface.use(code)
            values = {'interface': code}
            if code in self.session.lexicon.language_names():
                values['language'] = code
            self.change(values)
            if from_language(form):     # (the search is in the language)
                form['lang'] = [self.session.language.code]
        return self._back(start_response, form, s='1')

    def choose_appearance(self, environ, start_response):
        """The "Dark mode" box: ticked, the page is dark, if not, light
        (kept, as the windows' dark mode, in the configuration file)."""
        form = self._form(environ)
        if form is None:
            return self._plain(start_response, '403 Forbidden',
                               tr('Reload the page and try again.'))
        try:
            config.update(APPEARANCE, {'dark_mode': 'dark' in form})
        except (OSError, ConfigError) as e:
            self.message = tr('The settings were not saved: {error}',
                              error=e)
        return self._back(start_response, form)

    def choose_fuzzy(self, environ, start_response):
        """The "Fuzzy search" box (the setting fuzzy_search); the search
        is made again with it."""
        form = self._form(environ)
        if form is None:
            return self._plain(start_response, '403 Forbidden',
                               tr('Reload the page and try again.'))
        fuzzy = 'fuzzy' in form
        if fuzzy != self.saved.fuzzy_search:
            self.change({'fuzzy_search': fuzzy})
        return self._back(start_response, form)

    def change(self, values: dict[str, bool | str]):
        """Changes settings, applies them, and keeps them in the
        configuration file (as the window does)."""
        if not values:
            return
        with self.lock:
            for name, value in values.items():
                setattr(self.saved, name, value)
                setattr(self.session.settings, name, value)
            self.session.settings_changed()     # (language, cache)
            try:
                for section in {section_of(name) for name in values}:
                    self.saved.save(section, only=[
                        n for n in values if section_of(n) == section])
            except (OSError, ConfigError) as e:
                self.message = tr('The settings were not saved: {error}',
                                  error=e)

    def clear_history(self, environ, start_response):
        form = self._form(environ)
        if form is None:
            return self._plain(start_response, '403 Forbidden',
                               tr('Reload the page and try again.'))
        History().clear()
        self.message = tr('The history of the searches is cleared.')
        return self._back(start_response, {'lang': form.get('lang', [''])})


#  The texts of the page, by their places in it ($t_look_up ...), and those
#  of its script (as JavaScript strings)
PAGE_TEXTS = {
    't_tagline': N_('a Latin dictionary'), 't_search': N_('Search'),
    't_look_up': N_('Look up'), 't_meanings_in': N_('Meanings in'),
    't_change': N_('Change'), 't_earlier': N_('Earlier searches'),
    't_clear': N_('Clear history'), 't_settings': N_('Settings'),
    't_apply': N_('Apply'), 't_usual': N_('Usual settings'),
    't_kept': N_('Changes are kept for next time, also for the command '
                 'line and the window.'),
    't_interface': N_('Language of the interface'), 't_about': N_('About'),
    't_dark': N_('Dark mode'), 't_help': N_('Help'),
    't_fuzzy': N_('Fuzzy search'),
}
APPEARANCE = 'appearance'               # (the section of config.toml)

SCRIPT_TEXTS = {
    'j_forget': N_('Forget the earlier searches (also those of the window '
                   'and the command line)?'),
    'j_usual': N_('Go back to the usual value of every setting?'),
}

PAGE = Template("""<!doctype html>
<html lang="$html_lang"$theme>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<link rel="icon" href="/icon.png">
<style>
:root {
  --bg: #fbfaf7; --fg: #1d1d1b; --muted: #6b6a66; --line: #dcd9d2;
  --panel: #f1efe9; --accent: #8a2c1f; --focus: #c0573f;
  --form: #55534d; --analysis: #245a8a;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme=light]) {
    --bg: #1b1b1d; --fg: #e8e6e1; --muted: #9a9890; --line: #3a3a3e;
    --panel: #242428; --accent: #e8957f; --focus: #f0a58f;
    --form: #b8b4aa; --analysis: #8fb8e0;
    color-scheme: dark;
  }
}
:root[data-theme=dark] {
  --bg: #1b1b1d; --fg: #e8e6e1; --muted: #9a9890; --line: #3a3a3e;
  --panel: #242428; --accent: #e8957f; --focus: #f0a58f;
  --form: #b8b4aa; --analysis: #8fb8e0;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
}
.wrap { max-width: 64rem; margin: 0 auto; padding: 1rem; }
header { display: flex; align-items: baseline; gap: .6rem;
  flex-wrap: wrap; }
header h1 { font-size: 1.4rem; margin: 0; }
header h1 a { color: inherit; text-decoration: none; }
header span { color: var(--muted); }
header a.home { margin-left: auto; font-size: .85rem; color: var(--muted);
  text-decoration: none; }
header a.home:hover { color: var(--accent); text-decoration: underline; }
a { color: var(--accent); }
form.search { display: flex; flex-wrap: wrap; gap: .5rem;
  margin: 1rem 0 .5rem; }
form.search input[type=search] {
  flex: 1 1 16rem; min-width: 0; font: inherit; padding: .5rem .7rem;
  color: var(--fg); background: var(--bg);
  border: 1px solid var(--line); border-radius: 6px;
}
button {
  font: inherit; padding: .45rem 1rem; border-radius: 6px;
  border: 1px solid var(--line); background: var(--panel);
  color: var(--fg); cursor: pointer;
}
button.primary { background: var(--accent); color: var(--bg);
  border-color: var(--accent); }
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.lang { display: flex; gap: 1rem; flex-basis: 100%; color: var(--muted); }
form.meanings { color: var(--muted); margin: 0 0 .5rem; }
.row { display: flex; flex-wrap: wrap; gap: 0 1.5rem; align-items: baseline; }
select { font: inherit; color: var(--fg); background: var(--bg);
  border: 1px solid var(--line); border-radius: 6px; padding: .2rem .4rem; }
.message { background: var(--panel); border-left: 3px solid var(--accent);
  padding: .4rem .8rem; }
pre.results {
  font: 14px/1.45 ui-monospace, "DejaVu Sans Mono", Menlo, Consolas,
    monospace;
  white-space: pre-wrap; overflow-wrap: anywhere;
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 6px; padding: .8rem 1rem; margin: .5rem 0 1rem;
}
pre.results a { text-decoration: none; }
pre.results a:hover { text-decoration: underline; }
pre.results .k-word strong { font-size: 1.12em; }
pre.results .k-entry { font-weight: 600; }
pre.results .k-note { color: var(--muted); font-style: italic; }
pre.results .k-detail { color: var(--muted); }
pre.results .k-form { color: var(--form); }
pre.results abbr { text-decoration: none; cursor: help; }
pre.results abbr.codes { color: var(--muted); font-weight: normal; }
pre.results abbr.an { color: var(--analysis); }
#tip { position: absolute; z-index: 10; max-width: 90vw;
  font: 13px/1.4 ui-monospace, "DejaVu Sans Mono", Menlo, Consolas,
    monospace; white-space: pre-wrap; color: var(--fg);
  background: var(--panel); border: 1px solid var(--line);
  border-radius: 6px; padding: .4rem .6rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, .25); }
details { border-top: 1px solid var(--line); padding: .6rem 0; }
summary { cursor: pointer; font-weight: 600; }
.recent { display: flex; flex-wrap: wrap; gap: .3rem .9rem;
  list-style: none; padding: 0; }
.note { color: var(--muted); }
fieldset { border: 1px solid var(--line); border-radius: 6px;
  margin: .8rem 0; }
legend { font-weight: 600; padding: 0 .3rem; }
.setting { display: grid; grid-template-columns: auto 1fr;
  column-gap: .5rem; padding: .25rem 0; cursor: pointer; }
.setting small { grid-column: 2; color: var(--muted); }
.setting.off { opacity: .5; cursor: default; }
.buttons { display: flex; gap: .5rem; flex-wrap: wrap; }
pre.about { color: var(--muted); font-size: .85rem;
  white-space: pre-wrap; }
.guide { max-width: 46rem; }
.guide h3 { font-size: 1.05rem; margin: 1.2rem 0 .3rem; }
.guide pre { font: 13px/1.4 ui-monospace, "DejaVu Sans Mono", Menlo,
  Consolas, monospace; background: var(--panel); overflow-x: auto;
  border: 1px solid var(--line); border-radius: 6px; padding: .5rem .8rem; }
.guide li { margin: .25rem 0; }
</style>
</head>
<body>
<div class="wrap">
<header><h1><a href="/">$name</a></h1>
<span>$version · $t_tagline</span>
<a class="home" href="$home" target="_blank" rel="noopener">$home_name</a>
</header>
<form class="search" method="get" action="/">
<input type="search" name="q" value="$query" placeholder="$placeholder"
  aria-label="$t_search" autofocus autocomplete="off">
<button class="primary">$t_look_up</button>
<div class="lang">
<label><input type="radio" name="lang" value="la"$la_checked>
$to_language</label>
<label><input type="radio" name="lang" value="$code"$en_checked>
$from_language</label>
</div>
</form>
<div class="row">
<form class="meanings" method="post" action="/language">
<input type="hidden" name="token" value="$token">
<input type="hidden" name="q" value="$query">
<input type="hidden" name="lang" value="$lang">
<label>$t_meanings_in <select name="language">$languages</select></label>
<noscript><button>$t_change</button></noscript>
</form>
<form class="meanings" id="fuzzy" method="post" action="/fuzzy">
<input type="hidden" name="token" value="$token">
<input type="hidden" name="q" value="$query">
<input type="hidden" name="lang" value="$lang">
<label><input type="checkbox" name="fuzzy" value="1"$fuzzy_checked>
$t_fuzzy</label>
<noscript><button>$t_change</button></noscript>
</form>
<form class="meanings" id="dark" method="post" action="/appearance">
<input type="hidden" name="token" value="$token">
<input type="hidden" name="q" value="$query">
<input type="hidden" name="lang" value="$lang">
<label><input type="checkbox" name="dark" value="1"$dark_checked>
$t_dark</label>
<noscript><button>$t_change</button></noscript>
</form>
</div>
$message
<pre class="results"$results_attrs>$results</pre>
<div id="tip" hidden></div>
<details open><summary>$t_earlier</summary>
$recent
<form id="clear" method="post" action="/history/clear">
<input type="hidden" name="token" value="$token">
<input type="hidden" name="lang" value="$lang">
<button>$t_clear</button>
</form>
</details>
<details id="settings"$settings_open><summary>$t_settings</summary>
<form class="meanings" method="post" action="/interface">
<input type="hidden" name="token" value="$token">
<input type="hidden" name="q" value="$query">
<input type="hidden" name="lang" value="$lang">
<label>$t_interface <select name="interface">$interfaces</select></label>
<noscript><button>$t_change</button></noscript>
</form>
<form method="post" action="/settings">
<input type="hidden" name="token" value="$token">
<input type="hidden" name="q" value="$query">
<input type="hidden" name="lang" value="$lang">
$settings
<div class="buttons">
<noscript><button class="primary">$t_apply</button></noscript>
<button name="usual" value="1">$t_usual</button>
</div>
<p class="note">$t_kept</p>
</form>
</details>
<details id="help"><summary>$t_help</summary>
<div class="guide">
$help
</div></details>
<details><summary>$t_about</summary>
<pre class="about">$about</pre></details>
</div>
<script nonce="$nonce">
for (const box of document.querySelectorAll('#settings input[name=on]'))
  box.addEventListener('change', () => box.form.submit());
for (const select of document.querySelectorAll('select'))
  select.addEventListener('change', e => e.target.form.submit());
const dark = document.querySelector('#dark input[name=dark]');
if (!document.documentElement.dataset.theme)  // (as the system, till chosen)
  dark.checked = matchMedia('(prefers-color-scheme: dark)').matches;
dark.addEventListener('change', () => dark.form.submit());
const fuzzy = document.querySelector('#fuzzy input[name=fuzzy]');
fuzzy.addEventListener('change', () => fuzzy.form.submit());
for (const radio of document.querySelectorAll('input[name=lang]'))
  radio.addEventListener('change', () => {
    if (radio.form.q.value.trim()) radio.form.submit();
  });
//  The codes and analyses explain themselves: a tooltip (their title), and
//  a box on a tap, for the phones
const results = document.querySelector('pre.results');
const tip = document.getElementById('tip');
results.addEventListener('click', e => {
  const abbr = e.target.closest('abbr[title]');
  if (!abbr) { tip.hidden = true; return; }
  const box = abbr.getBoundingClientRect();
  tip.textContent = abbr.title;
  tip.hidden = false;
  //  (inside the screen, also on a phone)
  const left = Math.min(box.left, innerWidth - tip.offsetWidth - 8);
  tip.style.left = (scrollX + Math.max(8, left)) + 'px';
  tip.style.top = (scrollY + box.bottom + 4) + 'px';
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') tip.hidden = true;
});
//  A double click looks a word up: a form whole (arm-a: arma), a word of
//  the meanings in Latin
results.addEventListener('dblclick', e => {
  const form = e.target.closest('[data-q]');
  const word = form ? form.dataset.q : String(getSelection()).trim();
  if (!/^\\p{L}{2,}$$/u.test(word)) return;  // (\\ and $$: Python)
  const line = e.target.closest('[class^="k-"]');
  const toLatin = !form && !!line &&
    (line.classList.contains('k-meaning') ||
     (line.classList.contains('k-word') && !!results.dataset.toLatin));
  const search = document.querySelector('form.search');
  search.q.value = word;
  for (const radio of search.querySelectorAll('input[name=lang]'))
    radio.checked = (radio.value === 'la') !== toLatin;
  search.requestSubmit();
});
document.getElementById('clear').addEventListener('submit', e => {
  if (!confirm($j_forget)) e.preventDefault();
});
document.querySelector('[name=usual]').addEventListener('click', e => {
  if (!confirm($j_usual)) e.preventDefault();
});
</script>
</body>
</html>
""")


# The server ---------------------------------------------------------------

class Server(ThreadingMixIn, WSGIServer):
    """Answers each request in its own thread (a browser may keep idle
    connections open, which would block a server that answers one at a
    time)."""
    daemon_threads = True


class Server6(Server):
    address_family = socket.AF_INET6


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


def is_loopback(host: str) -> bool:
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def serve(app, host: str, port: int | None) -> WSGIServer:
    """A server for APP on HOST and PORT (None: the usual port, or any
    free one if it is taken)."""
    server_class = Server6 if ':' in host else Server
    try:
        return make_server(host, PORT if port is None else port, app,
                           server_class, QuietHandler)
    except OSError as e:
        if port is not None or e.errno != errno.EADDRINUSE:
            raise
    return make_server(host, 0, app, server_class, QuietHandler)


def address(host: str, port: int) -> str:
    """The address to open for a server on HOST and PORT."""
    if host in ('', '0.0.0.0'):
        host = '127.0.0.1'
    elif host == '::':
        host = '::1'
    if ':' in host:
        host = f'[{host}]'
    return f'http://{host}:{port}/'


def main(argv=None):
    ensure_config()                 # (made at the first start)
    interface.use_configured()
    interface.translate_argparse()
    parser = argparse.ArgumentParser(
        prog='words_web.py', description=tr('The WORDS dictionary in a web '
                                            'browser.'),
        epilog='\n\n'.join(tr(p) for p in __doc__.split('\n\n')[1:]),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', default=HOST, metavar=tr('HOST'),
                        help=tr('the address to listen on (default: {host}, '
                                'only this computer)', host=HOST))
    parser.add_argument('--port', type=int, metavar=tr('PORT'),
                        help=tr('the port (default: {port}, or a free one)',
                                port=PORT))
    parser.add_argument('--no-browser', action='store_true',
                        help=tr('do not open the browser'))
    parser.add_argument('--datadir', metavar=tr('DATADIR'),
                        help=tr('the folder with the data files (default: '
                                'as for words.py)'))
    args = parser.parse_args(argv)
    datadir = args.datadir or default_datadir()
    if not os.path.isfile(os.path.join(datadir, DICTIONARY)):
        sys.exit('words_web.py: ' + tr('there is no {file} in {folder}',
                                       file=DICTIONARY, folder=datadir))
    local = is_loopback(args.host)
    print(tr('Loading the dictionary…'), flush=True)
    try:
        app = WebApp(datadir, {'localhost', '127.0.0.1', '::1'}
                     if local else None)
    except DataError as e:
        sys.exit(f'words_web.py: {e}')
    try:
        server = serve(app, args.host, args.port)
    except OSError as e:
        sys.exit('words_web.py: ' + tr('cannot listen on {host} port '
                                       '{port}: {error}', host=args.host,
                                       port=args.port or PORT,
                                       error=e.strerror or e))
    url = address(args.host, server.server_port)
    print(tr('{name} {version} is at {url}  (Ctrl-C stops it)', name=NAME,
             version=VERSION, url=url))
    if not local:
        print(tr("Other computers can reach it too (at this computer's "
                 "address); there are no passwords."))
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
