#!/usr/bin/env python3
"""The dictionary in the terminal, full screen: python3 words_tui.py

    Type a Latin word or line (or, after F2, a word in the language of
    the meanings) and Enter.

    Up / Down       earlier searches (also of earlier sessions)
    PgUp / PgDn     scroll the results (Ctrl-Up / Ctrl-Down: a line)
    F2 / Ctrl-L     Latin to English (or the language of the meanings),
                    or back
    F3 / Ctrl-O     settings: every parameter and developer mode
    F4 / Ctrl-E     edit the dictionary
    F5 / Ctrl-G     the language of the meanings (with Logeion: its
                    dictionary, or all)
    F6              the language of the interface
    F7              copy all the results
    F8              search in this dictionary or in Logeion
    F9              clear the history of the searches
    F1              this help
    F10 / Ctrl-Q    quit

The results are those of words.py, or with F8 the entries of Logeion
for the lemmas of the words (it needs the internet); the settings, the
configuration file and the history of the searches are shared with it
and the window.  (On
Windows, curses needs the windows-curses package.)
"""

from version import check_python
check_python()          # (before the modules that need it)

import argparse
import curses
import os
import sys
import textwrap

import clipboard
import guide
import interface
import logeion
from config import ConfigError
from helptext import HELP
from history import History
from interface import N_, tr
from lexicon import DICTIONARY, Lexicon, default_datadir
from logeion_render import Style
from logeion_text import char_width, styled_segments
from session import Session
from settings import (COMMAND_LINE, DEPENDS, DEV_MODES, MODES, Settings,
                      ensure_config, first_sentence, label, section_of)
from tui import ENTER, Field, Screen, ctrl
from version import NAME, VERSION, about
from xmldata import DataError

KEYS = {
    'help': (curses.KEY_F1,), 'language': (curses.KEY_F2, ctrl('l')),
    'settings': (curses.KEY_F3, ctrl('o')), 'edit': (curses.KEY_F4,
                                                     ctrl('e')),
    'meanings': (curses.KEY_F5, ctrl('g')), 'interface': (curses.KEY_F6,),
    'clipboard': (curses.KEY_F7,), 'source': (curses.KEY_F8,),
    'clear': (curses.KEY_F9,), 'quit': (curses.KEY_F10, ctrl('q'),
                                        ctrl('c')),
}
BAR = N_('F1 help  F2 direction  F3 settings  F4 edit  F5 meanings  '
         'F6 interface  F7 copy  F8 source  F9 clear  F10 quit')
#  (with Logeion, F5 chooses its dictionary)
BAR_LOGEION = N_('F1 help  F2 direction  F3 settings  F4 edit  '
                 'F5 dictionary  F6 interface  F7 copy  F8 source  '
                 'F9 clear  F10 quit')

#  The help (F1, --help): the second and third paragraphs of the
#  docstring, without their indentation
#  What the screen shows until the first search
WELCOME = N_('Type a Latin word or line and Enter.  F1: help and credits.')

HELP_TEXT = textwrap.dedent('\n\n'.join(__doc__.split('\n\n')[1:3]))

#  Ctrl-Up and Ctrl-Down, which curses has no names for
CTRL_UP = ('kUP5', 'kUP')
CTRL_DOWN = ('kDN5', 'kDN')

#  The curses attributes of the ANSI codes of the entries of Logeion
ATTRIBUTES = {1: curses.A_BOLD, 2: curses.A_DIM, 4: curses.A_UNDERLINE,
              3: getattr(curses, 'A_ITALIC', 0), 36: curses.A_BOLD}


def key_bar(width: int, bar: str = BAR) -> str:
    """The keys of the last line, in WIDTH: when they do not fit, those
    before the last are left out, from the end, but the help (F1, which
    lists them all) and quitting stay."""
    keys = tr(bar).split('  ')
    while len('  '.join(keys)) > width and len(keys) > 2:
        del keys[-2]
    return '  '.join(keys)[:width]


