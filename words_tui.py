#!/usr/bin/env python3
"""The dictionary in the terminal, full screen: python3 words_tui.py

    Type a Latin word or line (or an English word, after F2) and Enter.

    Up / Down       earlier searches (also of earlier sessions)
    PgUp / PgDn     scroll the results (Ctrl-Up / Ctrl-Down: a line)
    F2 / Ctrl-L     Latin to English, or English to Latin
    F3 / Ctrl-O     settings: every parameter and developer mode
    F4 / Ctrl-E     edit the dictionary
    F9              clear the history of the searches
    F1              this help
    F10 / Ctrl-Q    quit

The results are those of words.py; the settings, the configuration file
and the history of the searches are shared with it and the window.  (On
Windows, curses needs the windows-curses package.)
"""

from version import check_python
check_python()          # (before the modules that need it)

import argparse
import curses
import os
import sys
import textwrap

from config import ConfigError
from helptext import HELP
from history import History
from lexicon import DICTIONARY, Lexicon, default_datadir
from session import Session
from settings import (COMMAND_LINE, DEPENDS, DEV_MODES, MODES, Settings,
                      ensure_config, first_sentence, label)
from tui import ENTER, Field, Screen, ctrl
from version import CREDITS, NAME, VERSION
from xmldata import DataError

KEYS = {
    'help': (curses.KEY_F1,), 'language': (curses.KEY_F2, ctrl('l')),
    'settings': (curses.KEY_F3, ctrl('o')), 'edit': (curses.KEY_F4,
                                                     ctrl('e')),
    'clear': (curses.KEY_F9,), 'quit': (curses.KEY_F10, ctrl('q'),
                                        ctrl('c')),
}
BAR = ('F1 help  F2 language  F3 settings  F4 edit dictionary  '
       'F9 clear history  F10 quit')

#  Ctrl-Up and Ctrl-Down, which curses has no names for
CTRL_UP = ('kUP5', 'kUP')
CTRL_DOWN = ('kDN5', 'kDN')


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
        self.message = 'Loading the dictionary…'
        self.draw()
        self.session = Session(Lexicon.load(datadir), settings)
        self.history = History()
        self.back = 0                   # how far back in the history
        self.query = Field('query', '', '')
        self.lines: list[str] = CREDITS.split('\n') + [
            '', 'Type a Latin word or line and Enter.  F1: help.']
        self.top = 0                    # the first line of results shown
        self.message = ''

    # Drawing --------------------------------------------------------------

    def draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        language = 'English → Latin' if getattr(
            self, 'session', None) and self.session.english \
            else 'Latin → English'
        title = f' {NAME} {VERSION}: a Latin dictionary'
        self.put(0, 0, (title + language.rjust(w - len(title) - 1) + ' ')
                 [:w].ljust(w), curses.A_REVERSE)
        if hasattr(self, 'query'):
            self.put(1, 0, '=> ' + self.query.value[self.offset(w - 4):])
            for i, line in enumerate(self.shown(w)[self.top:
                                                   self.top + self.rows()]):
                self.put(2 + i, 0, line)
            more = len(self.shown(w)) - self.top - self.rows()
            if more > 0:
                self.put(h - 3, w - 18, f' {more} more ↓ '.rjust(16),
                         curses.A_DIM)
        self.put(h - 2, 0, self.message[:w - 1])
        self.put(h - 1, 0, BAR[:w - 1].ljust(w - 1), curses.A_REVERSE)
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

    def shown(self, width: int) -> list[str]:
        """The results, long lines wrapped to WIDTH."""
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
        try:
            text = self.session.lookup(line)
        except Exception as e:          # show it, keep going
            text = f'(error: {e})'
        self.lines = (text.rstrip('\n') or '(no results)').split('\n')
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

    def language(self):
        self.session.english = not self.session.english
        self.message = 'English to Latin: type an English word.' \
            if self.session.english else 'Latin to English.'

    def clear_history(self):
        if self.confirm('Forget the earlier searches (also those of the '
                        'window and the command line)?'):
            self.history.clear()
            self.back = 0
            self.message = 'The history of the searches is cleared.'

    def help(self):
        text = __doc__.split('\n\n')[1].split('\n')
        self.popup('Help', [line.strip() for line in text if line.strip()])

    def edit_dictionary(self):
        """The dictionary editor, in this terminal; the dictionary is
        read again after it."""
        import words_edit
        path = os.path.join(self.datadir, DICTIONARY)
        before = os.path.getmtime(path)
        curses.curs_set(1)
        words_edit.run(self.scr, self.datadir)
        if os.path.getmtime(path) != before:
            self.message = 'Loading the dictionary again…'
            self.draw()
            old = self.session
            old.close()
            self.session = Session(Lexicon.load(self.datadir), old.settings)
            self.session.english = old.english
            self.message = 'The dictionary was saved and read again.'

    # Settings -------------------------------------------------------------

    def change(self, name: str, value):
        """Changes a setting, applies it, and keeps it in the
        configuration file (as the window does)."""
        setattr(self.saved, name, value)
        if name not in COMMAND_LINE:
            setattr(self.session.settings, name, value)
        self.session.settings_changed()
        try:
            self.saved.save('parameters' if name in MODES else 'developer')
        except (OSError, ConfigError) as e:
            self.message = f'The settings were not saved: {e}'

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
            win.addnstr(0, 2, ' Settings (Space switches, Esc closes) ',
                        bw - 4)
            for i, name in enumerate(names[top:top + rows]):
                k = top + i
                parent = DEPENDS.get(name)
                off = parent is not None and not getattr(self.saved,
                                                         parent)
                mark = '[x]' if getattr(self.saved, name) else '[ ]'
                kind = '' if name in MODES else '  (developer)'
                attr = curses.A_REVERSE if k == pos else \
                    (curses.A_DIM if off else 0)
                try:
                    win.addnstr(1 + i, 2, f'{mark} {label(name)}{kind}'
                                .ljust(bw - 4), bw - 4, attr)
                except curses.error:
                    pass
            name = names[pos]
            text = textwrap.wrap(first_sentence(HELP.get(name, '')),
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
    try:
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
    finally:
        tui.session.close()


def main(argv=None):
    ensure_config()                 # (made at the first start)
    parser = argparse.ArgumentParser(
        prog='words_tui.py', description='The WORDS dictionary in the '
        'terminal, full screen.', epilog=__doc__.split('\n\n', 1)[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--datadir', help='the folder with the data files '
                        '(default: as for words.py)')
    args = parser.parse_args(argv)
    datadir = args.datadir or default_datadir()
    if not os.path.isfile(os.path.join(datadir, DICTIONARY)):
        sys.exit(f'words_tui.py: there is no {DICTIONARY} in {datadir}')
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.exit('words_tui.py: this is a full-screen program; run it in a '
                 'terminal (or use words.py)')
    os.environ.setdefault('ESCDELAY', '25')
    try:
        curses.wrapper(run, datadir)
    except DataError as e:
        sys.exit(f'words_tui.py: {e}')


if __name__ == '__main__':
    main()
