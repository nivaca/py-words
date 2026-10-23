"""The Settings dialogue of the window: every parameter (the # dialogue of
the command line) and developer mode (!), with what each one does.

Changes apply at once and are kept in the configuration file, as those of
the # and ! dialogues are when saved.  A setting that only makes sense
with another (trim_medieval needs trim_output ...) is greyed out while
that one is off, as the command line skips it.  The pause and
the command characters only matter in the interactive command line; they
are offered under their own heading.  At the top are the language of the
interface and the fonts of the windows.
"""

import tkinter as tk
from tkinter import messagebox, ttk

import interface
from helptext import HELP
from interface import tr
from settings import (CHARACTERS, COMMAND_LINE, DEPENDS, DEV_MODES, GROUPS,
                      MODES, ON_SCREEN, Settings, first_sentence,
                      is_command_character, label)

class SettingsDialog:
    """GET(name) gives a setting's value and CHANGE(name, value) changes
    it (the window applies and saves it)."""

    def __init__(self, parent, get, change, name='py-words',
                 clear_history=None, fonts=None):
        """CLEAR_HISTORY, if given, forgets the earlier searches; FONTS,
        if given, opens the fonts dialogue (FONTS(parent))."""
        self.get = get
        self.change = change
        self.name = name
        self.vars: dict[str, tk.Variable] = {}
        self.boxes: dict[str, ttk.Checkbutton] = {}
        self.win = win = tk.Toplevel(parent)
        win.title(tr('{name}: settings', name=name))
        win.transient(parent.winfo_toplevel())
        win.geometry('720x620')

        self.interface_row(win, fonts)
        notebook = ttk.Notebook(win)
        notebook.pack(fill='both', expand=True, padx=8, pady=(8, 0))
        notes = (tr('Parameters (# in the command line).'),
                 tr('Parameters (# in the command line).'),
                 tr('The developer modes (! in the command line), for '
                    'special purposes.'))
        for (title, names), note in zip(GROUPS, notes):
            title = tr(title)
            outer, frame = self.scrolled(notebook)
            notebook.add(outer, text=title)
            ttk.Label(frame, text=note, style='Muted.TLabel').pack(
                anchor='w', pady=(0, 6))
            for name in names:
                if name not in COMMAND_LINE + ON_SCREEN:
                    self.row(frame, name)
            if names is DEV_MODES:
                self.command_line(frame)

        self.help = ttk.Label(win, wraplength=690, justify='left',
                              padding=(10, 6),
                              text=tr('Point at a setting to read more '
                                      'about it.  Changes apply at once and '
                                      'are kept for next time.'))
        self.help.pack(fill='x')
        buttons = ttk.Frame(win, padding=(8, 0, 8, 8))
        buttons.pack(fill='x')
        close = ttk.Button(buttons, text=tr('Close'), command=win.destroy)
        close.pack(side='right')
        ttk.Button(buttons, text=tr('Default settings'),
                   command=self.usual).pack(side='right', padx=(0, 6))
        if clear_history:
            def clear():
                if messagebox.askyesno(
                        self.name, tr('Forget the earlier searches (in the '
                                      'window and the command line)?'),
                        parent=self.win):
                    clear_history()
            ttk.Button(buttons, text=tr('Clear history'),
                       command=clear).pack(side='left')
        win.bind('<Escape>', lambda e: win.destroy())
        close.focus_set()
        self.refresh()

    # Building -------------------------------------------------------------

    def interface_row(self, win, fonts=None):
        """The language of the interface (the window is built again in
        it), and the button of the fonts dialogue."""
        names = interface.names()
        codes = {name: code for code, name in names.items()}
        row = ttk.Frame(win, padding=(10, 8, 10, 0))
        row.pack(fill='x')
        ttk.Label(row, text=tr('Language of the interface:')).pack(
            side='left')
        box = ttk.Combobox(row, state='readonly', width=12,
                           values=list(codes))
        box.set(names.get(self.get('interface'), names['en']))
        box.pack(side='left', padx=6)

        def chosen(event):
            code = codes.get(box.get())
            if code and code != self.get('interface'):
                self.change('interface', code)
        box.bind('<<ComboboxSelected>>', chosen)
        if fonts is not None:
            ttk.Button(row, text=tr('Font…'),
                       command=lambda: fonts(win)).pack(side='right')
        box.bind('<Enter>', lambda e: self.help.config(
            text=tr(HELP['interface'])))
        self.interface_box = box

    def scrolled(self, parent) -> tuple[ttk.Frame, ttk.Frame]:
        """A scrolling area (for the long lists), and the frame in it."""
        outer = ttk.Frame(parent)
        canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0)
        bar = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        inner = ttk.Frame(canvas, padding=(10, 10))
        window = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(
            scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(
            window, width=e.width))

        def wheel(event):
            step = -1 if (event.num == 4 or event.delta > 0) else 1
            canvas.yview_scroll(step, 'units')
        for widget in (canvas, inner):
            widget.bind('<Enter>', lambda e: (
                canvas.bind_all('<MouseWheel>', wheel),
                canvas.bind_all('<Button-4>', wheel),
                canvas.bind_all('<Button-5>', wheel)))
        canvas.bind('<Leave>', lambda e: (
            canvas.unbind_all('<MouseWheel>'),
            canvas.unbind_all('<Button-4>'),
            canvas.unbind_all('<Button-5>')))
        return outer, inner

    def row(self, parent, name: str):
        """A checkbox for setting NAME, with what it does."""
        var = tk.BooleanVar(value=self.get(name))
        box = ttk.Checkbutton(parent, text=label(name), variable=var,
                              command=lambda: self.toggled(name))
        box.pack(anchor='w')
        text = ttk.Label(parent, text=first_sentence(tr(HELP.get(name, ''))),
                         style='Muted.TLabel', wraplength=620,
                         justify='left')
        text.pack(anchor='w', padx=(24, 0), pady=(0, 6))
        for widget in (box, text):
            widget.bind('<Enter>', lambda e: self.help.config(
                text=tr(HELP.get(name, ''))))
        self.vars[name] = var
        self.boxes[name] = box

    def command_line(self, parent):
        """The settings that only the interactive command line uses."""
        ttk.Separator(parent).pack(fill='x', pady=8)
        ttk.Label(parent, text=tr('Only in the interactive command line'),
                  font='TkHeadingFont').pack(anchor='w', pady=(0, 6))
        for name in COMMAND_LINE:
            self.row(parent, name)
        grid = ttk.Frame(parent)
        grid.pack(anchor='w', pady=(4, 0))
        for i, (_, name) in enumerate(CHARACTERS):
            ttk.Label(grid, text=label(name)).grid(row=i, column=0,
                                                   sticky='w', pady=2)
            var = tk.StringVar(value=self.get(name))
            entry = ttk.Entry(grid, textvariable=var, width=3)
            entry.grid(row=i, column=1, sticky='w', padx=8)
            for event in ('<FocusOut>', '<Return>'):
                entry.bind(event, lambda e, n=name: self.character(n))
            entry.bind('<Enter>', lambda e: self.help.config(
                text=tr(HELP['characters'])))
            self.vars[name] = var
        ttk.Label(parent, text=first_sentence(tr(HELP['characters'])),
                  style='Muted.TLabel', wraplength=620,
                         justify='left').pack(
                      anchor='w', pady=(2, 6))

    # Changes --------------------------------------------------------------

    def toggled(self, name: str):
        self.change(name, self.vars[name].get())
        for child, parent in DEPENDS.items():
            if parent == name and not self.vars[name].get() and \
                    self.get(child):
                self.change(child, False)
        self.refresh()

    def character(self, name: str):
        value = self.vars[name].get().strip()
        if value == self.get(name):
            return
        others = {self.get(n) for _, n in CHARACTERS if n != name} | {'~'}
        if len(value) == 1 and is_command_character(value) and \
                value not in others:
            self.change(name, value)
        else:
            messagebox.showerror(
                self.name, tr('“{value}” cannot be {setting}: it must be one '
                              'punctuation character, different from the '
                              'others and from ~.', value=value,
                              setting=label(name).lower()), parent=self.win)
        self.refresh()

    def usual(self):
        if not messagebox.askyesno(
                self.name, tr('Go back to the default value of every '
                              'setting?'), parent=self.win):
            return
        usual = Settings()
        for name in MODES + DEV_MODES + tuple(n for _, n in CHARACTERS):
            if self.get(name) != getattr(usual, name):
                self.change(name, getattr(usual, name))
        self.refresh()

    def refresh(self):
        """Shows the values (after a change here or in the window)."""
        if not self.win.winfo_exists():
            return
        for name, var in self.vars.items():
            if var.get() != self.get(name):
                var.set(self.get(name))
        for child, parent in DEPENDS.items():
            if child in self.boxes:
                self.boxes[child].state(
                    ['!disabled'] if self.get(parent) else ['disabled'])