class DictionaryTUI(Screen):
    def __init__(self, screen, datadir):
        super().__init__(screen)
        self.datadir = datadir
        settings = Settings()
        settings.load(datadir)
        #  the settings as saved (kept for the command line), and those
        #  used here, which do not pause: the results scroll instead
        self.saved = settings.copy()
        settings.pause_in_screen_output = False
        self.message = tr('Loading the dictionary…')
        self.draw()
        self.session = Session(Lexicon.load(datadir), settings)
        self.history = History()
        self.back = 0                   # how far back in the history
        self.query = Field('query', '', '')
        self.welcome = True             # (until the first search)
        self.lines: list[str] = [tr(WELCOME)]
        self.top = 0                    # the first line of results shown
        self.message = self.session.notice
        self.source = logeion.saved_source()
        self.dictionary = logeion.saved_dictionary()    # (its code)
        self.logeion = logeion.Logeion()    # (its pages, kept)
        self.words = None               # (the results of Logeion shown)
        self.wrapped: tuple[int, list[str]] = (0, [])

    # Drawing --------------------------------------------------------------

    def draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        session = getattr(self, 'session', None)
        name = tr(session.language.name if session else 'English')
        language = tr('{language} → Latin', language=name) \
            if session and session.reverse else \
            tr('Latin → {language}', language=name)
        if getattr(self, 'source', None) == logeion.LOGEION:
            language = tr('Latin → Logeion') \
                if self.dictionary == logeion.ALL else \
                tr('Latin → {dictionary}',
                   dictionary=logeion.dictionary_name(self.dictionary))
        title = ' ' + tr('{name} {version}: A Latin Dictionary', name=NAME,
                         version=VERSION)
        self.put(0, 0, (title + language.rjust(w - len(title) - 1) + ' ')
                 [:w].ljust(w), curses.A_REVERSE)
        if hasattr(self, 'query'):
            self.put(1, 0, '=> ' + self.query.value[self.offset(w - 4):])
            for i, line in enumerate(self.shown(w)[self.top:
                                                   self.top + self.rows()]):
                if self.words is None:
                    self.put(2 + i, 0, line)
                else:
                    self.put_styled(2 + i, line)
            more = len(self.shown(w)) - self.top - self.rows()
            if more > 0:
                self.put(h - 3, w - 18,
                         (' ' + tr('{n} more', n=more) + ' ↓ ').rjust(16),
                         curses.A_DIM)
        self.put(h - 2, 0, self.message[:w - 1])
        bar = BAR_LOGEION if getattr(self, 'source', None) == \
            logeion.LOGEION else BAR
        self.put(h - 1, 0, key_bar(w - 1, bar).ljust(w - 1),
                 curses.A_REVERSE)
        if hasattr(self, 'query'):
            scr.move(1, min(3 + self.query.cursor - self.offset(w - 4),
                            w - 1))
            curses.curs_set(1)
        scr.refresh()

    def rows(self) -> int:
        return max(1, self.scr.getmaxyx()[0] - 4)

    def offset(self, width: int) -> int:
        """Where the visible part of the search line starts."""
        return max(0, self.query.cursor - width + 1)

    def put_styled(self, y: int, line: str):
        """A LINE of the entries of Logeion, in the attributes of its ANSI
        codes."""
        x = 0
        for piece, codes, _ in styled_segments(line):
            attr = 0
            for code in codes:
                attr |= ATTRIBUTES.get(code, 0)
            self.put(y, x, piece, attr)
            x += sum(char_width(c) for c in piece)

    def shown(self, width: int) -> list[str]:
        """The results, long lines wrapped to WIDTH."""
        if self.words is not None:      # (wrapped as Logeion's are)
            if self.wrapped[0] != width:
                self.wrapped = (width, [line for _, line in logeion.render(
                    self.words, Style(True), width - 1, self.dictionary)])
            return self.wrapped[1]
        out = []
        for line in self.lines:
            if len(line) < width:
                out.append(line)
                continue
            indent = ' ' * (len(line) - len(line.lstrip()) + 2)
            out += textwrap.wrap(line, width - 1,
                                 subsequent_indent=indent) or ['']
        return out

    def scroll(self, step: int):
        w = self.scr.getmaxyx()[1]
        last = max(0, len(self.shown(w)) - self.rows())
        self.top = max(0, min(last, self.top + step))

    # Actions --------------------------------------------------------------

    def lookup(self):
        line = self.query.value.strip()
        if not line:
            return
        self.history.add(line)
        self.back = 0
        self.words = None
        if self.source == logeion.LOGEION:
            self.message = tr('Asking Logeion…')
            self.draw()
            try:
                self.words = self.logeion.look_up(self.session, line)
                self.wrapped = (0, [])
            except Exception as e:      # show it, keep going
                self.lines = [tr('(error: {error})', error=e)]
            self.welcome = False
            self.top = 0
            self.message = ''
            self.query = Field('query', '', '')
            return
        try:
            text = self.session.lookup(line)
        except Exception as e:          # show it, keep going
            text = tr('(error: {error})', error=e)
        self.welcome = False
        self.lines = (text.rstrip('\n') or tr('(no results)')).split('\n')
        self.top = 0
        self.message = ''
        self.query = Field('query', '', '')

    def recall(self, step: int):
        """An earlier (STEP 1) or later (-1) search into the search line."""
        items = self.history.items
        back = max(0, min(len(items), self.back + step))
        if back == self.back:
            return
        if self.back == 0:
            self.draft = self.query.value       # (what was being typed)
        self.back = back
        value = items[-back] if back else getattr(self, 'draft', '')
        self.query = Field('query', '', value)

    def choose_source(self):
        """F8: this dictionary, or Logeion (kept for next time)."""
        self.source = logeion.LOCAL if self.source == logeion.LOGEION \
            else logeion.LOGEION
        if self.source == logeion.LOGEION:
            self.session.reverse = False
        self.message = logeion.save_source(self.source) or (
            tr('Searching in Logeion: the entries of its dictionaries for '
               'the lemmas of the words (it needs the internet).')
            if self.source == logeion.LOGEION else
            tr('Searching in this dictionary.'))

    def language(self):
        if self.source == logeion.LOGEION:
            self.message = tr('Logeion is searched in Latin only (F8: '
                              'this dictionary).')
            return
        self.session.reverse = not self.session.reverse
        name = tr(self.session.language.name)
        self.message = tr('{language} to Latin: type a word in '
                          '{language}.', language=name) \
            if self.session.reverse else \
            tr('Latin to {language}.', language=name)

    def choose_meanings(self):
        """F5: the language of the meanings, or with Logeion its
        dictionary."""
        if self.source == logeion.LOGEION:
            self.choose_dictionary()
        else:
            self.choose_language()

    def choose_dictionary(self):
        """A list of the dictionaries of Logeion; Enter chooses one (kept
        for next time), and the results are shown again with it."""
        codes = list(logeion.DICTIONARIES)
        lines = [f"{'*' if code == self.dictionary else ' '} "
                 f"{logeion.dictionary_name(code)}" for code in codes]
        pos = self.popup(tr('Dictionary (Enter chooses)'), lines,
                         choose=True, start=codes.index(self.dictionary))
        if pos is None or codes[pos] == self.dictionary:
            return
        self.dictionary = codes[pos]
        self.wrapped = (0, [])
        self.top = 0
        self.message = logeion.save_dictionary(self.dictionary) or \
            tr('Logeion: {dictionary}.',
               dictionary=logeion.dictionary_name(self.dictionary))

    def choose_language(self):
        """A list of the languages of the meanings; Enter chooses one."""
        languages = self.session.lexicon.language_names()
        codes = list(languages)
        current = self.session.language.code
        lines = [f"{'*' if code == current else ' '} {tr(name)}  ({code})"
                 for code, name in languages.items()]
        start = codes.index(current) if current in codes else 0
        pos = self.popup(tr('Meanings in (Enter chooses)'), lines,
                         choose=True, start=start)
        if pos is None or codes[pos] == current:
            return
        self.change('language', codes[pos])
        self.message = self.session.notice or \
            tr('The meanings are in {language}.',
               language=tr(self.session.language.name))

    def choose_interface(self):
        """A list of the languages of the interface; Enter chooses one."""
        names = interface.names()
        codes = list(names)
        current = interface.code()
        lines = [f"{'*' if code == current else ' '} {name}  ({code})"
                 for code, name in names.items()]
        pos = self.popup(tr('Interface in (Enter chooses)'), lines,
                         choose=True, start=codes.index(current)
                         if current in codes else 0)
        if pos is None or codes[pos] == current:
            return
        interface.use(codes[pos])
        self.change('interface', codes[pos])
        if codes[pos] in self.session.lexicon.language_names():
            self.change('language', codes[pos])     # (the meanings too)
        if self.welcome:                # (in the language chosen)
            self.lines = [tr(WELCOME)]
        self.message = tr('The interface is in {language}.',
                          language=names[codes[pos]])

    def copy_results(self):
        """All the results, as they are (not wrapped), into the
        clipboard."""
        if self.welcome:
            self.message = tr('There are no results yet.')
            return
        lines = self.lines if self.words is None else \
            logeion.text(self.words,
                         dictionary=self.dictionary).split('\n')
        self.message = tr('The results were copied.') \
            if clipboard.copy('\n'.join(lines) + '\n') else \
            tr('The results were copied, if the terminal lets programs '
               'use the clipboard.')

    def clear_history(self):
        if self.confirm(tr('Forget the earlier searches (also those of the '
                           'window and the command line)?')):
            self.history.clear()
            self.back = 0
            self.message = tr('The history of the searches is cleared.')

    def help(self):
        """The keys, then the help (see guide.py) and the credits."""
        _, w = self.scr.getmaxyx()
        blocks = guide.blocks(self.session, [('pre', tr(HELP_TEXT)),
                                             guide.configuration()])
        text = guide.text(blocks, max(30, min(76, w - 8)))
        self.popup(tr('Help'), text.split('\n') + [''] +
                   about().split('\n'))

    def edit_dictionary(self):
        """The dictionary editor, in this terminal; the dictionary is
        read again after it."""
        import words_edit
        from editor import read_only, read_only_message
        if self.source == logeion.LOGEION:
            self.message = tr('The dictionary editor edits this dictionary, '
                              'not Logeion: F8 goes back to it.')
            return
        if read_only(self.datadir):
            h, w = self.scr.getmaxyx()
            self.popup(tr('Edit dictionary…').rstrip('…'), textwrap.wrap(
                read_only_message(self.datadir), max(30, min(70, w - 8))))
            return
        path = os.path.join(self.datadir, DICTIONARY)
        before = os.path.getmtime(path)
        curses.curs_set(1)
        words_edit.run(self.scr, self.datadir, self.session.language.code)
        if os.path.getmtime(path) != before:
            self.message = tr('Loading the dictionary again…')
            self.draw()
            old = self.session
            self.session = Session(Lexicon.load(self.datadir), old.settings)
            self.session.reverse = old.reverse
            self.message = tr('The dictionary was saved and read again.')

    # Settings -------------------------------------------------------------

    def change(self, name: str, value):
        """Changes a setting, applies it, and keeps it in the
        configuration file (as the window does)."""
        setattr(self.saved, name, value)
        if name not in COMMAND_LINE:
            setattr(self.session.settings, name, value)
        self.session.settings_changed()
        try:
            self.saved.save(section_of(name), only=[name])
        except (OSError, ConfigError) as e:
            self.message = tr('The settings were not saved: {error}',
                              error=e)

    def settings(self):
        """A list of the settings: Space or Enter switches one."""
        names = [n for n in MODES + DEV_MODES if n not in COMMAND_LINE]
        h, w = self.scr.getmaxyx()
        bw, bh = min(w - 2, 100), h - 2
        win = curses.newwin(bh, bw, 1, (w - bw) // 2)
        win.keypad(True)
        pos = top = 0
        while True:
            rows = bh - 5
            top = min(max(top, pos - rows + 1), pos)
            win.erase()
            win.box()
            win.addnstr(0, 2, ' ' + tr('Settings (Space switches, Esc '
                                       'closes)') + ' ', bw - 4)
            for i, name in enumerate(names[top:top + rows]):
                k = top + i
                parent = DEPENDS.get(name)
                off = parent is not None and not getattr(self.saved,
                                                         parent)
                mark = '[x]' if getattr(self.saved, name) else '[ ]'
                kind = '' if name in MODES else '  ' + tr('(developer)')
                attr = curses.A_REVERSE if k == pos else \
                    (curses.A_DIM if off else 0)
                try:
                    win.addnstr(1 + i, 2, f'{mark} {label(name)}{kind}'
                                .ljust(bw - 4), bw - 4, attr)
                except curses.error:
                    pass
            name = names[pos]
            text = textwrap.wrap(first_sentence(tr(HELP.get(name, ''))),
                                 bw - 4)[:3]
            for i, line in enumerate(text):
                try:
                    win.addnstr(bh - 4 + i, 2, line, bw - 4, curses.A_DIM)
                except curses.error:
                    pass
            win.refresh()
            ch = win.get_wch()
            code = ord(ch) if isinstance(ch, str) and len(ch) == 1 else ch
            if ch in ('\x1b', 27) or code in KEYS['settings'] + \
                    KEYS['quit']:
                return
            if code == curses.KEY_UP:
                pos = max(0, pos - 1)
            elif code == curses.KEY_DOWN:
                pos = min(len(names) - 1, pos + 1)
            elif code == curses.KEY_PPAGE:
                pos = max(0, pos - rows)
            elif code == curses.KEY_NPAGE:
                pos = min(len(names) - 1, pos + rows)
            elif ch == ' ' or code in ENTER:
                parent = DEPENDS.get(name)
                if parent is not None and not getattr(self.saved, parent):
                    continue                    # (greyed out)
                value = not getattr(self.saved, name)
                self.change(name, value)
                for child, of in DEPENDS.items():
                    if of == name and not value and \
                            getattr(self.saved, child):
                        self.change(child, False)

    # Keys -----------------------------------------------------------------

    def handle(self, ch) -> bool:
        """Acts on a key; returns False to quit."""
        code = ord(ch) if isinstance(ch, str) and len(ch) == 1 else ch
        if code in KEYS['quit']:
            return False
        actions = {'help': self.help, 'language': self.language,
                   'settings': self.settings, 'edit': self.edit_dictionary,
                   'meanings': self.choose_meanings,
                   'interface': self.choose_interface,
                   'clipboard': self.copy_results,
                   'source': self.choose_source,
                   'clear': self.clear_history}
        for name, action in actions.items():
            if code in KEYS[name]:
                action()
                return True
        if code in ENTER:
            self.lookup()
        elif code == curses.KEY_UP:
            self.recall(1)
        elif code == curses.KEY_DOWN:
            self.recall(-1)
        elif code == curses.KEY_PPAGE:
            self.scroll(-(self.rows() - 1))
        elif code == curses.KEY_NPAGE:
            self.scroll(self.rows() - 1)
        elif isinstance(code, int) and code > 255 and \
                curses.keyname(code).decode() in CTRL_UP:
            self.scroll(-1)
        elif isinstance(code, int) and code > 255 and \
                curses.keyname(code).decode() in CTRL_DOWN:
            self.scroll(1)
        else:
            self.query.key_press(ch)
        return True


def run(screen, datadir):
    curses.raw()
    curses.use_default_colors()
    screen.keypad(True)
    tui = DictionaryTUI(screen, datadir)
    while True:
        tui.draw()
        try:
            ch = screen.get_wch()
        except KeyboardInterrupt:
            ch = ctrl('c')
        if ch == curses.KEY_RESIZE:
            continue
        if not tui.handle(ch):
            return


def main(argv=None):
    ensure_config()                 # (made at the first start)
    interface.use_configured()
    interface.translate_argparse()
    parser = argparse.ArgumentParser(
        prog='words_tui.py', description=tr('The WORDS dictionary in the '
                                            'terminal, full screen.'),
        epilog=tr(HELP_TEXT) + '\n\n' + tr(__doc__.split('\n\n')[3]),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--datadir', metavar=tr('DATADIR'),
                        help=tr('the folder with the data files (default: '
                                'as for words.py)'))
    args = parser.parse_args(argv)
    datadir = args.datadir or default_datadir()
    if not os.path.isfile(os.path.join(datadir, DICTIONARY)):
        sys.exit('words_tui.py: ' + tr('there is no {file} in {folder}',
                                       file=DICTIONARY, folder=datadir))
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.exit('words_tui.py: ' + tr('this is a full-screen program; run '
                                       'it in a terminal (or use '
                                       'words.py)'))
    os.environ.setdefault('ESCDELAY', '25')
    try:
        curses.wrapper(run, datadir)
    except DataError as e:
        sys.exit(f'words_tui.py: {e}')


if __name__ == '__main__':
    main()
