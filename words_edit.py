#!/usr/bin/env python3
"""A full-screen terminal editor for the dictionary:
python3 words_edit.py

    Find   type a Latin form, a stem or an English word and Enter
    List   Up/Down to choose an entry, Enter to edit it
    Form   Up/Down between fields; type in text fields; in a field with
           choices, Left/Right change it and Enter lists them all

    F3 / Ctrl-A  apply the changes (or add the new entry)
    F4 / Ctrl-N  new entry           F5 / Ctrl-D  new entry like this one
    F6 / Ctrl-T  try a word          F8 / Ctrl-K  delete the entry
    F2 / Ctrl-S  save the file       F10 / Ctrl-Q quit
    Tab          next area           Ctrl-F       find

Nothing is written until the file is saved; the first save keeps the
original as dictionary.xml.bak.  (On Windows, curses needs the
windows-curses package; the window editor, words_edit_gui.py, needs nothing.)
"""

import curses
import os
import sys

from lexicon import default_datadir
from editor import Editor, Fields, FIELD_LABELS, POS_CHOICES, CODE_FIELDS
from lexicon import DICTIONARY
from version import NAME
from xmldata import DataError

SEP = ' — '


def ctrl(c):
    return ord(c) & 0x1f


KEYS = {
    'apply': (curses.KEY_F3, ctrl('a')), 'new': (curses.KEY_F4, ctrl('n')),
    'copy': (curses.KEY_F5, ctrl('d')), 'try': (curses.KEY_F6, ctrl('t')),
    'delete': (curses.KEY_F8, ctrl('k')), 'save': (curses.KEY_F2, ctrl('s')),
    'quit': (curses.KEY_F10, ctrl('q'), ctrl('c')), 'find': (ctrl('f'),),
}
HELP = ('F3 apply  F4 new  F5 new like this  F6 try  F8 delete  F2 save  '
        'F10 quit  Tab next  ^F find')
ENTER = (10, 13, curses.KEY_ENTER)
BACKSPACE = (curses.KEY_BACKSPACE, 127, 8)


class Field:
    """A line of the form: a text field, or one with choices."""

    def __init__(self, key, label, value, options=None):
        self.key = key              # 'pos', 'stem0', 'decl', 'meaning' ...
        self.label = label
        self.value = value
        self.options = options or []    # [(value, description)]
        self.cursor = len(value)

    @property
    def choice(self):
        return bool(self.options) and self.key not in ('decl', 'conj')

    def shown(self):
        for v, d in self.options:
            if v == self.value and d:
                return self.value + SEP + d
        return self.value

    def cycle(self, step):
        values = [v for v, _ in self.options]
        i = values.index(self.value) if self.value in values else -1
        self.value = values[(i + step) % len(values)]
        self.cursor = len(self.value)

    def key_press(self, ch):
        """Edits the text; returns whether the key was used."""
        code = ord(ch) if isinstance(ch, str) and len(ch) == 1 else ch
        v, c = self.value, self.cursor
        if code in BACKSPACE:
            if c > 0:
                self.value, self.cursor = v[:c - 1] + v[c:], c - 1
        elif code == curses.KEY_DC:
            self.value = v[:c] + v[c + 1:]
        elif code == curses.KEY_LEFT:
            self.cursor = max(0, c - 1)
        elif code == curses.KEY_RIGHT:
            self.cursor = min(len(v), c + 1)
        elif code == curses.KEY_HOME:
            self.cursor = 0
        elif code == curses.KEY_END:
            self.cursor = len(v)
        elif isinstance(ch, str) and ch.isprintable():
            self.value, self.cursor = v[:c] + ch + v[c:], c + len(ch)
        else:
            return False
        return True


