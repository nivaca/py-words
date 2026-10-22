"""The fonts of the windows, which the user can change.

Ctrl and + or - make all the text larger or smaller, Ctrl and 0 brings
back the usual fonts (Command instead of Ctrl on macOS), and the "Font…"
dialogue chooses the fonts and their sizes.  The choice is kept for next
time in the section [fonts] of the configuration file (see config.py).

Every widget uses a named Tk font, so a change reaches all open windows at
once.  There are three kinds of text:

* the results (and the editor's "try a word" output), in TEXT, which must
  be a fixed-width font, as the forms are laid out in columns;
* the windows' own text (labels, buttons, lists, boxes), in Tk's standard
  fonts (TkDefaultFont ...), whose family and size are changed together;
* the box where words are typed, in ENTRY, a little larger than the rest.
"""

import sys
import tkinter as tk
from tkinter import font, ttk

import config
from interface import tr

#  The usual fixed-width font: the first of these that is installed
MONOSPACE = ('DejaVu Sans Mono', 'Liberation Mono', 'Noto Sans Mono',
             'Menlo', 'Consolas', 'Courier New', 'Courier')
TEXT_SIZE = 11
ENTRY_EXTRA = 2         # the typing box is this many points larger
MIN_SIZE, MAX_SIZE = 6, 40

#  Tk's standard fonts, which ttk widgets, lists and menus use
UI_FONTS = ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont',
            'TkCaptionFont', 'TkSmallCaptionFont', 'TkIconFont',
            'TkTooltipFont')

KEYS = ('text_family', 'text_size', 'ui_family', 'ui_size')


def _size(font_name: str) -> int:
    """The size in points of a named font (Tk gives pixels as negative
    numbers; they are close enough)."""
    return abs(font.nametofont(font_name).actual()['size']) or 10


def _clamp(size: int) -> int:
    return max(MIN_SIZE, min(MAX_SIZE, size))


