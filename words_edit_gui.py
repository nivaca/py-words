#!/usr/bin/env python3
"""A window for editing the dictionary: python3 words_edit_gui.py

Find an entry (by a Latin form such as "amicorum", a stem, or an English
word), correct it, add a new one (from scratch, or as a copy of the one
shown), or delete it.  The preview shows how WORDS will show the entry and
any problems; "Try" shows what WORDS makes of a word with the dictionary as
edited.  Nothing is written until "Save"; the first save keeps the original
file as dictionary.xml.bak.
"""

from version import check_python
check_python()          # (before the modules that need it)

import os
import tkinter as tk
from tkinter import messagebox, ttk

from lexicon import default_datadir
from editor import Editor, Fields, FIELD_LABELS, POS_CHOICES
from gui_fonts import Fonts
from lexicon import DICTIONARY
from version import NAME
from xmldata import DataError

SEP = ' — '            # between a code and its description


def _show(value, description):
    return value + SEP + description if description else value


def _value(shown):
    return shown.split(SEP)[0].strip()


class EditorWindow:
    def __init__(self, master, datadir, on_save=None):
        self.editor = Editor(datadir)
        self.on_save = on_save
        self.current = None             # the entry shown, or None if new
        self.fields = Fields()
        self.results = []
        self.win = win = tk.Toplevel(master) if master else tk.Tk()
        win.title(f'{NAME}: dictionary editor')
        win.geometry('1080x720')
        self.fonts = Fonts.of(win)
        win.protocol('WM_DELETE_WINDOW', self.close)

        top = ttk.Frame(win, padding=(8, 8, 8, 4))
        top.pack(fill='x')
        ttk.Label(top, text='Find:').pack(side='left')
        self.query = ttk.Entry(top, font=self.fonts.entry)
        self.query.pack(side='left', fill='x', expand=True, padx=6)
        self.query.bind('<Return>', lambda e: self.find())
        ttk.Button(top, text='Find', command=self.find).pack(side='left')
        ttk.Label(top, text='  a Latin form, a stem or an English word',
                  foreground='gray').pack(side='left')

        panes = ttk.PanedWindow(win, orient='horizontal')
        panes.pack(fill='both', expand=True, padx=8)

        left = ttk.Frame(panes)
        listframe = ttk.Frame(left)
        listframe.pack(side='top', fill='both', expand=True)
        self.listbox = tk.Listbox(listframe, width=48, activestyle='dotbox',
                                  exportselection=False)
        scroll = ttk.Scrollbar(listframe, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.listbox.pack(side='left', fill='both', expand=True)
        self.listbox.bind('<<ListboxSelect>>', lambda e: self.select())
        buttons = ttk.Frame(left, padding=(0, 6))
        buttons.pack(fill='x')
        ttk.Button(buttons, text='New', command=self.new).pack(side='left')
        ttk.Button(buttons, text='New like this',
                   command=self.copy).pack(side='left', padx=4)
        ttk.Button(buttons, text='Delete',
                   command=self.delete).pack(side='left')
        panes.add(left, weight=1)

        right = ttk.Frame(panes, padding=(10, 0, 0, 0))
        panes.add(right, weight=2)
        self.form = ttk.Frame(right)
        self.form.pack(fill='x')
        self.preview = ttk.Label(right, font=self.fonts.bold,
                                 wraplength=620, justify='left')
        self.preview.pack(fill='x', pady=(10, 0))
        self.problems = ttk.Label(right, foreground='#b00020',
                                  wraplength=620, justify='left')
        self.problems.pack(fill='x')
        actions = ttk.Frame(right, padding=(0, 8))
        actions.pack(fill='x')
        self.apply_button = ttk.Button(actions, text='Apply changes',
                                       command=self.apply)
        self.apply_button.pack(side='left')
        ttk.Button(actions, text='Revert',
                   command=self.revert).pack(side='left', padx=4)

        trybox = ttk.Frame(right)
        trybox.pack(fill='x', pady=(8, 0))
        ttk.Label(trybox, text='Try a word:').pack(side='left')
        self.word = ttk.Entry(trybox)
        self.word.pack(side='left', fill='x', expand=True, padx=6)
        self.word.bind('<Return>', lambda e: self.try_word())
        ttk.Button(trybox, text='Try', command=self.try_word).pack(
            side='left')
        self.output = tk.Text(right, height=10, wrap='word',
                              font=self.fonts.text, state='disabled')
        self.output.pack(fill='both', expand=True, pady=(4, 0))

        bottom = ttk.Frame(win, padding=(8, 4, 8, 8))
        bottom.pack(fill='x')
        self.status = ttk.Label(bottom)
        self.status.pack(side='left')
        ttk.Button(bottom, text='Close', command=self.close).pack(
            side='right')
        ttk.Button(bottom, text='Save', command=self.save).pack(
            side='right', padx=4)
        ttk.Button(bottom, text='Font…',
                   command=lambda: self.fonts.dialog(win)).pack(
                       side='right', padx=(0, 12))

        self.vars = {}
        self.new()
        self.update_status()
        self.query.focus_set()

    # The form ----------------------------------------------------------------

    def build_form(self):
        """(Re)builds the fields for the current part of speech."""
        for w in self.form.winfo_children():
            w.destroy()
        self.vars = {}
        f = self.fields
        row = 0

        def label(text):
            ttk.Label(self.form, text=text).grid(row=row, column=0,
                                                 sticky='w', pady=2)

        label('part of speech')
        pos = ttk.Combobox(self.form, state='readonly', width=44,
                           values=[_show(v, d) for v, d in POS_CHOICES])
        pos.set(_show(f.pos, dict(POS_CHOICES)[f.pos]))
        pos.bind('<<ComboboxSelected>>',
                 lambda e: self.change_pos(_value(pos.get())))
        pos.grid(row=row, column=1, sticky='w')
        row += 1
        for i, text in enumerate(f.stem_labels()):
            label(text)
            var = tk.StringVar(value=f.stems[i])
            ttk.Entry(self.form, textvariable=var, width=24).grid(
                row=row, column=1, sticky='w')
            var.trace_add('write', lambda *a: self.changed())
            self.vars[f'stem{i}'] = var
            row += 1
        for name in f.names():
            label(FIELD_LABELS.get(name, name))
            options = self.editor.options(name, f.pos)
            var = tk.StringVar()
            current = f.attrs.get(name, 'X' if name in (
                'age', 'area', 'geo', 'freq', 'source') else '')
            if options:
                shown = dict(options)
                var.set(_show(current, shown.get(current, '')))
                state = 'normal' if name in ('decl', 'conj') else 'readonly'
                widget = ttk.Combobox(self.form, textvariable=var,
                                      state=state, width=44,
                                      values=[_show(v, d)
                                              for v, d in options])
            else:
                var.set(current)
                widget = ttk.Entry(self.form, textvariable=var, width=12)
            widget.grid(row=row, column=1, sticky='w')
            var.trace_add('write', lambda *a: self.changed())
            self.vars[name] = var
            row += 1
        label('meaning')
        var = tk.StringVar(value=f.meaning)
        ttk.Entry(self.form, textvariable=var, width=80).grid(
            row=row, column=1, sticky='we')
        var.trace_add('write', lambda *a: self.changed())
        self.vars['meaning'] = var
        self.form.columnconfigure(1, weight=1)
        self.changed()

    def read_form(self):
        f = self.fields
        for i in range(len(f.stem_labels())):
            f.stems[i] = self.vars[f'stem{i}'].get().strip()
        for name in f.names():
            f.attrs[name] = _value(self.vars[name].get())
        f.meaning = self.vars['meaning'].get()

    def change_pos(self, pos):
        self.read_form()
        self.fields.set_pos(pos)
        self.build_form()

    def changed(self):
        """Updates the preview and the problems."""
        if 'meaning' not in self.vars:
            return
        self.read_form()
        try:
            entry = self.fields.entry()
        except DataError as e:
            self.preview.config(text='')
            self.problems.config(text='✖ ' + e.message)
            self.apply_button.state(['disabled'])
            return
        self.preview.config(text=self.editor.describe(entry))
        warnings = self.editor.warnings(entry)
        self.problems.config(text='\n'.join('⚠ ' + w for w in warnings))
        self.apply_button.state(['!disabled'])
        self.apply_button.config(
            text='Add to the dictionary' if self.current is None
            else 'Apply changes')

    # Actions -----------------------------------------------------------------

    def find(self):
        self.results = self.editor.search(self.query.get())
        self.listbox.delete(0, 'end')
        for e in self.results:
            self.listbox.insert('end', self.editor.summary(e, 80))
        self.status.config(text=f'{len(self.results)} found'
                           if self.results else 'Nothing found')
        if self.results:
            self.listbox.selection_set(0)
            self.select()

    def select(self):
        sel = self.listbox.curselection()
        if sel:
            self.show(self.results[sel[0]])

    def show(self, entry):
        self.current = entry
        self.fields = Fields.of(entry)
        self.build_form()

    def new(self):
        self.current = None
        self.fields = Fields('N', {'decl': '', 'gender': '', 'kind': 'X'})
        self.listbox.selection_clear(0, 'end')
        self.build_form()

    def copy(self):
        """A new entry with the values of the one shown."""
        self.read_form()
        self.current = None
        self.listbox.selection_clear(0, 'end')
        self.build_form()

    def revert(self):
        if self.current is not None:
            self.show(self.current)
        else:
            self.new()

    def apply(self):
        self.read_form()
        try:
            entry = self.fields.entry()
        except DataError as e:
            messagebox.showerror(NAME, e.message, parent=self.win)
            return
        if self.current is None:
            self.editor.add(entry)
            done = 'Added'
        else:
            self.editor.replace(self.current, entry)
            done = 'Changed'
        self.current = entry
        self.results = [entry] + [e for e in self.results
                                  if e is not entry]
        self.refresh_list()
        self.update_status(f'{done}: {self.editor.summary(entry, 60)}')
        self.changed()

    def delete(self):
        if self.current is None:
            return
        if not messagebox.askyesno(
                NAME, 'Delete this entry?\n\n' +
                self.editor.summary(self.current, 90), parent=self.win):
            return
        self.editor.delete(self.current)
        self.results = [e for e in self.results if e is not self.current]
        self.refresh_list()
        self.new()
        self.update_status('Deleted')

    def refresh_list(self):
        self.listbox.delete(0, 'end')
        for e in self.results:
            self.listbox.insert('end', self.editor.summary(e, 80))
        if self.current is not None:
            for i, e in enumerate(self.results):
                if e is self.current:
                    self.listbox.selection_set(i)

    def try_word(self):
        word = self.word.get().strip()
        if not word:
            return
        text = self.editor.try_word(word)
        self.output.config(state='normal')
        self.output.delete('1.0', 'end')
        self.output.insert('1.0', text.strip() or '(nothing)')
        self.output.config(state='disabled')

    def save(self):
        try:
            self.editor.save()
        except OSError as e:
            messagebox.showerror(NAME, f'Cannot save: {e}',
                                 parent=self.win)
            return
        self.update_status(f'Saved {self.editor.path}')
        if self.on_save:
            self.on_save()

    def update_status(self, message=''):
        unsaved = '  (unsaved changes)' if self.editor.dirty else ''
        self.status.config(text=message + unsaved)

    def close(self):
        if self.editor.dirty:
            answer = messagebox.askyesnocancel(
                NAME, 'Save the changes to the dictionary?', parent=self.win)
            if answer is None:
                return
            if answer:
                self.save()
        self.win.destroy()


def main():
    datadir = default_datadir()
    if not os.path.isfile(os.path.join(datadir, DICTIONARY)):
        raise SystemExit(f'There is no {DICTIONARY} in {datadir}')
    window = EditorWindow(None, datadir)
    window.win.mainloop()


if __name__ == '__main__':
    main()