class TUI:
    def __init__(self, screen, datadir):
        self.scr = screen
        self.editor = Editor(datadir)
        self.query = Field('find', 'Find', '')
        self.results = []
        self.selected = 0
        self.list_top = 0
        self.focus = 'find'             # 'find', 'list' or 'form'
        self.row = 0                    # the field with the focus
        self.current = None             # the entry in the form (None: new)
        self.fields = []
        self.message = 'Type a Latin form, a stem or an English word, ' \
            'and Enter.'
        self.load(Fields('N', {'kind': 'X'}))

    # The form --------------------------------------------------------------

    def load(self, f: Fields):
        """Fills the form from F."""
        ed = self.editor
        fields = [Field('pos', 'part of speech', f.pos, POS_CHOICES)]
        for i, label in enumerate(f.stem_labels()):
            fields.append(Field('stem%d' % i, label, f.stems[i]))
        for name in f.names():
            default = 'X' if name in CODE_FIELDS else ''
            fields.append(Field(name, FIELD_LABELS.get(name, name),
                                f.attrs.get(name, default),
                                ed.options(name, f.pos)))
        fields.append(Field('meaning', 'meaning', f.meaning))
        self.fields = fields
        self.row = min(self.row, len(fields) - 1)

    def form_values(self) -> Fields:
        f = Fields(self.fields[0].value)
        for field in self.fields[1:]:
            if field.key.startswith('stem'):
                f.stems[int(field.key[4:])] = field.value.strip()
            elif field.key == 'meaning':
                f.meaning = field.value
            else:
                f.attrs[field.key] = field.value.strip()
        return f

    def entry(self):
        """The entry in the form, or the error message."""
        try:
            return self.form_values().entry(), None
        except DataError as e:
            return None, e.message

    # Drawing ---------------------------------------------------------------

    def put(self, y, x, text, attr=0):
        h, w = self.scr.getmaxyx()
        if 0 <= y < h and x < w:
            try:
                self.scr.addnstr(y, x, text, w - x - (1 if y == h - 1
                                                      else 0), attr)
            except curses.error:
                pass

    def draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        ed = self.editor
        title = ' %s: dictionary editor   %s%s ' % (
            NAME, ed.path, '   [unsaved changes]' if ed.dirty else '')
        self.put(0, 0, title.ljust(w), curses.A_REVERSE)
        self.put(1, 0, 'Find: ')
        self.put(1, 6, self.query.value,
                 curses.A_UNDERLINE if self.focus == 'find' else 0)
        left = max(30, w * 2 // 5)
        top, bottom = 3, h - 4
        self.put(2, 0, '%d found' % len(self.results) if self.results
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
        self.put(2, x, 'NEW ENTRY' if self.current is None else 'ENTRY',
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
            for k, warning in enumerate(ed.warnings(entry)[:2]):
                self.put(y + 1 + k, x, '! ' + warning)
        else:
            self.put(y, x, 'x ' + error, curses.A_BOLD)
        # the message and the keys
        self.put(h - 2, 0, self.message[:w - 1])
        self.put(h - 1, 0, HELP.ljust(w - 1), curses.A_REVERSE)
        # the cursor
        if self.focus == 'find':
            scr.move(1, min(6 + self.query.cursor, w - 1))
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

    @staticmethod
    def scrolled(field, width):
        """Where a text field's visible part starts, so that its cursor is
        on the screen."""
        if width <= 1 or field.cursor < width:
            return 0
        return field.cursor - width + 1

    # Small windows ---------------------------------------------------------

    def popup(self, title, lines, choose=False, start=0):
        """Shows LINES in a box; with CHOOSE, returns the index chosen
        (None if cancelled).  Up/Down/PgUp/PgDn scroll, Esc closes."""
        h, w = self.scr.getmaxyx()
        bw = min(w - 4, max([len(title) + 4] + [len(s) + 4 for s in lines]))
        bh = min(h - 4, len(lines) + 2)
        win = curses.newwin(bh, bw, (h - bh) // 2, (w - bw) // 2)
        win.keypad(True)
        pos, top = start, 0
        while True:
            rows = bh - 2
            if pos < top:
                top = pos
            elif pos >= top + rows:
                top = pos - rows + 1
            win.erase()
            win.box()
            win.addnstr(0, 2, ' %s ' % title, bw - 4)
            for i, line in enumerate(lines[top:top + rows]):
                attr = curses.A_REVERSE if choose and top + i == pos else 0
                try:
                    win.addnstr(1 + i, 2, line, bw - 4, attr)
                except curses.error:
                    pass
            win.refresh()
            ch = win.get_wch()
            if ch in ('\x1b', 27):
                return None
            if ch in ('\n', '\r') or ch in ENTER:
                return pos if choose else None
            if ch == curses.KEY_UP:
                pos = max(0, pos - 1) if choose else max(0, top - 1)
                if not choose:
                    top = pos
            elif ch == curses.KEY_DOWN:
                if choose:
                    pos = min(len(lines) - 1, pos + 1)
                else:
                    top = pos = min(max(0, len(lines) - rows), top + 1)
            elif ch == curses.KEY_PPAGE:
                pos = max(0, pos - rows)
                if not choose:
                    top = pos
            elif ch == curses.KEY_NPAGE:
                pos = min(len(lines) - 1, pos + rows)
                if not choose:
                    top = pos = min(max(0, len(lines) - rows), pos)
            elif not choose:
                return None

    def ask(self, prompt):
        """A line of text from the user (None if cancelled)."""
        h, w = self.scr.getmaxyx()
        field = Field('ask', prompt, '')
        while True:
            self.put(h - 2, 0, (prompt + ' ' + field.value).ljust(w - 1),
                     curses.A_BOLD)
            self.scr.move(h - 2, min(len(prompt) + 1 + field.cursor, w - 1))
            curses.curs_set(1)
            ch = self.scr.get_wch()
            if ch in ('\x1b', 27):
                return None
            if ch in ('\n', '\r') or ch in ENTER:
                return field.value
            field.key_press(ch)

    def confirm(self, question):
        answer = self.ask(question + ' (y/n)')
        return answer is not None and answer.strip().lower().startswith('y')

    # Actions ---------------------------------------------------------------

    def find(self):
        self.results = self.editor.search(self.query.value)
        self.selected = self.list_top = 0
        if self.results:
            self.focus = 'list'
            self.message = 'Up/Down to choose, Enter to edit.'
        else:
            self.message = 'Nothing found.'

    def edit(self, entry):
        self.current = entry
        self.load(Fields.of(entry))
        self.focus, self.row = 'form', 1
        self.message = 'Editing.  F3 applies the changes.'

    def new(self, like=False):
        values = self.form_values() if like else Fields('N', {'kind': 'X'})
        self.current = None
        self.load(values)
        self.focus, self.row = 'form', 1
        self.message = 'New entry.  F3 adds it to the dictionary.'

    def apply(self):
        entry, error = self.entry()
        if entry is None:
            self.message = 'Not applied: ' + error
            return
        if self.current is None:
            self.editor.add(entry)
            done = 'Added'
        else:
            self.editor.replace(self.current, entry)
            done = 'Changed'
        self.results = [entry] + [e for e in self.results
                                  if e is not self.current]
        self.current = entry
        self.selected = 0
        self.message = '%s: %s.  F2 saves the file.' % (
            done, self.editor.summary(entry, 50))

    def delete(self):
        if self.current is None:
            self.message = 'Choose an entry to delete first.'
            return
        if not self.confirm('Delete %s?' % self.editor.summary(
                self.current, 50)):
            return
        self.editor.delete(self.current)
        self.results = [e for e in self.results if e is not self.current]
        self.selected = min(self.selected, max(0, len(self.results) - 1))
        self.new()
        self.message = 'Deleted.  F2 saves the file.'

    def try_word(self):
        word = self.ask('Try the word:')
        if word and word.strip():
            text = self.editor.try_word(word.strip()) or '(nothing)'
            self.popup('WORDS with the dictionary as edited',
                       text.rstrip('\n').split('\n'))

    def save(self):
        try:
            self.editor.save()
            self.message = 'Saved %s (the original is in %s.bak).' % (
                self.editor.path, DICTIONARY)
        except OSError as e:
            self.message = 'Cannot save: %s' % e

    def quit(self):
        if self.editor.dirty:
            answer = self.ask('Save the changes before quitting? '
                              '(y/n, Esc to stay)')
            if answer is None:
                return False
            if answer.strip().lower().startswith('y'):
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
                   'save': self.save}
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
            self.current = self.results[self.selected]
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


def run(screen, datadir):
    curses.raw()
    curses.use_default_colors()
    screen.keypad(True)
    tui = TUI(screen, datadir)
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
    import argparse
    parser = argparse.ArgumentParser(
        prog='words_edit.py', description='Edit the WORDS dictionary in the '
        'terminal.', epilog=__doc__.split('\n\n', 1)[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--datadir', help='the folder with dictionary.xml '
                        '(default: as for words)')
    args = parser.parse_args(argv)
    datadir = args.datadir or default_datadir()
    if not os.path.isfile(os.path.join(datadir, DICTIONARY)):
        sys.exit('words_edit.py: there is no %s in %s' % (DICTIONARY, datadir))
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.exit('words_edit.py: this is a full-screen program; run it in a '
                 'terminal (or use words_edit_gui.py)')
    os.environ.setdefault('ESCDELAY', '25')
    curses.wrapper(run, datadir)


if __name__ == '__main__':
    main()
