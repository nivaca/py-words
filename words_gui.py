#!/usr/bin/env python3
"""A window for WORDS: python3 words_gui.py

Type Latin words (or an English word in English-to-Latin mode) and press
Enter; the results are those the command line shows.
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
from tkinter.scrolledtext import ScrolledText

from config import ConfigError
from gui_fonts import Fonts
from gui_settings import SettingsDialog
from history import History
from lexicon import default_datadir
from lexicon import Lexicon, DICTIONARY
from session import Session
from settings import COMMAND_LINE, MODES, Settings
from version import ABOUT, CREDITS, NAME, URL

class App:
    def __init__(self, root, datadir):
        self.root = root
        self.datadir = datadir
        self.session = None
        self.saved = None               # (see ready)
        self.settings_window = None
        self.lock = threading.Lock()
        root.title(f'{NAME}: a Latin dictionary')
        root.geometry('860x620')
        self.fonts = Fonts.of(root)

        top = ttk.Frame(root, padding=(8, 8, 8, 4))
        top.pack(fill='x')
        #  the box where words are typed, with the earlier searches (of
        #  this and earlier sessions, and of the command line) in its list
        self.history = History()
        self.entry = ttk.Combobox(top, font=self.fonts.entry,
                                  values=self.history.recent())
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', lambda e: self.lookup())
        self.entry.bind('<<ComboboxSelected>>', lambda e: self.lookup())
        self.button = ttk.Button(top, text='Look up', command=self.lookup)
        self.button.pack(side='left', padx=(6, 0))

        lang = ttk.Frame(root, padding=(8, 0, 8, 6))
        lang.pack(fill='x')
        self.english = tk.BooleanVar(value=False)
        ttk.Radiobutton(lang, text='Latin → English', value=False,
                        variable=self.english).pack(side='left')
        ttk.Radiobutton(lang, text='English → Latin', value=True,
                        variable=self.english).pack(side='left', padx=(12, 0))
        ttk.Button(lang, text='About', command=self.about).pack(side='right')
        ttk.Button(lang, text='Font…',
                   command=lambda: self.fonts.dialog(root)).pack(
                       side='right', padx=(6, 0))
        ttk.Button(lang, text='Settings…',
                   command=self.settings_dialog).pack(side='right',
                                                      padx=(6, 0))
        ttk.Button(lang, text='Edit dictionary…',
                   command=self.edit_dictionary).pack(side='right', padx=6)
        self.text = ScrolledText(root, wrap='word', font=self.fonts.text,
                                 padx=6, pady=6, state='disabled')
        self.text.pack(fill='both', expand=True, padx=8)
        self.show_text(CREDITS)
        self.status = ttk.Label(root, padding=(8, 2, 8, 6),
                                text='Loading the dictionary…')
        self.status.pack(fill='x')

        self.done = queue.Queue()       # (function, arguments) to call
        self.poll()
        self.set_busy(True)
        threading.Thread(target=self.load, daemon=True).start()

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
            messagebox.showerror(NAME,
                                 f'Could not load the dictionary:\n{error}')
            self.root.destroy()
            return
        self.session = session
        #  the settings as saved, which the window keeps for the command
        #  line (session.settings differ in what the window cannot use)
        self.saved = saved or session.settings.copy()
        self.status.config(text='Ready.')
        self.set_busy(False)
        self.entry.focus_set()

    def setting(self, name):
        return getattr(self.saved, name)

    def change_setting(self, name, value):
        """Changes a setting (a parameter, developer mode or command
        character), applies it, and keeps it in the configuration file."""
        setattr(self.saved, name, value)
        section = 'parameters' if name in MODES else 'developer'
        with self.lock:
            if name not in COMMAND_LINE:
                setattr(self.session.settings, name, value)
            self.session.settings_changed()     # (output files, cache)
            try:
                self.saved.save(section)
            except (OSError, ConfigError) as e:
                self.status.config(text=f'The settings were not saved: {e}')
        if self.settings_window is not None:
            self.settings_window.refresh()
        if self.entry.get().strip():
            self.lookup()

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
            clear_history=self.clear_history)

    def clear_history(self):
        self.history.clear()
        self.entry.configure(values=[])

    def lookup(self):
        line = self.entry.get().strip()
        if not line or self.session is None or \
                str(self.button['state']) == 'disabled':
            return
        self.history.add(line)
        self.entry.configure(values=self.history.recent())
        self.set_busy(True)
        self.status.config(text='Looking up…')
        english = self.english.get()

        def work():
            with self.lock:
                self.session.english = english
                try:
                    result = self.session.lookup(line)
                except Exception as e:      # show it, keep going
                    result = f'(error: {e})'
            self.done.put((self.show, (result,)))
        threading.Thread(target=work, daemon=True).start()

    def show_text(self, text):
        self.text.config(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', text)
        self.text.config(state='disabled')

    def show(self, result):
        self.show_text(result.strip('\n') or '(no results)')
        self.status.config(text='Ready.')
        self.set_busy(False)
        self.entry.select_range(0, 'end')
        self.entry.focus_set()

    def edit_dictionary(self):
        """Opens the dictionary editor; after a save, the dictionary is
        loaded again."""
        from words_edit_gui import EditorWindow
        try:
            EditorWindow(self.root, self.datadir, on_save=self.reload)
        except Exception as e:              # (a bad data file, say)
            messagebox.showerror(NAME, f'Cannot open the editor:\n{e}')

    def reload(self):
        self.set_busy(True)
        self.status.config(text='Loading the dictionary again…')
        threading.Thread(target=self.load, daemon=True).start()

    def about(self):
        """A small window with the credits."""
        win = tk.Toplevel(self.root)
        win.title(f'About {NAME}')
        win.transient(self.root)
        frame = ttk.Frame(win, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=ABOUT, justify='left').pack(anchor='w')
        buttons = ttk.Frame(frame, padding=(0, 12, 0, 0))
        buttons.pack(fill='x')
        close = ttk.Button(buttons, text='Close', command=win.destroy)
        close.pack(side='right')
        ttk.Button(buttons, text=f'Open the {NAME} project page',
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
    root = tk.Tk(className=WM_CLASS)
    set_icon(root)
    datadir = default_datadir()
    if not os.path.isfile(os.path.join(datadir, DICTIONARY)):
        root.withdraw()
        datadir = filedialog.askdirectory(
            title=f'Choose the folder containing {DICTIONARY}')
        if not datadir:
            return
        root.deiconify()
    App(root, datadir)
    root.mainloop()


if __name__ == '__main__':
    main()
