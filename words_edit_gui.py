#!/usr/bin/env python3
"""A window for editing the dictionary: python3 words_edit_gui.py

Find an entry (by a Latin form such as "amicorum", a stem, or a word of
its meaning), correct it, add a new one (from scratch, or as a copy of the one
shown), or delete it.  The preview shows how WORDS will show the entry and
any problems; "Try" shows what WORDS makes of a word with the dictionary as
edited.  A change counts once it is applied ("Apply changes"); "Save"
applies the entry shown and writes the file, and leaving an entry with
changes not applied asks what to do with them.  Nothing is written until
"Save"; the first save keeps the original file as dictionary.xml.bak.

"Meanings in" chooses a language of the meanings besides English: the form
then has the meaning in that language too, which "Save" writes to its file
in languages/.
"""

from version import check_python
check_python()          # (before the modules that need it)

import os
import tkinter as tk
from tkinter import messagebox, ttk

import interface
from interface import tr
from settings import Settings, ensure_config
from lexicon import default_datadir
from editor import Editor, Editing, Fields, FIELD_LABELS, POS_CHOICES
from gui_fonts import Fonts
from gui_theme import Theme
from lexicon import DICTIONARY
from version import NAME
from xmldata import DataError

SEP = ' — '            # between a code and its description


def _show(value, description):
    return value + SEP + description if description else value


def _value(shown):
    return shown.split(SEP)[0].strip()


