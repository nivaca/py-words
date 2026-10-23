#!/usr/bin/env python3
"""A window for WORDS: python3 words_gui.py

Type Latin words (or, in the other direction, a word in the language of
the meanings) and press Enter; the results are those the command line
shows.
"""

from version import check_python
check_python()          # (before the modules that need it)

import os
import sys
import queue
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import guide
import interface
from config import ConfigError
from gui_fonts import Fonts
from gui_results import Results
from gui_settings import SettingsDialog
from gui_theme import Theme
from history import History
from interface import N_, tr
from lexicon import default_datadir
from lexicon import Lexicon, DICTIONARY
from session import Session
from settings import COMMAND_LINE, Settings, section_of
from version import NAME, URL, about

#  What the window shows until the first search
WELCOME = N_('Type a Latin word or line, and press Enter.  "Help" explains '
             'the results, and "About" shows the credits.')


class App:
    def __init__(self, root, datadir):
        self.root = root
        self.datadir = datadir
        self.session = None
        self.saved = None               # (see ready)
        self.settings_window = None
        self.help_window = None
        self.lock = threading.Lock()
        root.geometry('1000x620')
        self.fonts = Fonts.of(root)
        self.theme = Theme.of(root)
        #  the searches (of this and earlier sessions, and of the command
        #  line), in the list of the box where words are typed
        self.history = History()
        self.languages: dict[str, str] = {}         # name -> code
        self.reverse = tk.BooleanVar(value=False)
        self.fuzzy = tk.BooleanVar(value=Settings().fuzzy_search)
        self.dark = tk.BooleanVar(value=self.theme.dark)
        self.shown = None               # (the results, and their direction)
        self.gloss_table: dict[str, str] = {}
        self.build()
        self.welcome = True             # (until the first search)
        self.show_welcome()
        self.status.config(text=tr('Loading the dictionary…'))

        self.done = queue.Queue()       # (function, arguments) to call
        self.poll()
        self.set_busy(True)
        threading.Thread(target=self.load, daemon=True).start()

    def build(self):
        """The widgets of the window, in the language of the interface."""
        root = self.root
        root.title(tr('{name}: a Latin dictionary', name=NAME))
        top = ttk.Frame(root, padding=(8, 8, 8, 4))
        top.pack(fill='x')
        self.entry = ttk.Combobox(top, font=self.fonts.entry,
                                  values=self.history.recent())
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', lambda e: self.lookup())
        self.entry.bind('<<ComboboxSelected>>', lambda e: self.lookup())
        self.button = ttk.Button(top, text=tr('Look up'),
                                 command=self.lookup)
        self.button.pack(side='left', padx=(6, 0))

        lang = ttk.Frame(root, padding=(8, 0, 8, 6))
        lang.pack(fill='x')
        #  on the left, the direction, and below it the language of the
        #  meanings; on the right, the buttons
        choices = ttk.Frame(lang)
        choices.pack(side='left')
        direction = ttk.Frame(choices)
        direction.pack(anchor='w')
        english = tr('English')
        self.to_language = ttk.Radiobutton(
            direction, text=tr('Latin → {language}', language=english),
            value=False, variable=self.reverse)
        self.to_language.pack(side='left')
        self.to_latin = ttk.Radiobutton(
            direction, text=tr('{language} → Latin', language=english),
            value=True, variable=self.reverse)
        self.to_latin.pack(side='left', padx=(12, 0))
        #  (the choices of the language are known once the dictionary is
        #  loaded)
        meanings = ttk.Frame(choices)
        meanings.pack(anchor='w', pady=(4, 0))
        ttk.Label(meanings, text=tr('Meanings in')).pack(side='left',
                                                         padx=(0, 4))
        self.language = ttk.Combobox(meanings, state='disabled', width=9)
        self.language.pack(side='left')
        self.language.bind('<<ComboboxSelected>>',
                           lambda e: self.choose_language())
        ttk.Checkbutton(meanings, text=tr('Fuzzy search'),
                        variable=self.fuzzy, command=self.choose_fuzzy
                        ).pack(side='left', padx=(12, 0))
        self.menus()
        #  the status line and the dark mode box, at the bottom (packed
        #  before the results, so that they stay when the window is small
        #  for its fonts)
        bottom = ttk.Frame(root, padding=(8, 2, 8, 6))
        bottom.pack(side='bottom', fill='x')
        self.results = Results(root, self.fonts, self.theme, self.look_up,
                               self.explain_codes, self.explain_analysis)
        self.results.pack(fill='both', expand=True, padx=8)
        self.text = self.results.text
        ttk.Checkbutton(bottom, text=tr('Dark mode'), variable=self.dark,
                        command=self.choose_dark).pack(side='right')
        self.status = ttk.Label(bottom)
        self.status.pack(side='left', fill='x', expand=True)
        root.bind('<<FontsChanged>>', lambda e: self.fit())
        self.fit()

    def menus(self):
        """The menu bar: Dictionary, View and Help."""
        root = self.root
        bar = tk.Menu(root)
        key = 'Command' if sys.platform == 'darwin' else 'Ctrl'
        dictionary = tk.Menu(bar, tearoff=False)
        dictionary.add_command(label=tr('Edit dictionary…'),
                               command=self.edit_dictionary)
        dictionary.add_command(label=tr('Settings…'),
                               command=self.settings_dialog)
        dictionary.add_separator()
        dictionary.add_command(label=tr('Quit'), accelerator=f'{key}+Q',
                               command=root.destroy)
        bar.add_cascade(label=tr('Dictionary'), menu=dictionary)
        view = tk.Menu(bar, tearoff=False)
        view.add_command(label=tr('Find in results…'),
                         accelerator=f'{key}+F', command=self.find)
        view.add_separator()
        view.add_command(label=tr('Larger text'), accelerator=f'{key}++',
                         command=lambda: self.fonts.key(1))
        view.add_command(label=tr('Smaller text'), accelerator=f'{key}+−',
                         command=lambda: self.fonts.key(-1))
        view.add_command(label=tr('Usual size'), accelerator=f'{key}+0',
                         command=lambda: self.fonts.key(0))
        view.add_command(label=tr('Font…'),
                         command=lambda: self.fonts.dialog(root))
        view.add_separator()
        view.add_checkbutton(label=tr('Dark mode'), variable=self.dark,
                             command=self.choose_dark)
        bar.add_cascade(label=tr('View'), menu=view)
        helping = tk.Menu(bar, tearoff=False)
        helping.add_command(label=tr('Help'), accelerator='F1',
                            command=self.help)
        helping.add_command(label=tr('About'), command=self.about)
        bar.add_cascade(label=tr('Help'), menu=helping)
        root.config(menu=bar)
        self.menu_bar = bar
        mod = 'Command' if sys.platform == 'darwin' else 'Control'
        root.bind('<F1>', lambda e: self.help())
        root.bind(f'<{mod}-f>', lambda e: self.find())
        root.bind(f'<{mod}-q>', lambda e: root.destroy())

    def choose_dark(self):
        self.theme.set(self.dark.get())

    def find(self):
        return self.results.show_find()

    def fit(self):
        """Makes the window at least as wide as its widgets need (up to
        the screen), so that none of its buttons is cut off when the text
        is large or long."""
        root = self.root
        root.update_idletasks()
        width = min(root.winfo_reqwidth(), root.winfo_screenwidth())
        root.minsize(width, 300)
        if root.winfo_width() < width:
            root.geometry(f'{width}x{root.winfo_height()}')

    def rebuild(self):
        """Builds the window again in the language of the interface (now
        another), keeping what it shows."""
        query = self.entry.get()
        busy = str(self.button['state']) == 'disabled'
        for child in self.root.winfo_children():
            if not isinstance(child, tk.Toplevel):
                child.destroy()
        self.build()
        self.entry.insert(0, query)
        if self.welcome or self.shown is None:
            self.show_welcome()
        else:
            self.show_results(*self.shown)
        self.status.config(text=tr('Loading the dictionary…') if busy
                           else tr('Ready.'))
        self.set_busy(busy)
        interface.translate_tk(self.root)
        if self.session is not None:
            self.languages = {tr(name): code for code, name in
                              self.session.lexicon.language_names().items()}
            self.language.config(values=list(self.languages),
                                 state='readonly')
            self.show_language()

    # The dictionary is loaded, and words looked up, on a worker thread,
    # which hands the results to the window through a queue (Tk may only
    # be used from its own thread).

    def poll(self):
        try:
            while True:
                function, args = self.done.get_nowait()
                function(*args)
        except queue.Empty:
            pass
        try:
            self.root.after(50, self.poll)
        except tk.TclError:             # (the window is gone)
            pass

    def load(self):
        saved = None
        try:
            settings = Settings()
            settings.load(self.datadir)
            saved = settings.copy()
            settings.pause_in_screen_output = False     # (no paging here)
            session = Session(Lexicon.load(self.datadir), settings)
            error = None
        except Exception as e:              # keep the window alive
            session, error = None, e
        self.done.put((self.ready, (session, error, saved)))

    def ready(self, session, error, saved=None):
        if error is not None:
            messagebox.showerror(NAME, tr('Could not load the dictionary:')
                                 + f'\n{error}')
            self.root.destroy()
            return
        self.session = session
        #  the settings as saved, which the window keeps for the command
        #  line (session.settings differ in what the window cannot use)
        self.saved = saved or session.settings.copy()
        self.languages = {tr(name): code for code, name in
                          session.lexicon.language_names().items()}
        self.language.config(values=list(self.languages), state='readonly')
        self.show_language()
        self.fuzzy.set(self.saved.fuzzy_search)
        self.gloss_table = guide.gloss_table(session)
        if self.welcome:
            self.show_welcome()         # (its examples, in the language)
        self.status.config(text=session.notice or tr('Ready.'))
        self.set_busy(False)
        self.entry.focus_set()

    def setting(self, name):
        return getattr(self.saved, name)

    def choose_fuzzy(self):
        """The "Fuzzy search" box (the setting fuzzy_search)."""
        if self.session is None:            # (still loading: as it was)
            self.fuzzy.set(not self.fuzzy.get())
            return
        self.change_setting('fuzzy_search', self.fuzzy.get())

    def change_setting(self, name, value):
        """Changes a setting (a parameter, developer mode, command
        character or language), applies it, and keeps it in the
        configuration file.  The meanings follow the language of the
        interface, if the dictionary has it."""
        if name == 'interface' and value != self.session.language.code and \
                value in self.session.lexicon.language_names():
            self.change_setting('language', value)
        setattr(self.saved, name, value)
        if name == 'interface':
            interface.use(value)
            self.gloss_table = guide.gloss_table(self.session)
        section = section_of(name)
        with self.lock:
            if name not in COMMAND_LINE:
                setattr(self.session.settings, name, value)
            self.session.settings_changed()     # (language, cache)
            try:
                self.saved.save(section, only=[name])
            except (OSError, ConfigError) as e:
                self.status.config(text=tr('The settings were not saved: '
                                           '{error}', error=e))
        if name == 'interface':
            self.rebuild()
            if self.settings_window is not None:
                self.settings_window.win.destroy()
                self.settings_window = None
                self.settings_dialog()
            return
        self.fuzzy.set(self.saved.fuzzy_search)     # (also when it changes
                                                    # in the dialogue)
        if self.settings_window is not None:
            self.settings_window.refresh()
        if self.entry.get().strip():
            self.lookup()

    def show_language(self):
        """The language of the meanings, in the pull-down and the
        direction buttons."""
        name = tr(self.session.language.name)
        self.language.set(name)
        self.to_language.config(text=tr('Latin → {language}',
                                        language=name))
        self.to_latin.config(text=tr('{language} → Latin', language=name))

    def choose_language(self):
        code = self.languages.get(self.language.get())
        if code is None or self.session is None or \
                code == self.session.language.code:
            return
        self.change_setting('language', code)
        self.show_language()
        if self.session.notice:
            self.status.config(text=self.session.notice)

    def settings_dialog(self):
        """Opens the dialogue with every setting (or brings it forward)."""
        if self.session is None:
            return
        win = self.settings_window
        if win is not None and win.win.winfo_exists():
            win.win.lift()
            return
        self.settings_window = SettingsDialog(
            self.root, self.setting, self.change_setting, NAME,
            clear_history=self.clear_history, fonts=self.fonts.dialog)

    def clear_history(self):
        self.history.clear()
        self.entry.configure(values=[])

    def look_up(self, query: str, to_latin: bool = False):
        """Looks QUERY up (a word clicked in the results), in the direction
        given."""
        if self.session is None or str(self.button['state']) == 'disabled':
            return
        self.reverse.set(to_latin)
        self.entry.delete(0, 'end')
        self.entry.insert(0, query)
        self.lookup()

    def explain_codes(self, codes: str) -> str:
        return guide.explain_codes(codes, self.datadir)

    def explain_analysis(self, analysis: str) -> str:
        return guide.explain_analysis(analysis, self.gloss_table)

    def lookup(self):
        line = self.entry.get().strip()
        if not line or self.session is None or \
                str(self.button['state']) == 'disabled':
            return
        self.history.add(line)
        self.entry.configure(values=self.history.recent())
        self.set_busy(True)
        self.status.config(text=tr('Looking up…'))
        reverse = self.reverse.get()

        def work():
            with self.lock:
                self.session.reverse = reverse
                try:
                    result = self.session.lookup(line)
                except Exception as e:      # show it, keep going
                    result = tr('(error: {error})', error=e)
            self.done.put((self.show, (result, reverse)))
        threading.Thread(target=work, daemon=True).start()

    def show_welcome(self):
        """The welcome text, with examples to click."""
        code = self.session.language.code if self.session else 'en'
        self.results.show_welcome(tr(WELCOME), guide.examples(code))

    def show_results(self, text: str, to_latin: bool):
        self.shown = (text, to_latin)
        plain = self.session is None or \
            self.session.settings.do_pearse_codes   # (another layout)
        self.results.show(text, to_latin, styled=not plain)

    def show(self, result, to_latin=False):
        self.welcome = False
        self.show_results(result.strip('\n') or tr('(no results)'),
                          to_latin)
        self.status.config(text=tr('Ready.'))
        self.set_busy(False)
        self.entry.select_range(0, 'end')
        self.entry.focus_set()

    def edit_dictionary(self):
        """Opens the dictionary editor; after a save, the dictionary is
        loaded again."""
        from words_edit_gui import EditorWindow
        try:
            EditorWindow(self.root, self.datadir, on_save=self.reload,
                         language=self.session.language.code)
        except Exception as e:              # (a bad data file, say)
            messagebox.showerror(NAME, tr('Cannot open the editor:') +
                                 f'\n{e}')

    def reload(self):
        self.set_busy(True)
        self.status.config(text=tr('Loading the dictionary again…'))
        threading.Thread(target=self.load, daemon=True).start()

    def help(self):
        """A window with the help (see guide.py): how to search, and how
        to read the results."""
        if self.session is None:
            return                      # (the dictionary is loading)
        if self.help_window is not None and self.help_window.winfo_exists():
            self.help_window.destroy()  # (made again: the languages may
                                        # have changed)
        win = self.help_window = tk.Toplevel(self.root)
        win.title(tr('{name}: help', name=NAME))
        win.geometry('820x640')
        frame = ttk.Frame(win, padding=(8, 8, 8, 0))
        frame.pack(fill='both', expand=True)
        text = tk.Text(frame, wrap='word', padx=10, pady=8,
                       font='TkDefaultFont', spacing1=2, spacing3=2)
        bar = ttk.Scrollbar(frame, command=text.yview)
        text.config(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        text.pack(side='left', fill='both', expand=True)
        text.tag_config('h', font=self.fonts.bold, spacing1=12,
                        spacing3=4)
        text.tag_config('pre', font=self.fonts.text, lmargin1=16,
                        lmargin2=16)
        text.tag_config('li', lmargin1=8, lmargin2=24)
        with self.lock:
            blocks = guide.blocks(self.session, guide.paragraphs(
                guide.WINDOW) + [guide.configuration()])
        previous = ''
        for kind, body in blocks:
            if previous == 'li' and kind != 'li':
                text.insert('end', '\n')
            if kind == 'li':
                body = '•  ' + body
            text.insert('end', body + ('\n' if kind in ('li', 'h')
                                       else '\n\n'), kind)
            previous = kind
        text.config(state='disabled')
        buttons = ttk.Frame(win, padding=8)
        buttons.pack(fill='x')
        close = ttk.Button(buttons, text=tr('Close'), command=win.destroy)
        close.pack(side='right')
        win.bind('<Escape>', lambda e: win.destroy())
        text.focus_set()

    def about(self):
        """A small window with the credits."""
        win = tk.Toplevel(self.root)
        win.title(tr('About {name}', name=NAME))
        win.transient(self.root)
        frame = ttk.Frame(win, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=about(), justify='left').pack(anchor='w')
        buttons = ttk.Frame(frame, padding=(0, 12, 0, 0))
        buttons.pack(fill='x')
        close = ttk.Button(buttons, text=tr('Close'), command=win.destroy)
        close.pack(side='right')
        ttk.Button(buttons, text=tr('Open the {name} project page',
                                    name=NAME),
                   command=lambda: webbrowser.open(URL)).pack(
                       side='right', padx=(0, 6))
        win.bind('<Escape>', lambda e: win.destroy())
        win.bind('<Return>', lambda e: win.destroy())
        close.focus_set()
        win.resizable(False, False)     # (once its contents are in)
        win.grab_set()

    def set_busy(self, busy):
        self.button.config(state='disabled' if busy else 'normal')
        self.root.config(cursor='watch' if busy else '')


#  The window's class, which desktop files name in StartupWMClass, and its
#  icon
WM_CLASS = 'py-words'
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons',
                        'linux', 'icons', 'hicolor')


def set_icon(root):
    """Gives the window the program's icon, if the icons are there."""
    images = []
    for size in (16, 32, 48, 128, 256):
        path = os.path.join(ICON_DIR, f'{size}x{size}', 'apps',
                            WM_CLASS + '.png')
        try:
            images.append(tk.PhotoImage(file=path))
        except tk.TclError:             # missing, or no PNG support (Tk 8.5)
            pass
    if images:
        root.iconphoto(True, *images)
        root._icons = images            # (Tk does not keep them alive)


def main():
    if sys.platform == 'win32':
        #  So that the taskbar shows the window's icon, not Python's
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                WM_CLASS)
        except (AttributeError, OSError):
            pass
    interface.use_configured()
    root = tk.Tk(className=WM_CLASS)
    interface.translate_tk(root)
    set_icon(root)
    datadir = default_datadir()
    if not os.path.isfile(os.path.join(datadir, DICTIONARY)):
        root.withdraw()
        datadir = filedialog.askdirectory(
            title=tr('Choose the folder containing {file}',
                     file=DICTIONARY))
        if not datadir:
            return
        root.deiconify()
    App(root, datadir)
    root.mainloop()


if __name__ == '__main__':
    main()
