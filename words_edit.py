#!/usr/bin/env python3
"""A full-screen terminal editor for the dictionary:
python3 words_edit.py

    Find   type a Latin form, a stem or a word of the meanings and Enter
    List   Up/Down to choose an entry, Enter to edit it
    Form   Up/Down between fields; type in text fields; in a field with
           choices, Left/Right change it and Enter lists them all

    F3 / Ctrl-A  apply the changes (or add the new entry)
    F4 / Ctrl-N  new entry           F5 / Ctrl-D  new entry like this one
    F6 / Ctrl-T  try a word          F8 / Ctrl-K  delete the entry
    F7 / Ctrl-L  the language of the meanings edited besides English
    F2 / Ctrl-S  save the file (applying the changes first)
    F10 / Ctrl-Q quit
    Tab          next area           Ctrl-F       find

Nothing is written until the file is saved; the first save keeps the
original as dictionary.xml.bak (and so for the file of the language of
the meanings, in languages/, if one is chosen).  Leaving an entry whose
changes were not applied asks what to do with them.  (On Windows, curses
needs the windows-curses package; the window editor, words_edit_gui.py,
needs nothing.)
"""

from version import check_python
check_python()          # (before the modules that need it)

import curses
import os
import sys

import interface
from interface import N_, tr, yes
from settings import Settings, ensure_config
from lexicon import default_datadir
from editor import (Editor, Editing, Fields, FIELD_LABELS, POS_CHOICES,
                    CODE_FIELDS)
from lexicon import DICTIONARY
from version import NAME
from tui import ENTER, SEP, Field, Screen, ctrl
from xmldata import DataError

KEYS = {
    'apply': (curses.KEY_F3, ctrl('a')), 'new': (curses.KEY_F4, ctrl('n')),
    'copy': (curses.KEY_F5, ctrl('d')), 'try': (curses.KEY_F6, ctrl('t')),
    'delete': (curses.KEY_F8, ctrl('k')), 'save': (curses.KEY_F2, ctrl('s')),
    'language': (curses.KEY_F7, ctrl('l')),
    'quit': (curses.KEY_F10, ctrl('q'), ctrl('c')), 'find': (ctrl('f'),),
}
HELP = N_('F3 apply  F4 new  F5 like this  F6 try  F7 language  '
          'F8 delete  F2 save  F10 quit  Tab next  ^F find')

#  The help (--help): the docstring after its first paragraph
HELP_TEXT = __doc__.split('\n\n', 1)[1]