class EditorWindow:
    def __init__(self, master, datadir, on_save=None, language='en'):
        """LANGUAGE: the language of the meanings edited besides
        English."""
        self.editor = Editor(datadir, language)
        self.editing = Editing(self.editor)
        self.on_save = on_save
        self.fields = Fields()
        self.win = win = tk.Toplevel(master) if master else tk.Tk()
        win.title(tr('{name}: dictionary editor', name=NAME))
        win.geometry('1080x720')
        self.fonts = Fonts.of(win)
        Theme.of(win)                   # (light or dark, as saved)
        win.protocol('WM_DELETE_WINDOW', self.close)

        top = ttk.Frame(win, padding=(8, 8, 8, 4))
        top.pack(fill='x')
        ttk.Label(top, text=tr('Find:')).pack(side='left')
        self.query = ttk.Entry(top, font=self.fonts.entry)
        self.query.pack(side='left', fill='x', expand=True, padx=6)
        self.query.bind('<Return>', lambda e: self.find())
        ttk.Button(top, text=tr('Find'), command=self.find).pack(
            side='left')
        ttk.Label(top, text='  ' + tr('a Latin form, a stem or a word of '
                                      'the meanings'),
                  style='Muted.TLabel').pack(side='left')
        self.language_codes = {tr(name): code for code, name in
                               self.editor.language_names.items()}
        self.language_box = ttk.Combobox(
            top, state='readonly', width=10,
            values=list(self.language_codes))
        self.language_box.set(tr(self.editor.language_name))
        self.language_box.bind('<<ComboboxSelected>>',
                               lambda e: self.choose_language())
        self.language_box.pack(side='right')
        ttk.Label(top, text=tr('Meanings in:')).pack(side='right',
                                                     padx=(12, 4))

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
        ttk.Button(buttons, text=tr('New'), command=self.new).pack(
            side='left')
        ttk.Button(buttons, text=tr('New like this'),
                   command=self.copy).pack(side='left', padx=4)
        ttk.Button(buttons, text=tr('Delete'),
                   command=self.delete).pack(side='left')
        panes.add(left, weight=1)

        right = ttk.Frame(panes, padding=(10, 0, 0, 0))
        panes.add(right, weight=2)
        self.form = ttk.Frame(right)
        self.form.pack(fill='x')
        self.preview = ttk.Label(right, font=self.fonts.bold,
                                 wraplength=620, justify='left')
        self.preview.pack(fill='x', pady=(10, 0))
        self.problems = ttk.Label(right, style='Error.TLabel',
                                  wraplength=620, justify='left')
        self.problems.pack(fill='x')
        actions = ttk.Frame(right, padding=(0, 8))
        actions.pack(fill='x')
        self.apply_button = ttk.Button(actions, text=tr('Apply changes'),
                                       command=self.apply)
        self.apply_button.pack(side='left')
        ttk.Button(actions, text=tr('Revert'),
                   command=self.revert).pack(side='left', padx=4)

        trybox = ttk.Frame(right)
        trybox.pack(fill='x', pady=(8, 0))
        ttk.Label(trybox, text=tr('Try a word:')).pack(side='left')
        self.word = ttk.Entry(trybox)
        self.word.pack(side='left', fill='x', expand=True, padx=6)
        self.word.bind('<Return>', lambda e: self.try_word())
        ttk.Button(trybox, text=tr('Try'), command=self.try_word).pack(
            side='left')
        self.output = tk.Text(right, height=10, wrap='word',
                              font=self.fonts.text, state='disabled')
        self.output.pack(fill='both', expand=True, pady=(4, 0))

        bottom = ttk.Frame(win, padding=(8, 4, 8, 8))
        bottom.pack(fill='x')
        self.status = ttk.Label(bottom)
        self.status.pack(side='left')
        ttk.Button(bottom, text=tr('Close'), command=self.close).pack(
            side='right')
        ttk.Button(bottom, text=tr('Save'), command=self.save).pack(
            side='right', padx=4)
        ttk.Button(bottom, text=tr('Font…'),
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

        label(tr('part of speech'))
        pos = ttk.Combobox(self.form, state='readonly', width=44,
                           values=[_show(v, tr(d)) for v, d in POS_CHOICES])
        pos.set(_show(f.pos, tr(dict(POS_CHOICES)[f.pos])))
        pos.bind('<<ComboboxSelected>>',
                 lambda e: self.change_pos(_value(pos.get())))
        pos.grid(row=row, column=1, sticky='w')
        row += 1
        for i, text in enumerate(f.stem_labels()):
            label(tr(text))
            var = tk.StringVar(value=f.stems[i])
            ttk.Entry(self.form, textvariable=var, width=24).grid(
                row=row, column=1, sticky='w')
            var.trace_add('write', lambda *a: self.changed())
            self.vars[f'stem{i}'] = var
            row += 1
        for name in f.names():
            label(tr(FIELD_LABELS.get(name, name)))
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
        meanings = [('meaning', tr('meaning'), f.meaning)]
        if f.translation is not None:       # (and in the language chosen)
            meanings = [('meaning', tr('meaning in English'), f.meaning),
                        ('translation',
                         tr('meaning in {language}',
                            language=tr(self.editor.language_name)),
                         f.translation)]
        for key, text, value in meanings:
            label(text)
            var = tk.StringVar(value=value)
            ttk.Entry(self.form, textvariable=var, width=80).grid(
                row=row, column=1, sticky='we')
            var.trace_add('write', lambda *a: self.changed())
            self.vars[key] = var
            row += 1
        self.form.columnconfigure(1, weight=1)
        self.changed()

    def read_form(self):
        f = self.fields
        for i in range(len(f.stem_labels())):
            f.stems[i] = self.vars[f'stem{i}'].get().strip()
        for name in f.names():
            f.attrs[name] = _value(self.vars[name].get())
        f.meaning = self.vars['meaning'].get()
        if 'translation' in self.vars:
            f.translation = self.vars['translation'].get()

    def change_pos(self, pos):
        self.read_form()
        self.fields.set_pos(pos)
        self.build_form()

    def changed(self):
        """Updates the preview and the problems."""
        if 'meaning' not in self.vars:
            return
        self.apply_button.config(
            text=tr('Add to the dictionary') if self.current is None
            else tr('Apply changes'))
        self.read_form()
        try:
            entry = self.fields.entry()
        except DataError as e:
            self.preview.config(text='')
            self.problems.config(text='✖ ' + e.message)
            self.apply_button.state(['disabled'])
            return
        self.preview.config(text=self.editor.describe(entry))
        warnings = self.editor.warnings(entry, self.fields.translation)
        self.problems.config(text='\n'.join('⚠ ' + w for w in warnings))
        self.apply_button.state(['!disabled'])

    # Actions -----------------------------------------------------------------

    @property
    def current(self):
        """The entry shown, or None for a new one."""
        return self.editing.current

    @property
    def results(self):
        return self.editing.results

    def values(self) -> Fields:
        """The values in the form."""
        self.read_form()
        return self.fields

    def find(self):
        self.editing.find(self.query.get())
        self.listbox.delete(0, 'end')
        for e in self.results:
            self.listbox.insert('end', self.editor.summary(e, 80))
        self.status.config(text=tr('{n} found', n=len(self.results))
                           if self.results else tr('Nothing found'))
        if self.results:
            self.listbox.selection_set(0)
            self.select()

    def select(self):
        sel = self.listbox.curselection()
        if not sel or self.results[sel[0]] is self.current:
            return
        entry = self.results[sel[0]]
        if not self.leave():                # stay on the entry shown
            self.refresh_list()
            return
        self.show(entry)

    def show(self, entry):
        self.fields = self.editor.fields(entry)
        self.build_form()
        self.showing(entry)

    def showing(self, entry):
        """The form now shows ENTRY (None: a new one)."""
        self.editing.start(entry, self.values())
        self.changed()                  # (the button says Add or Apply)

    def new(self, ask=True):
        """An empty form, for a new entry (ASK: what to do with changes
        not applied)."""
        if ask and not self.leave():
            return
        self.fields = Fields('N', {'decl': '', 'gender': '', 'kind': 'X'},
                             translation=self.editor.translation(None))
        self.listbox.selection_clear(0, 'end')
        self.build_form()
        self.showing(None)

    def copy(self):
        """A new entry with the values of the one shown."""
        self.read_form()
        self.listbox.selection_clear(0, 'end')
        self.build_form()
        self.showing(None)

    def choose_language(self):
        """Edits the meanings in the language chosen (after asking about
        the changes not applied)."""
        code = self.language_codes.get(self.language_box.get())
        if code is None or code == self.editor.language:
            return
        if not self.leave():
            self.language_box.set(tr(self.editor.language_name))
            return
        try:
            self.editor.set_language(code)
        except (LookupError, DataError) as e:
            messagebox.showerror(NAME, str(e), parent=self.win)
            self.language_box.set(tr(self.editor.language_name))
            return
        if self.current is not None:
            self.show(self.current)
        else:
            self.new(ask=False)
        self.refresh_list()

    def revert(self):
        if self.current is not None:
            self.show(self.current)
        else:
            self.new(ask=False)

    def pending(self) -> bool:
        """Whether the form has changes that were not applied."""
        return 'meaning' in self.vars and self.editing.pending(self.values())

    def leave(self) -> bool:
        """Before the form shows something else: asks what to do with
        changes not applied.  False: stay."""
        if 'meaning' not in self.vars:
            return True

        def ask(what):
            return messagebox.askyesnocancel(
                NAME, tr('Apply the changes to {what} first?', what=what) +
                '\n\n' + tr('No leaves them out; Cancel stays on the '
                             'entry.'), parent=self.win)
        try:
            return self.editing.leave(self.values(), ask)
        except DataError as e:
            messagebox.showerror(NAME, e.message, parent=self.win)
            return False
        finally:
            self.refresh_list()

    def apply(self) -> bool:
        """Puts the form into the dictionary; False if it has an error."""
        try:
            entry, done = self.editing.apply(self.values())
        except DataError as e:
            messagebox.showerror(NAME, e.message, parent=self.win)
            return False
        self.applied(entry, done)
        return True

    def applied(self, entry, done):
        self.refresh_list()
        self.update_status(f'{tr(done)}: {self.editor.summary(entry, 60)}')
        self.changed()

    def delete(self):
        if self.current is None:
            return
        if not messagebox.askyesno(
                NAME, tr('Delete this entry?') + '\n\n' +
                self.editor.summary(self.current, 90), parent=self.win):
            return
        self.editing.delete()
        self.refresh_list()
        self.new(ask=False)
        self.update_status(tr('Deleted'))

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
        self.output.insert('1.0', text.strip() or tr('(nothing)'))
        self.output.config(state='disabled')

    def save(self):
        """Applies the entry shown, if it has changes, and saves."""
        try:
            applied = self.editing.save(self.values())
        except DataError as e:
            messagebox.showerror(NAME, e.message, parent=self.win)
            self.update_status(tr('Not saved: the entry shown has an '
                                  'error'))
            return
        except OSError as e:
            messagebox.showerror(NAME, tr('Cannot save: {error}', error=e),
                                 parent=self.win)
            return
        if applied:
            self.applied(*applied)
        self.update_status(
            tr('Saved {path} and the meanings in {language}',
               path=self.editor.path,
               language=tr(self.editor.language_name))
            if self.editor.translating else
            tr('Saved {path}', path=self.editor.path))
        if self.on_save:
            self.on_save()

    def update_status(self, message=''):
        unsaved = '  ' + tr('(unsaved changes)') if self.editor.dirty \
            else ''
        self.status.config(text=message + unsaved)

    def close(self):
        if not self.leave():
            return
        if self.editor.dirty:
            answer = messagebox.askyesnocancel(
                NAME, tr('Save the changes to the dictionary?'),
                parent=self.win)
            if answer is None:
                return
            if answer:
                self.save()
        self.win.destroy()


def main():
    ensure_config()                 # (made at the first start)
    interface.use_configured()
    datadir = default_datadir()
    if not os.path.isfile(os.path.join(datadir, DICTIONARY)):
        raise SystemExit(tr('There is no {file} in {folder}',
                            file=DICTIONARY, folder=datadir))
    settings = Settings()
    settings.load(datadir)
    window = EditorWindow(None, datadir, language=settings.language)
    interface.translate_tk(window.win)
    window.win.mainloop()


if __name__ == '__main__':
    main()

