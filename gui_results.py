"""The results in the window: the same text that words.py prints, shown
with some order for the eye, and with things to click.

* Each line is styled by what it is, which the layout of the results
  tells (see render.py): the word looked up (bold, larger), the line of an
  entry (its dictionary form bold, its codes in brackets grey), the
  meaning, the forms (stem-ending and the analysis, in another colour),
  and the notes in parentheses (grey).  With the Pearse codes (a developer
  mode) the layout is another one, and the text is shown as it is.
* The first word of an entry is a link to its own search; a double click
  on any word looks it up (to Latin, if it is a word of the meanings).
* Pointing at the codes ([XXXBO]) or at an analysis (GEN.PL) shows what
  they mean, with the words of the help (guide.py).
* A right click gives Copy, Look up and Find; Ctrl-F opens a bar to find
  a text in the results.

The colours follow the light or dark look (<<ThemeChanged>>), and the
fonts the size chosen (<<FontsChanged>>).
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont, ttk

from interface import tr
from layout import (FORM_LINE, CODES, HEADWORD, WORD,  # noqa: F401
                    analysis_of, kind_of)

#  The colours of what is styled, in the light and dark looks
COLOURS = {
    False: {'headword': '#8a2c1f', 'form': '#55534d', 'analysis': '#245a8a',
            'muted': '#77756e', 'found': '#ffe58a', 'found_now': '#ffb84d',
            'tip': '#ffffe8', 'tip_fg': '#1d1d1b'},
    True: {'headword': '#e8957f', 'form': '#b8b4aa', 'analysis': '#8fb8e0',
           'muted': '#9a9890', 'found': '#5c4d16', 'found_now': '#8a5f10',
           'tip': '#34343a', 'tip_fg': '#e8e6e1'},
}


class Results(ttk.Frame):
    """The results, with their scroll bar and the find bar.  ON_LOOKUP
    (query, to_latin) looks a word up; EXPLAIN_CODES and EXPLAIN_ANALYSIS
    give the text of the tooltips ('' for none)."""

    def __init__(self, parent, fonts, theme, on_lookup,
                 explain_codes=lambda codes: '',
                 explain_analysis=lambda analysis: ''):
        super().__init__(parent)
        self.fonts, self.theme = fonts, theme
        self.on_lookup = on_lookup
        self.explain_codes = explain_codes
        self.explain_analysis = explain_analysis
        self.links: dict[str, tuple[str, bool]] = {}
        self.to_latin_words = False     # (the words looked up are not Latin)
        self.tip = None
        self.tip_after = None
        self.matches: list[str] = []
        self.match = -1

        box = ttk.Frame(self)
        box.pack(fill='both', expand=True)
        self.text = tk.Text(box, wrap='word', font=fonts.text, padx=14,
                            pady=10, state='disabled', borderwidth=0,
                            highlightthickness=1, spacing1=1, spacing2=2,
                            spacing3=1)
        bar = ttk.Scrollbar(box, command=self.text.yview)
        self.text.config(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y', padx=(2, 0))
        self.text.pack(side='left', fill='both', expand=True)
        self.find_bar = self._find_bar()

        self.word_font = tkfont.Font(self)
        self.bold_font = tkfont.Font(self)
        self.note_font = tkfont.Font(self)
        self.restyle()
        top = self.winfo_toplevel()
        for event in ('<<ThemeChanged>>', '<<FontsChanged>>'):
            top.bind(event, lambda e: self.restyle(), add='+')

        t = self.text
        t.tag_bind('link', '<Enter>', lambda e: t.config(cursor='hand2'))
        t.tag_bind('link', '<Leave>', lambda e: t.config(cursor=''))
        t.tag_bind('link', '<ButtonRelease-1>', self._follow)
        for tag in ('codes', 'analysis'):
            t.tag_bind(tag, '<Enter>', lambda e, tag=tag: self._tip_later(
                e, tag))
            t.tag_bind(tag, '<Leave>', lambda e: self._tip_hide())
        t.bind('<Double-Button-1>', self._double_click)
        menu_button = '<Button-2>' if sys.platform == 'darwin' \
            else '<Button-3>'
        t.bind(menu_button, self._menu)
        t.bind('<Control-f>', lambda e: self.show_find())

    # Styles ----------------------------------------------------------------

    def restyle(self):
        """The fonts and colours of the styled parts (after a change of the
        look or of the fonts)."""
        base = tkfont.Font(font=self.fonts.text).actual()
        family, size = base['family'], base['size']
        self.word_font.config(family=family, size=size + 2, weight='bold')
        self.bold_font.config(family=family, size=size, weight='bold')
        self.note_font.config(family=family, size=size, slant='italic')
        c = COLOURS[self.theme.dark]
        t = self.text
        t.tag_config('word', font=self.word_font, spacing1=8, spacing3=3)
        t.tag_config('entry', font=self.bold_font)
        t.tag_config('headword', foreground=c['headword'])
        t.tag_config('codes', foreground=c['muted'], font=self.fonts.text)
        t.tag_config('note', foreground=c['muted'], font=self.note_font)
        t.tag_config('detail', foreground=c['muted'])
        t.tag_config('form', foreground=c['form'])
        t.tag_config('analysis', foreground=c['analysis'])
        t.tag_config('link', underline=False)
        t.tag_config('found', background=c['found'])
        t.tag_config('found_now', background=c['found_now'])
        t.tag_raise('found_now')
        if self.tip is not None:
            self._tip_hide()

    # Showing ---------------------------------------------------------------

    def _start(self):
        t = self.text
        t.config(state='normal')
        t.delete('1.0', 'end')
        for tag in self.links:
            t.tag_delete(tag)
        self.links = {}
        self._clear_found()

    def _end(self):
        self.text.config(state='disabled')
        self.text.yview_moveto(0)
        if self.find_bar.winfo_ismapped() and self.find_entry.get():
            self._search()

    def show_plain(self, text: str):
        """TEXT as it is (a message, or results in another layout)."""
        self._start()
        self.text.insert('1.0', text)
        self._end()

    def show(self, text: str, to_latin: bool = False, styled: bool = True):
        """The results TEXT; TO_LATIN: they are of a search to Latin (the
        words looked up are not Latin)."""
        if not styled:
            self.show_plain(text)
            return
        self.to_latin_words = to_latin
        self._start()
        for line in text.split('\n'):
            self._line(line)
        self.text.delete('end-1c')              # (the last newline)
        self._end()

    def _line(self, line: str):
        t = self.text
        kind = kind_of(line)
        start = t.index('end-1c')
        t.insert('end', line + '\n', kind)
        if kind == 'entry':
            m = HEADWORD.match(line)
            if m:
                self._link(start, m.start(1), m.end(1), m.group(1), False)
                t.tag_add('headword', f'{start}+{m.start(1)}c',
                          f'{start}+{m.end(1)}c')
            for m in CODES.finditer(line):
                t.tag_add('codes', f'{start}+{m.start()}c',
                          f'{start}+{m.end()}c')
        elif kind == 'form':
            m = FORM_LINE.fullmatch(line)
            analysis = analysis_of(m.group(4))
            if analysis:
                at = m.start(4)
                t.tag_add('analysis', f'{start}+{at}c',
                          f'{start}+{at + len(analysis)}c')

    def _link(self, line_start: str, begin: int, end: int, query: str,
              to_latin: bool):
        tag = f'link{len(self.links)}'
        self.links[tag] = (query, to_latin)
        self.text.tag_add('link', f'{line_start}+{begin}c',
                          f'{line_start}+{end}c')
        self.text.tag_add(tag, f'{line_start}+{begin}c',
                          f'{line_start}+{end}c')

    def show_welcome(self, text: str, examples: list[tuple[str, str, bool]]):
        """The text shown before the first search, with EXAMPLES to click:
        (label, query, to Latin)."""
        self._start()
        t = self.text
        t.insert('end', text + '\n\n' + tr('Try, for example:') + '  ')
        for i, (label, query, to_latin) in enumerate(examples):
            if i:
                t.insert('end', '  ·  ')
            line_start = t.index('end-1c linestart')
            column = int(t.index('end-1c').split('.')[1])
            t.insert('end', label)
            self._link(line_start, column, column + len(label), query,
                       to_latin)
            t.tag_add('headword', f'{line_start}+{column}c',
                      f'{line_start}+{column + len(label)}c')
        self._end()

    # Clicking --------------------------------------------------------------

    def _follow(self, event):
        if self.text.tag_ranges('sel'):         # (a selection, not a click)
            return
        for tag in self.text.tag_names('current'):
            if tag in self.links:
                self.on_lookup(*self.links[tag])
                return 'break'

    def _word_at(self, index: str) -> tuple[str, bool] | None:
        """(the word at INDEX, whether to look it up to Latin), or None."""
        t = self.text
        line = t.get(f'{index} linestart', f'{index} lineend')
        kind = kind_of(line)
        if kind == 'form':
            #  (the whole form, not a piece of stem-ending: arm-a is arma)
            m = FORM_LINE.fullmatch(line)
            column = int(t.index(index).split('.')[1])
            if m.start(2) <= column < m.end(2):
                return m.group(2).replace('-', ''), False
        word = t.get(f'{index} wordstart', f'{index} wordend')
        if not WORD.fullmatch(word) or len(word) < 2:
            return None
        to_latin = kind == 'meaning' or (kind == 'word' and
                                         self.to_latin_words)
        return word, to_latin

    def _double_click(self, event):
        found = self._word_at(f'@{event.x},{event.y}')
        if found:
            self.on_lookup(*found)
            return 'break'

    def _menu(self, event):
        t = self.text
        menu = tk.Menu(t, tearoff=False)
        has_selection = bool(t.tag_ranges('sel'))
        menu.add_command(label=tr('Copy'),
                         state='normal' if has_selection else 'disabled',
                         command=lambda: t.event_generate('<<Copy>>'))
        found = self._word_at(f'@{event.x},{event.y}')
        if found:
            word, to_latin = found
            label = tr('Find “{word}” in Latin', word=word) if to_latin \
                else tr('Look up “{word}”', word=word)
            menu.add_command(label=label,
                             command=lambda: self.on_lookup(word, to_latin))
        menu.add_command(label=tr('Select all'),
                         command=lambda: t.tag_add('sel', '1.0', 'end'))
        menu.add_separator()
        menu.add_command(label=tr('Find in results…'),
                         accelerator='Ctrl+F', command=self.show_find)
        menu.tk_popup(event.x_root, event.y_root)
        return 'break'

    # Tooltips --------------------------------------------------------------

    def _tip_later(self, event, tag: str):
        self._tip_hide()
        index = self.text.index(f'@{event.x},{event.y}')
        self.tip_after = self.after(
            350, lambda: self._tip_show(tag, index, event.x_root,
                                        event.y_root))

    def _tip_show(self, tag: str, index: str, x: int, y: int):
        self.tip_after = None
        ranges = self.text.tag_prevrange(tag, f'{index}+1c')
        if not ranges:
            return
        shown = self.text.get(*ranges)
        if tag == 'codes':
            text = self.explain_codes(shown.strip('[]'))
        else:
            text = self.explain_analysis(shown)
        if not text:
            return
        c = COLOURS[self.theme.dark]
        tip = self.tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        tk.Label(tip, text=text, justify='left', background=c['tip'],
                 foreground=c['tip_fg'], font=self.fonts.text, padx=8,
                 pady=4, borderwidth=1, relief='solid').pack()
        tip.wm_geometry(f'+{x + 12}+{y + 16}')

    def _tip_hide(self):
        if self.tip_after is not None:
            self.after_cancel(self.tip_after)
            self.tip_after = None
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None

    # Finding ---------------------------------------------------------------

    def _find_bar(self) -> ttk.Frame:
        bar = ttk.Frame(self, padding=(0, 4, 0, 0))
        ttk.Label(bar, text=tr('Find:')).pack(side='left')
        self.find_entry = ttk.Entry(bar, width=24)
        self.find_entry.pack(side='left', padx=(4, 6))
        ttk.Button(bar, text=tr('Previous'),
                   command=lambda: self._step(-1)).pack(side='left')
        ttk.Button(bar, text=tr('Next'),
                   command=lambda: self._step(1)).pack(side='left',
                                                       padx=(4, 0))
        self.find_count = ttk.Label(bar, style='Muted.TLabel')
        self.find_count.pack(side='left', padx=8)
        ttk.Button(bar, text=tr('Close'),
                   command=self.hide_find).pack(side='right')
        e = self.find_entry
        e.bind('<KeyRelease>', self._typed)
        e.bind('<Return>', lambda ev: self._step(1))
        e.bind('<Shift-Return>', lambda ev: self._step(-1))
        e.bind('<Escape>', lambda ev: self.hide_find())
        return bar

    def show_find(self):
        if not self.find_bar.winfo_ismapped():
            self.find_bar.pack(fill='x')
        self.find_entry.focus_set()
        self.find_entry.select_range(0, 'end')
        return 'break'

    def hide_find(self):
        self.find_bar.pack_forget()
        self._clear_found()
        self.find_count.config(text='')
        self.text.focus_set()

    def _clear_found(self):
        self.text.tag_remove('found', '1.0', 'end')
        self.text.tag_remove('found_now', '1.0', 'end')
        self.matches, self.match = [], -1

    def _typed(self, event):
        if event.keysym not in ('Return', 'Escape', 'Shift_L', 'Shift_R'):
            self._search()

    def _search(self):
        """Marks every place where the text of the find bar is."""
        self._clear_found()
        wanted = self.find_entry.get()
        if not wanted:
            self.find_count.config(text='')
            return
        t = self.text
        count = tk.IntVar()
        index = '1.0'
        while True:
            index = t.search(wanted, index, 'end', nocase=True, count=count)
            if not index or not count.get():
                break
            end = f'{index}+{count.get()}c'
            t.tag_add('found', index, end)
            self.matches.append(index)
            index = end
        if self.matches:
            self.find_count.config(text=tr('{count} found',
                                           count=len(self.matches)))
            self._step(1)
        else:
            self.find_count.config(text=tr('Not found'))

    def _step(self, step: int):
        if not self.matches:
            return 'break'
        self.match = (self.match + step) % len(self.matches)
        index = self.matches[self.match]
        t = self.text
        t.tag_remove('found_now', '1.0', 'end')
        end = t.index(f'{index}+{len(self.find_entry.get())}c')
        t.tag_add('found_now', index, end)
        t.see(index)
        return 'break'
