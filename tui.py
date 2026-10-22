"""What the full-screen terminal programs (words_tui.py, words_edit.py)
share: keys, a line of text to edit, and a screen with boxes and prompts.
Built on curses (on Windows, it needs the windows-curses package)."""

import curses

from interface import tr, yes

SEP = ' — '                     # between a value and its description


def ctrl(c):
    return ord(c) & 0x1f


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


class Screen:
    """A full-screen program on the curses window SCR: writing, boxes and
    prompts."""

    def __init__(self, screen):
        self.scr = screen

    def put(self, y, x, text, attr=0):
        h, w = self.scr.getmaxyx()
        if 0 <= y < h and x < w:
            try:
                self.scr.addnstr(y, x, text, w - x - (1 if y == h - 1
                                                      else 0), attr)
            except curses.error:
                pass

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
            win.addnstr(0, 2, f' {title} ', bw - 4)
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
        return yes(self.ask(question + ' ' + tr('(y/n)')))
