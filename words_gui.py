#!/usr/bin/env python3
"""Una ventana para py-words: python3 words_gui.py [-e] [WORD ...]

Se escriben palabras latinas (o, en la otra dirección, una palabra en el
idioma de los significados) y se pulsa Enter; los resultados son los que
muestra la línea de órdenes.  Las palabras WORD dadas se buscan enseguida
(con -e, hacia el latín).

"Buscar en" ("Search in") elige dónde: Local (el diccionario de este
programa) o Logeion (sus entradas para los lemas de las palabras, véase
logeion.py), que necesita internet; la lista de al lado elige entonces su
diccionario (o todos).
"""

from version import check_python
check_python()          # (antes de los módulos que lo necesitan)

import os
import sys
import queue
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

import guide
import interface
import logeion
from config import ConfigError
from editor import read_only
from gui_fonts import Fonts, scaled, start_tk
from gui_results import Results
from gui_settings import SettingsDialog
from gui_theme import Theme
from history import History
from interface import N_, tr
from lexicon import default_datadir
from lexicon import Lexicon, DICTIONARY
from session import Session, save_to_latin, saved_to_latin
from settings import COMMAND_LINE, Settings, section_of
from version import NAME, URL, VERSION, about

#  El botón del modo oscuro: lo que hace un clic (sin imágenes, solo
#  letras que tienen las fuentes habituales)
MOON = '\u263e'                 # ☾  (make it dark)
SUN = '\u2600'                  # ☀  (make it light)

#  Lo que muestra la ventana hasta la primera búsqueda
WELCOME = N_('Type a Latin word or line, and press Enter.  "Help" explains '
             'the results, and "About" shows the credits.')


def selected(widget) -> bool:
    """Whether WIDGET (an entry or a text) has text selected."""
    try:
        if isinstance(widget, tk.Text):
            return bool(widget.tag_ranges('sel'))
        return isinstance(widget, (tk.Entry, ttk.Entry)) and \
            widget.selection_present()
    except tk.TclError:
        return False


def editable(widget) -> bool:
    """Whether text can be typed in WIDGET (not in the results, nor in a
    list to choose from)."""
    if not isinstance(widget, (tk.Entry, ttk.Entry, tk.Text)):
        return False
    try:
        return str(widget.cget('state')) == 'normal'
    except tk.TclError:
        return False