class TUI(Screen):
    def __init__(self, screen, datadir, language='en'):
        super().__init__(screen)
        self.editor = Editor(datadir, language)
        self.editing = Editing(self.editor)
        self.query = Field('find', tr('Find'), '')
        self.selected = 0
        self.list_top = 0
        self.focus = 'find'             # 'find', 'list' or 'form'
        self.row = 0                    # the field with the focus
        self.fields = []
        self.message = tr('Type a Latin form, a stem or a word of the '
                          'meanings, and Enter.')
        self.load(self.empty())
        self.editing.start(None, self.form_values())

    @property
    def current(self):
        """The entry in the form, or None for a new one."""
        return self.editing.current

    @property
    def results(self):
        return self.editing.results

    # The form --------------------------------------------------------------

    def empty(self) -> Fields:
        """The values of a new entry."""
        return Fields('N', {'kind': 'X'},
                      translation=self.editor.translation(None))

    def load(self, f: Fields):
        """Fills the form from F."""
        ed = self.editor
        fields = [Field('pos', tr('part of speech'), f.pos,
                        [(v, tr(d)) for v, d in POS_CHOICES])]
        for i, label in enumerate(f.stem_labels()):
            fields.append(Field(f'stem{i}', tr(label), f.stems[i]))
        for name in f.names():
            default = 'X' if name in CODE_FIELDS else ''
            fields.append(Field(name, tr(FIELD_LABELS.get(name, name)),
                                f.attrs.get(name, default),
                                ed.options(name, f.pos)))
        if f.translation is None:
            fields.append(Field('meaning', tr('meaning'), f.meaning))
        else:
            fields.append(Field('meaning', tr('meaning in English'),
                                f.meaning))
            fields.append(Field('translation',
                                tr('meaning in {language}',
                                   language=tr(ed.language_name)),
                                f.translation))
        self.fields = fields
        self.row = min(self.row, len(fields) - 1)

    def form_values(self) -> Fields:
        f = Fields(self.fields[0].value)
        for field in self.fields[1:]:
            if field.key.startswith('stem'):
                f.stems[int(field.key[4:])] = field.value.strip()
            elif field.key == 'meaning':
                f.meaning = field.value
            elif field.key == 'translation':
                f.translation = field.value
            else:
                f.attrs[field.key] = field.value.strip()
        return f

    def pending(self) -> bool:
        """Whether the form has changes that were not applied."""
        return self.editing.pending(self.form_values())

    def leave(self) -> bool:
        """Before the form shows something else: asks what to do with
        changes not applied.  False: stay."""
        def ask(what):
            answer = self.ask(tr('{what} has changes that are not '
                                 'applied.  Apply them? (y/n, Esc to stay)',
                                 what=what[0].upper() + what[1:]))
            return None if answer is None else yes(answer)
        try:
            return self.editing.leave(self.form_values(), ask)
        except DataError as e:
            self.message = tr('Not applied: {error}', error=e.message)
            return False

    def entry(self):
        """The entry in the form, or the error message."""
        try:
            return self.form_values().entry(), None
        except DataError as e:
            return None, e.message

    # Drawing ---------------------------------------------------------------

    def draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        ed = self.editor
        unsaved = '   ' + tr('[unsaved changes]') if ed.dirty else ''
        language = '   ' + tr('meanings in {language}',
                              language=tr(ed.language_name)) \
            if ed.translating else ''
        title = ' ' + tr('{name}: dictionary editor', name=NAME) + \
            f'   {ed.path}{language}{unsaved} '
        self.put(0, 0, title.ljust(w), curses.A_REVERSE)
        find = tr('Find:') + ' '
        self.put(1, 0, find)
        self.put(1, len(find), self.query.value,
                 curses.A_UNDERLINE if self.focus == 'find' else 0)
        left = max(30, w * 2 // 5)
        top, bottom = 3, h - 4
        self.put(2, 0, tr('{n} found', n=len(self.results)) if self.results
                 else '', curses.A_DIM)
        # the list
        rows = bottom - top
        if self.selected < self.list_top:
            self.list_top = self.selected
        elif self.selected >= self.list_top + rows:
            self.list_top = self.selected - rows + 1
        for i, e in enumerate(self.results[self.list_top:
                                           self.list_top + rows]):
            k = i + self.list_top
            attr = curses.A_REVERSE if k == self.selected and \
                self.focus == 'list' else (curses.A_BOLD if e is
                                           self.current else 0)
            self.put(top + i, 0, ed.summary(e, left - 2).ljust(left - 2),
                     attr)
        for y in range(2, bottom):
            self.put(y, left - 1, '│')
        # the form
        x = left + 1
        label_w = max(len(f.label) for f in self.fields) + 2
        self.put(2, x, tr('NEW ENTRY') if self.current is None
                 else tr('ENTRY'),
                 curses.A_BOLD)
        for i, f in enumerate(self.fields):
            y = top + i
            if y >= bottom - 2:
                break
            focused = self.focus == 'form' and i == self.row
            self.put(y, x, f.label, curses.A_BOLD if focused else 0)
            marker = ' ▾' if f.options else ''
            if f.choice:
                text = f.shown() + marker
            else:
                text = f.value[self.scrolled(f, w - x - label_w - 1):]
            self.put(y, x + label_w, text,
                     curses.A_REVERSE if focused and f.choice else
                     curses.A_UNDERLINE if focused else 0)
        entry, error = self.entry()
        y = min(top + len(self.fields) + 1, bottom - 2)
        if entry is not None:
            self.put(y, x, ed.describe(entry), curses.A_BOLD)
            translation = self.form_values().translation
            for k, warning in enumerate(ed.warnings(entry,
                                                    translation)[:2]):
                self.put(y + 1 + k, x, '! ' + warning)
        else:
            self.put(y, x, 'x ' + error, curses.A_BOLD)
        # the message and the keys
        self.put(h - 2, 0, self.message[:w - 1])
        self.put(h - 1, 0, tr(HELP).ljust(w - 1), curses.A_REVERSE)
        # the cursor
        if self.focus == 'find':
            scr.move(1, min(len(find) + self.query.cursor, w - 1))
            curses.curs_set(1)
        elif self.focus == 'form' and not self.fields[self.row].choice and \
                top + self.row < bottom - 2:
            f = self.fields[self.row]
            start = self.scrolled(f, w - x - label_w - 1)
            scr.move(top + self.row,
                     min(x + label_w + f.cursor - start, w - 1))
            curses.curs_set(1)
        else:
            curses.curs_set(0)
        scr.refresh()

    # Actions ---------------------------------------------------------------

    def find(self):
        self.editing.find(self.query.value)
        self.selected = self.list_top = 0
        if self.results:
            self.focus = 'list'
            self.message = tr('Up/Down to choose, Enter to edit.')
        else:
            self.message = tr('Nothing found.')

    def edit(self, entry):
        if entry is not self.current:
            if not self.leave():
                return
            self.load(self.editor.fields(entry))
            self.editing.start(entry, self.form_values())
            self.row = 1
        self.focus = 'form'
        self.message = tr('Editing.  F3 applies the changes (F2 also '
                          'saves).')

    def new(self, like=False, ask=True):
        if not like and ask and not self.leave():
            return
        values = self.form_values() if like else self.empty()
        self.load(values)
        self.editing.start(None, self.form_values())
        self.focus, self.row = 'form', 1
        self.message = tr('New entry.  F3 adds it to the dictionary.')

    def apply(self) -> bool:
        """Puts the form into the dictionary; False if it has an error."""
        try:
            entry, done = self.editing.apply(self.form_values())
        except DataError as e:
            self.message = tr('Not applied: {error}', error=e.message)
            return False
        self.applied(entry, done)
        return True

    def applied(self, entry, done):
        self.selected = 0
        self.message = tr('{done}: {entry}.  F2 saves the file.',
                          done=tr(done),
                          entry=self.editor.summary(entry, 50))

    def delete(self):
        if self.current is None:
            self.message = tr('Choose an entry to delete first.')
            return
        if not self.confirm(tr('Delete {entry}?', entry=self.editor.summary(
                self.current, 50))):
            return
        self.editing.delete()
        self.selected = min(self.selected, max(0, len(self.results) - 1))
        self.new(ask=False)
        self.message = tr('Deleted.  F2 saves the file.')

    def choose_language(self):
        """Edits the meanings in another language besides English (after
        asking about the changes not applied)."""
        names = self.editor.language_names
        codes = list(names)
        k = self.popup(tr('The meanings in'), [f'{tr(names[c])} ({c})'
                                               for c in codes],
                       choose=True, start=codes.index(self.editor.language)
                       if self.editor.language in codes else 0)
        if k is None or codes[k] == self.editor.language:
            return
        if not self.leave():
            return
        try:
            self.editor.set_language(codes[k])
        except (LookupError, DataError) as e:
            self.message = tr('Cannot use that language: {error}', error=e)
            return
        entry = self.current
        self.load(self.editor.fields(entry) if entry is not None
                  else self.empty())
        self.editing.start(entry, self.form_values())
        self.message = tr('The meanings are now edited in English and '
                          '{language}.',
                          language=tr(self.editor.language_name)) \
            if self.editor.translating else \
            tr('The meanings are now edited in English only.')

    def try_word(self):
        word = self.ask(tr('Try the word:'))
        if word and word.strip():
            text = self.editor.try_word(word.strip()) or tr('(nothing)')
            self.popup(tr('WORDS with the dictionary as edited'),
                       text.rstrip('\n').split('\n'))

    def save(self):
        """Applies the form, if it has changes, and saves."""
        try:
            applied = self.editing.save(self.form_values())
        except DataError as e:
            self.message = tr('Not saved: {error}', error=e.message)
            return
        except OSError as e:
            self.message = tr('Cannot save: {error}', error=e)
            return
        if applied:
            self.applied(*applied)
        if self.editor.translating:
            self.message = tr('Saved {path} and the meanings in {language} '
                              '(the originals are kept as .bak files).',
                              path=self.editor.path,
                              language=tr(self.editor.language_name))
        else:
            self.message = tr('Saved {path} (the originals are kept as .bak '
                              'files).', path=self.editor.path)

    def quit(self):
        if not self.leave():
            return False
        if self.editor.dirty:
            answer = self.ask(tr('Save the changes before quitting? (y/n, '
                                 'Esc to stay)'))
            if answer is None:
                return False
            if yes(answer):
                self.save()
        return True

    # Keys ------------------------------------------------------------------

    def handle(self, ch):
        """Acts on a key; returns False to quit."""
        code = ord(ch) if isinstance(ch, str) and len(ch) == 1 else ch
        if code in KEYS['quit']:
            return not self.quit()
        actions = {'apply': self.apply, 'new': self.new,
                   'copy': lambda: self.new(like=True),
                   'try': self.try_word, 'delete': self.delete,
                   'save': self.save, 'language': self.choose_language}
        for name, action in actions.items():
            if code in KEYS[name]:
                action()
                return True
        if code in KEYS['find']:
            self.focus = 'find'
            return True
        if code == 9:                                   # Tab
            self.focus = {'find': 'list' if self.results else 'form',
                          'list': 'form', 'form': 'find'}[self.focus]
            return True
        if code == curses.KEY_BTAB:
            self.focus = {'find': 'form', 'list': 'find',
                          'form': 'list' if self.results else 'find'}[
                              self.focus]
            return True
        getattr(self, 'key_' + self.focus)(ch, code)
        return True

    def key_find(self, ch, code):
        if code in ENTER:
            self.find()
        elif code == curses.KEY_DOWN and self.results:
            self.focus = 'list'
        else:
            self.query.key_press(ch)

    def key_list(self, ch, code):
        n = len(self.results)
        if not n:
            return
        h = self.scr.getmaxyx()[0]
        page = max(1, h - 7)
        if code == curses.KEY_UP:
            if self.selected == 0:
                self.focus = 'find'
            self.selected = max(0, self.selected - 1)
        elif code == curses.KEY_DOWN:
            self.selected = min(n - 1, self.selected + 1)
        elif code == curses.KEY_PPAGE:
            self.selected = max(0, self.selected - page)
        elif code == curses.KEY_NPAGE:
            self.selected = min(n - 1, self.selected + page)
        elif code in ENTER:
            self.edit(self.results[self.selected])
        elif code == curses.KEY_DC:
            entry = self.results[self.selected]
            self.edit(entry)            # (asks about changes not applied)
            if self.current is entry:
                self.delete()

    def key_form(self, ch, code):
        f = self.fields[self.row]
        if code == curses.KEY_UP:
            self.row = max(0, self.row - 1)
        elif code == curses.KEY_DOWN:
            self.row = min(len(self.fields) - 1, self.row + 1)
        elif f.options and code in ENTER:
            values = [v for v, _ in f.options]
            start = values.index(f.value) if f.value in values else 0
            k = self.popup(f.label, [v + SEP + d if d else v
                                     for v, d in f.options],
                           choose=True, start=start)
            if k is not None:
                self.set(f, values[k])
        elif code in ENTER:
            self.row = min(len(self.fields) - 1, self.row + 1)
        elif f.choice and code in (curses.KEY_LEFT, curses.KEY_RIGHT):
            values = [v for v, _ in f.options]
            i = values.index(f.value) if f.value in values else -1
            self.set(f, values[(i + (1 if code == curses.KEY_RIGHT
                                     else -1)) % len(values)])
        elif f.choice and isinstance(ch, str) and ch.isalnum():
            for v, _ in f.options:          # jump to the value typed
                if v.upper().startswith(ch.upper()):
                    self.set(f, v)
                    break
        elif not f.choice:
            f.key_press(ch)

    def set(self, field, value):
        if field.key == 'pos' and value != field.value:
            values = self.form_values()
            values.set_pos(value)
            self.load(values)
        else:
            field.value = value
            field.cursor = len(value)


def run(screen, datadir, language='en'):
    curses.raw()
    curses.use_default_colors()
    screen.keypad(True)
    tui = TUI(screen, datadir, language)
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
    import argparse
    parser = argparse.ArgumentParser(
        prog='words_edit.py', description=tr('Edit the WORDS dictionary in '
                                             'the terminal.'),
        epilog=tr(HELP_TEXT),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--datadir', metavar=tr('DATADIR'),
                        help=tr('the folder with dictionary.xml (default: '
                                'as for words)'))
    parser.add_argument('--language', metavar=tr('CODE'),
                        help=tr('also edit the meanings in this language '
                                '(es ...; default: the language of the '
                                'configuration file, en for English only)'))
    args = parser.parse_args(argv)
    datadir = args.datadir or default_datadir()
    language = args.language
    if language is None:
        settings = Settings()
        settings.load(datadir)
        language = settings.language
    if not os.path.isfile(os.path.join(datadir, DICTIONARY)):
        sys.exit('words_edit.py: ' + tr('there is no {file} in {folder}',
                                        file=DICTIONARY, folder=datadir))
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.exit('words_edit.py: ' + tr('this is a full-screen program; '
                                        'run it in a terminal (or use '
                                        'words_edit_gui.py)'))
    os.environ.setdefault('ESCDELAY', '25')
    curses.wrapper(run, datadir, language)


if __name__ == '__main__':
    main()