class Fonts:
    """The fonts of one Tk application.  Use `Fonts.of(widget)`, which
    makes them once."""

    @classmethod
    def of(cls, widget) -> 'Fonts':
        root = widget._root()
        fonts = getattr(root, '_py_words_fonts', None)
        if fonts is None:
            fonts = root._py_words_fonts = cls(root)
        return fonts

    def __init__(self, root):
        self.root = root
        installed = set(font.families(root))
        text_family = next((f for f in MONOSPACE if f in installed),
                           font.nametofont('TkFixedFont').actual()['family'])
        ui_size = _size('TkDefaultFont')
        self.defaults = {
            'text_family': text_family, 'text_size': TEXT_SIZE,
            'ui_family': font.nametofont('TkDefaultFont').actual()['family'],
            'ui_size': ui_size}
        #  how much larger or smaller than TkDefaultFont each standard
        #  font is, which is kept when the size changes
        self.ui_offsets = {name: _size(name) - ui_size for name in UI_FONTS}
        self.values = dict(self.defaults)
        self.values.update(self.load())
        self.text = font.Font(root, name='PyWordsText', exists=False)
        self.entry = font.Font(root, name='PyWordsEntry', exists=False)
        self.bold = font.Font(root, name='PyWordsBold', exists=False,
                              weight='bold')
        self._fixed_families = None
        self.apply()
        mod = 'Command' if sys.platform == 'darwin' else 'Control'
        for keys, step in ((('plus', 'equal', 'KP_Add'), 1),
                           (('minus', 'KP_Subtract'), -1),
                           (('0', 'KP_0'), 0)):
            for key in keys:
                root.bind_all(f'<{mod}-{key}>',
                              lambda e, step=step: self.key(step))

    # Settings -----------------------------------------------------------

    def load(self) -> dict:
        """The saved choices that are still usable."""
        saved = config.section('fonts')
        out = {}
        for key in KEYS:
            value = saved.get(key)
            if key.endswith('size') and isinstance(value, int) and \
                    not isinstance(value, bool):
                out[key] = _clamp(value)
            elif key.endswith('family') and isinstance(value, str) and value:
                out[key] = value
        return out

    def save(self):
        """Keeps the choices that differ from the usual ones."""
        changed = {k: v for k, v in self.values.items()
                   if v != self.defaults[k]}
        if not changed and not config.section('fonts'):
            return                      # (nothing to write, or to remove)
        try:
            config.update('fonts', changed)
        except (OSError, config.ConfigError):
            pass                        # (then they last for this session)

    # Changes --------------------------------------------------------------

    def apply(self):
        v = self.values
        self.text.configure(family=v['text_family'], size=v['text_size'])
        self.entry.configure(family=v['ui_family'],
                             size=_clamp(v['ui_size'] + ENTRY_EXTRA))
        self.bold.configure(family=v['ui_family'],
                            size=_clamp(v['ui_size'] + 1))
        for name, offset in self.ui_offsets.items():
            font.nametofont(name).configure(
                family=v['ui_family'], size=_clamp(v['ui_size'] + offset))
        #  (for the windows that fit themselves to their text)
        self.root.event_generate('<<FontsChanged>>', when='tail')

    def set(self, **values):
        """Changes some of the fonts (the keys of KEYS), and keeps it."""
        for key, value in values.items():
            self.values[key] = _clamp(value) if key.endswith('size') \
                else value
        self.apply()
        self.save()

    def zoom(self, step: int):
        """All the text STEP points larger (or smaller)."""
        self.set(text_size=self.values['text_size'] + step,
                 ui_size=self.values['ui_size'] + step)

    def reset(self):
        self.set(**self.defaults)

    def key(self, step: int):
        if step:
            self.zoom(step)
        else:
            self.reset()
        return 'break'

    def fixed_families(self) -> list[str]:
        """The installed fixed-width fonts (found once: it takes a moment)."""
        if self._fixed_families is None:
            found = set()
            for family in font.families(self.root):
                if family.startswith('@'):      # (Windows: vertical text)
                    continue
                f = font.Font(self.root, family=family, size=10)
                if f.metrics('fixed'):
                    found.add(family)
            found.add(self.values['text_family'])
            self._fixed_families = sorted(found, key=str.casefold)
        return self._fixed_families

    def all_families(self) -> list[str]:
        return sorted({f for f in font.families(self.root)
                       if not f.startswith('@')}, key=str.casefold)

    # The dialogue ---------------------------------------------------------

    def dialog(self, parent):
        """A window to choose the fonts; changes show at once."""
        top = parent.winfo_toplevel()
        top.config(cursor='watch')
        top.update_idletasks()
        fixed = self.fixed_families()
        top.config(cursor='')
        win = tk.Toplevel(parent)
        win.title(tr('Fonts'))
        win.transient(top)
        frame = ttk.Frame(win, padding=14)
        frame.pack(fill='both', expand=True)
        rows = ((tr('Results (fixed-width)'), 'text_family', 'text_size',
                 fixed),
                (tr('Window'), 'ui_family', 'ui_size', self.all_families()))
        variables = {}
        for row, (label, family_key, size_key, families) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w',
                                              padx=(0, 10), pady=4)
            family = tk.StringVar(value=self.values[family_key])
            ttk.Combobox(frame, textvariable=family, values=families,
                         state='readonly', width=28).grid(
                             row=row, column=1, sticky='w', pady=4)
            size = tk.StringVar(value=str(self.values[size_key]))
            ttk.Spinbox(frame, textvariable=size, from_=MIN_SIZE,
                        to=MAX_SIZE, width=4).grid(row=row, column=2,
                                                   sticky='w', padx=(8, 0))
            variables[family_key] = family
            variables[size_key] = size

        sample = tk.Text(frame, height=3, width=44, font=self.text,
                         relief='flat', background=frame.winfo_toplevel()
                         .cget('background'))
        sample.insert('1.0', 'amicus, amici  ' + tr('noun, 2nd declension')
                      + '\n  amic-orum      ' + tr('genitive plural'))
        sample.config(state='disabled')
        sample.grid(row=2, column=0, columnspan=3, sticky='we', pady=(10, 0))
        mod = 'Command' if sys.platform == 'darwin' else 'Ctrl'
        ttk.Label(frame, text=tr('{key} and + or − change all the sizes; '
                                 '{key} and 0 brings back the usual fonts.',
                                 key=mod),
                  style='Muted.TLabel').grid(row=3, column=0, columnspan=3,
                                          sticky='w', pady=(8, 0))

        updating = []

        def changed(*_):
            if updating:
                return
            new = {}
            for key, var in variables.items():
                value = var.get().strip()
                if key.endswith('size'):
                    if not value.isdigit():
                        return
                    new[key] = int(value)
                elif value:
                    new[key] = value
            self.set(**new)

        def refresh():
            """Shows the current values (after a reset or a zoom)."""
            updating.append(1)
            for key, var in variables.items():
                var.set(str(self.values[key]))
            updating.clear()

        for var in variables.values():
            var.trace_add('write', changed)

        buttons = ttk.Frame(frame, padding=(0, 12, 0, 0))
        buttons.grid(row=4, column=0, columnspan=3, sticky='we')
        close = ttk.Button(buttons, text=tr('Close'), command=win.destroy)
        close.pack(side='right')
        ttk.Button(buttons, text=tr('Usual fonts'),
                   command=lambda: (self.reset(), refresh())).pack(
                       side='right', padx=(0, 6))
        win.bind('<Escape>', lambda e: win.destroy())
        close.focus_set()
        win.resizable(False, False)     # (once its contents are in)
        win.refresh = refresh           # (for the tests)
        win.variables = variables
        return win