class App:
    def __init__(self, root, datadir, query: str = '', to_latin=False):
        self.root = root
        self.datadir = datadir
        self.query = (query, to_latin)  # (se busca cuando esté lista)
        self.session = None
        self.saved = None               # (see ready)
        self.settings_window = None
        self.help_window = None
        self.lock = threading.Lock()
        root.geometry(scaled(root, '1000x620'))
        self.fonts = Fonts.of(root)
        self.theme = Theme.of(root)
        #  las búsquedas (de esta sesión y de las anteriores, y de la línea
        #  de órdenes), en la lista del cuadro donde se escriben las palabras
        self.history = History()
        self.languages: dict[str, str] = {}         # name -> code
        #  la dirección: la de las palabras dadas o, si no, la última elegida
        #  (se guarda cuando se elige con sus botones)
        self.reverse = tk.BooleanVar(
            value=to_latin if query.strip() else saved_to_latin())
        self.fuzzy = tk.BooleanVar(value=Settings().fuzzy_search)
        self.source = tk.StringVar(value=logeion.saved_source())
        self.dictionary = logeion.saved_dictionary()    # (its code)
        self.logeion = logeion.Logeion()    # (sus páginas, guardadas)
        self.shown_words = None         # (the results of Logeion shown)
        self.dark = tk.BooleanVar(value=self.theme.dark)
        self.shown = None               # (los resultados, y su dirección)
        self.gloss_table: dict[str, str] = {}
        self.build()
        self.show_source()
        self.welcome = True             # (until the first search)
        self.show_welcome()
        self.status.config(text=tr('Loading the dictionary…'))

        self.done = queue.Queue()       # (función, argumentos) por llamar
        self.poll()
        self.set_busy(True)
        threading.Thread(target=self.load, daemon=True).start()

    def build(self):
        """The widgets of the window, in the language of the interface."""
        root = self.root
        root.title(tr('{name} {version}: A Latin Dictionary', name=NAME,
                      version=VERSION))
        top = ttk.Frame(root, padding=(12, 12, 12, 8))
        top.pack(fill='x')
        self.entry = ttk.Combobox(top, font=self.fonts.entry,
                                  values=self.history.recent())
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', lambda e: self.lookup())
        self.entry.bind('<<ComboboxSelected>>', lambda e: self.lookup())
        self.button = ttk.Button(top, text=tr('Look up'),
                                 style='Accent.TButton', command=self.lookup)
        self.button.pack(side='left', padx=(8, 0), fill='y')

        lang = ttk.Frame(root, padding=(12, 0, 12, 10))
        lang.pack(fill='x')
        #  a la izquierda, la dirección y, debajo, el idioma de los
        #  significados; a la derecha, los botones
        choices = ttk.Frame(lang)
        choices.pack(side='left')
        #  dónde buscar: este diccionario o Logeion
        sources = ttk.Frame(choices)
        sources.pack(anchor='w', pady=(0, 6))
        ttk.Label(sources, text=tr('Search in')).pack(side='left',
                                                      padx=(0, 6))
        for i, source in enumerate(logeion.SOURCES):
            ttk.Radiobutton(sources, text=tr(logeion.NAMES[source]),
                            value=source, variable=self.source,
                            command=self.choose_source
                            ).pack(side='left', padx=(16 if i else 0, 0))
        #  and in Logeion, which dictionary
        names = [logeion.dictionary_name(c) for c in logeion.DICTIONARIES]
        self.dictionaries = ttk.Combobox(
            sources, values=names, state='readonly',
            width=max(map(len, names)))
        self.dictionaries.set(logeion.dictionary_name(self.dictionary))
        self.dictionaries.pack(side='left', padx=(10, 0))
        self.dictionaries.bind('<<ComboboxSelected>>',
                               lambda e: self.choose_dictionary())
        direction = ttk.Frame(choices)
        direction.pack(anchor='w')
        english = tr('English')
        self.to_language = ttk.Radiobutton(
            direction, text=tr('Latin → {language}', language=english),
            value=False, variable=self.reverse, command=self.keep_direction)
        self.to_language.pack(side='left')
        self.to_latin = ttk.Radiobutton(
            direction, text=tr('{language} → Latin', language=english),
            value=True, variable=self.reverse, command=self.keep_direction)
        self.to_latin.pack(side='left', padx=(16, 0))
        #  (las opciones del idioma se conocen una vez cargado el
        #  diccionario)
        meanings = ttk.Frame(choices)
        meanings.pack(anchor='w', pady=(6, 0))
        ttk.Label(meanings, text=tr('Meanings in')).pack(side='left',
                                                         padx=(0, 6))
        self.language = ttk.Combobox(meanings, state='disabled', width=9)
        self.language.pack(side='left')
        self.language.bind('<<ComboboxSelected>>',
                           lambda e: self.choose_language())
        self.fuzzy_box = ttk.Checkbutton(
            meanings, text=tr('Fuzzy search'), variable=self.fuzzy,
            command=self.choose_fuzzy)
        self.fuzzy_box.pack(side='left', padx=(16, 0))
        self.menus()
        #  la línea de estado y la casilla del modo oscuro, abajo (con pack
        #  antes que los resultados, para que sigan ahí cuando la ventana es
        #  pequeña para sus fuentes)
        bottom = ttk.Frame(root, padding=(12, 4, 12, 6))
        bottom.pack(side='bottom', fill='x')
        self.results = Results(root, self.fonts, self.theme, self.look_up,
                               self.explain_codes, self.explain_analysis)
        self.results.pack(fill='both', expand=True, padx=12)
        self.text = self.results.text
        #  el modo oscuro: una luna para oscurecer la ventana, un sol para
        #  aclararla de nuevo (su nombre, en la línea de estado, bajo el ratón)
        self.dark_box = ttk.Checkbutton(bottom, variable=self.dark,
                                        style='Mode.Flat.Toolbutton',
                                        command=self.choose_dark)
        self.dark_box.pack(side='right')
        self.dark.trace_add('write', lambda *a: self.show_dark())
        self.show_dark()
        #  el idioma de la interfaz: su código (EN, ES, LA), a la izquierda
        #  de la luna, que abre la lista de los idiomas, como en la página
        #  web
        self.interface_button = ttk.Button(
            bottom, text=interface.code().upper(),
            style='Lang.Flat.Toolbutton', command=self.interface_menu)
        self.interface_button.pack(side='right', padx=(0, 4))
        self.status = ttk.Label(bottom)
        self.status.pack(side='left', fill='x', expand=True)
        for button, name in ((self.dark_box, N_('Dark mode')),
                             (self.interface_button,
                              N_('Language of the interface'))):
            button.bind('<Enter>', lambda e, n=name: self.name_button(n,
                                                                      True))
            button.bind('<Leave>', lambda e, n=name: self.name_button(n,
                                                                      False))
        root.bind('<<FontsChanged>>', lambda e: self.fit())
        self.fit()

    def menus(self):
        """The menu bar: Dictionary, Edit, View and Help."""
        root = self.root
        bar = tk.Menu(root, tearoff=False)
        key = 'Command' if sys.platform == 'darwin' else 'Ctrl'
        dictionary = tk.Menu(bar, tearoff=False)
        #  (en gris donde los datos no se pueden escribir, como en la
        #  AppImage, y mientras está elegido Logeion: véase show_source)
        dictionary.add_command(
            label=tr('Edit dictionary…'), command=self.edit_dictionary,
            state='disabled' if read_only(self.datadir) else 'normal')
        self.dictionary_menu = dictionary
        dictionary.add_command(label=tr('Settings…'),
                               command=self.settings_dialog)
        dictionary.add_separator()
        dictionary.add_command(label=tr('Quit'), accelerator=f'{key}+Q',
                               command=root.destroy)
        bar.add_cascade(label=tr('Dictionary'), menu=dictionary)
        #  (the keys are Tk's own, in every box of text)
        edit = tk.Menu(bar, tearoff=False)
        edit.config(postcommand=lambda: self.edit_states(edit))
        for name, letter, event in ((N_('Cut'), 'X', '<<Cut>>'),
                                    (N_('Copy'), 'C', '<<Copy>>'),
                                    (N_('Paste'), 'V', '<<Paste>>')):
            edit.add_command(label=tr(name), accelerator=f'{key}+{letter}',
                             command=lambda e=event: self.edit_event(e))
        bar.add_cascade(label=tr('Edit'), menu=edit)
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
        helping.add_command(label=tr('Web page'),
                            command=lambda: webbrowser.open(URL))
        helping.add_command(label=tr('About'), command=self.about)
        bar.add_cascade(label=tr('Help'), menu=helping)
        root.config(menu=bar)
        self.menu_bar = bar
        mod = 'Command' if sys.platform == 'darwin' else 'Control'
        root.bind('<F1>', lambda e: self.help())
        root.bind(f'<{mod}-f>', lambda e: self.find())
        root.bind(f'<{mod}-q>', lambda e: root.destroy())

    # The Edit menu acts on the box with the keyboard's focus (the search
    # box, or the one of "Find in results"), or, for copying, on the
    # results, where text is selected but not typed.

    def edit_widget(self, event: str):
        """The widget that EVENT (<<Cut>>, <<Copy>> or <<Paste>>) would act
        on, or None if it cannot now."""
        try:
            focus = self.root.focus_get()
        except (KeyError, tk.TclError):     # (en la lista de un combobox)
            focus = None
        if event == '<<Copy>>':
            for widget in (focus, self.text):
                if selected(widget):
                    return widget
            return None
        if not editable(focus):
            return None
        if event == '<<Cut>>':
            return focus if selected(focus) else None
        try:
            return focus if self.root.clipboard_get() else None
        except tk.TclError:                 # (the clipboard is empty)
            return None

    def edit_states(self, menu: tk.Menu):
        """Greys out what the Edit menu cannot do now."""
        for i, event in enumerate(('<<Cut>>', '<<Copy>>', '<<Paste>>')):
            menu.entryconfig(i, state='normal' if self.edit_widget(event)
                             else 'disabled')

    def edit_event(self, event: str):
        widget = self.edit_widget(event)
        if widget is not None:
            widget.event_generate(event)

    def choose_dark(self):
        self.theme.set(self.dark.get())
        self.show_dark()

    def show_dark(self):
        """The moon or the sun, larger than the text (each theme has its
        own styles, so this is done again when it changes)."""
        size = tkfont.nametofont('TkDefaultFont').actual('size')
        ttk.Style().configure('Mode.Flat.Toolbutton', padding=(6, 0),
                              font=('TkDefaultFont', round(abs(size) * 1.5)))
        #  el código del idioma, en negrita, de la altura de la luna
        ttk.Style().configure('Lang.Flat.Toolbutton', padding=(6, 2),
                              font=('TkDefaultFont', abs(size), 'bold'))
        self.dark_box.config(text=SUN if self.dark.get() else MOON)

    def name_button(self, name: str, shown: bool):
        """The name of a button of the bottom line (NAME, in English), in
        the status line while the mouse is over it (and what was there,
        after)."""
        if shown:
            self._status_before = self.status.cget('text')
            self.status.config(text=tr(name))
        elif self.status.cget('text') == tr(name):
            self.status.config(text=getattr(self, '_status_before', ''))

    def interface_menu(self):
        """The languages of the interface, each in itself, in a menu over
        the button with the code of the current one; choosing another
        changes the interface (and the window is built again)."""
        if self.session is None:            # (still loading)
            return
        menu = tk.Menu(self.root, tearoff=False)
        current = tk.StringVar(self.root, interface.code())
        for code, name in interface.names().items():
            menu.add_radiobutton(
                label=name, value=code, variable=current,
                command=lambda c=code: self.choose_interface(c))
        menu.update_idletasks()
        button = self.interface_button
        #  (hacia arriba, porque el botón está al pie de la ventana; Tk la
        #  mueve si no cabe)
        menu.tk_popup(button.winfo_rootx(),
                      button.winfo_rooty() - menu.winfo_reqheight())
        menu.grab_release()
        self._interface_var = current       # (Tk keeps only a name)

    def choose_interface(self, code: str):
        if code != interface.code():
            self.change_setting('interface', code)

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
        if self.welcome:
            self.show_welcome()
        elif self.shown_words is not None:
            self.results.show_logeion(self.shown_words, self.dictionary)
        elif self.shown is not None:
            self.show_results(*self.shown)
        else:
            self.show_welcome()
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
        self.show_source()

    # El diccionario se carga, y las palabras se buscan, en un hilo de
    # trabajo, que pasa los resultados a la ventana por una cola (Tk solo
    # se puede usar desde su propio hilo).

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
            settings.pause_in_screen_output = False     # (aquí no se pagina)
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
        #  los ajustes tal como se guardaron, que la ventana conserva para la
        #  línea de órdenes (session.settings difiere en lo que la ventana no
        #  puede usar)
        self.saved = saved or session.settings.copy()
        self.languages = {tr(name): code for code, name in
                          session.lexicon.language_names().items()}
        self.language.config(values=list(self.languages), state='readonly')
        self.show_language()
        self.show_source()
        self.fuzzy.set(self.saved.fuzzy_search)
        self.gloss_table = guide.gloss_table(session)
        if self.welcome:
            self.show_welcome()         # (its examples, in the language)
        self.status.config(text=session.notice or tr('Ready.'))
        self.set_busy(False)
        self.entry.focus_set()
        query, self.query = self.query, ('', False)
        if query[0].strip():
            self.look_up(*query)

    def setting(self, name):
        return getattr(self.saved, name)

    def choose_fuzzy(self):
        """The "Fuzzy search" box (the setting fuzzy_search)."""
        if self.session is None:            # (aún cargando: como estaba)
            self.fuzzy.set(not self.fuzzy.get())
            return
        self.change_setting('fuzzy_search', self.fuzzy.get())

    def change_setting(self, name, value):
        """Changes a setting (a parameter, developer mode, command
        character or language), applies it, and keeps it in the
        configuration file.  The meanings follow the language of the
        interface, if the dictionary has it."""
        if name == 'interface' and not interface.use(value):
            #  (su archivo está mal: como estaba, y diciendo por qué)
            error = interface.error() or value
            interface.use(self.saved.interface)
            self.status.config(text=tr(
                'The language of the interface could not be changed: '
                '{error}', error=error))
            if self.settings_window is not None:
                self.settings_window.refresh()
            return
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

    def keep_direction(self):
        """Keeps the direction chosen with its buttons for the next
        start."""
        error = save_to_latin(self.reverse.get())
        if error:
            self.status.config(text=error)

    def choose_source(self):
        """The choice of "Search in": kept, and the words looked up again
        there."""
        error = logeion.save_source(self.source.get())
        self.show_source()
        if error:
            self.status.config(text=error)
        if self.entry.get().strip():
            self.lookup()

    def show_source(self):
        """What Logeion cannot do (search to Latin, the meanings in a
        language, the fuzzy search), and the dictionary editor, greyed
        out while it is chosen."""
        on = self.source.get() == logeion.LOGEION
        if on:
            self.reverse.set(False)
        #  (el editor edita este diccionario, no el de Logeion)
        self.dictionary_menu.entryconfig(
            0, state='disabled' if on or read_only(self.datadir)
            else 'normal')
        self.dictionaries.config(state='readonly' if on else 'disabled')
        self.to_latin.config(state='disabled' if on else 'normal')
        self.fuzzy_box.config(state='disabled' if on else 'normal')
        if self.session is not None:
            self.language.config(state='disabled' if on else 'readonly')

    def choose_dictionary(self):
        """The dictionary of Logeion chosen: kept, and the results shown
        again with it (Logeion is not asked again)."""
        self.dictionaries.selection_clear()
        names = {logeion.dictionary_name(c): c for c in logeion.DICTIONARIES}
        code = names.get(self.dictionaries.get(), logeion.ALL)
        if code == self.dictionary:
            return
        self.dictionary = code
        error = logeion.save_dictionary(code)
        if error:
            self.status.config(text=error)
        if self.shown_words is not None:
            self.results.show_logeion(self.shown_words, code)

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
        if to_latin and self.source.get() == logeion.LOGEION:
            #  (un ejemplo hacia el latín, que solo hace este diccionario)
            self.source.set(logeion.LOCAL)
            logeion.save_source(logeion.LOCAL)
            self.show_source()
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
        if self.source.get() == logeion.LOGEION:
            self.lookup_logeion(line)
            return
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

    def lookup_logeion(self, line: str):
        """Looks the words of LINE up in Logeion: their lemmas (from the
        analysis here), and then the pages of these (from the internet)."""
        self.status.config(text=tr('Asking Logeion…'))

        def work():
            try:
                with self.lock:
                    words = logeion.queries(self.session, line)
                self.logeion.fetch(words)
            except Exception as e:          # show it, keep going
                self.done.put((self.show, (tr('(error: {error})',
                                              error=e),)))
                return
            self.done.put((self.show_logeion, (words,)))
        threading.Thread(target=work, daemon=True).start()

    def show_logeion(self, words):
        self.welcome = False
        self.shown, self.shown_words = None, words
        self.results.show_logeion(words, self.dictionary)
        self.status.config(text=tr('Ready.'))
        self.set_busy(False)
        self.entry.select_range(0, 'end')
        self.entry.focus_set()

    def show_welcome(self):
        """The welcome text, with examples to click."""
        code = self.session.language.code if self.session else 'en'
        self.results.show_welcome(tr(WELCOME), guide.examples(code))

    def show_results(self, text: str, to_latin: bool):
        self.shown, self.shown_words = (text, to_latin), None
        plain = self.session is None or \
            self.session.settings.pearse_codes   # (otra disposición)
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
        loaded again.  (Not while Logeion is chosen: its menu item is
        greyed out then.)"""
        if self.source.get() == logeion.LOGEION:
            return
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
            return                      # (el diccionario se está cargando)
        if self.help_window is not None and self.help_window.winfo_exists():
            self.help_window.destroy()  # (se hace de nuevo: los idiomas
                                        # pueden haber cambiado)
        win = self.help_window = tk.Toplevel(self.root)
        win.title(tr('{name}: help', name=NAME))
        win.geometry(scaled(win, '820x640'))
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
        self.credits(frame, about())
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

    def credits(self, frame, text):
        """The credits TEXT in FRAME, with the commit (a line 'Commit:
        URL') as a link that shows its short hash."""
        lines = text.split('\n')
        at = next((i for i, line in enumerate(lines)
                   if line.startswith('Commit: ')), None)
        if at is None:
            ttk.Label(frame, text=text, justify='left').pack(anchor='w')
            return
        ttk.Label(frame, text='\n'.join(lines[:at]),
                  justify='left').pack(anchor='w')
        row = ttk.Frame(frame)
        row.pack(anchor='w')
        label, url = lines[at].split(' ', 1)
        ttk.Label(row, text=label).pack(side='left')
        underlined = tkfont.nametofont('TkDefaultFont').copy()
        underlined.config(underline=True)
        link = ttk.Label(row, text=url.rsplit('/', 1)[1][:7],
                         style='Link.TLabel', cursor='hand2', font=underlined)
        link.pack(side='left')
        link.font = underlined          # (se guarda mientras viva la etiqueta)
        link.bind('<Button-1>', lambda e: webbrowser.open(url))
        ttk.Label(frame, text='\n'.join(lines[at + 1:]),
                  justify='left').pack(anchor='w')

    def set_busy(self, busy):
        self.button.config(state='disabled' if busy else 'normal')
        self.root.config(cursor='watch' if busy else '')


#  La clase de la ventana, que los archivos .desktop nombran en
#  StartupWMClass, y su icono
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
        root._icons = images            # (Tk no las mantiene vivas)


def main(argv: list[str] | None = None):
    argv = sys.argv[1:] if argv is None else argv
    to_latin = argv[:1] in (['-e'], ['--english'])
    query = ' '.join(argv[1:] if to_latin else argv)
    if sys.platform == 'win32':
        #  Para que la barra de tareas muestre el icono de la ventana, no el
        #  de Python
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                WM_CLASS)
        except (AttributeError, OSError):
            pass
    interface.use_configured()
    root = start_tk(className=WM_CLASS)
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
    App(root, datadir, query, to_latin)
    root.mainloop()


if __name__ == '__main__':
    main()
