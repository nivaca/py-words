"""The light or dark look of the windows (the dictionary, its settings and
fonts dialogues, the editor).

Dark mode uses Tk's "clam" theme with dark colours; light mode is the
system's usual theme.  The choice is kept for next time in the section
[appearance] of the configuration file (dark_mode = true or false; the
web page, which shares it, follows the system if there is none), and
changes all the open windows at once: the ttk widgets through their
style, the others (texts, lists) through Tk's option database for those
made later and one by one for those already there.

Labels that are not plain text use a style of their own, which follows
the theme: Muted.TLabel (hints, in grey) and Error.TLabel (problems).
"""

import tkinter as tk
from tkinter import font as tkfont, ttk

import config

SECTION = 'appearance'
DARK_THEME = 'clam'

#  The colours of dark mode (as those of the web page's)
DARK = {
    'background': '#242428', 'foreground': '#e8e6e1',
    'field': '#1b1b1d', 'select': '#8a2c1f', 'select_fg': '#ffffff',
    'muted': '#9a9890', 'error': '#ff8a80', 'border': '#3a3a3e',
    'active': '#34343a', 'disabled': '#6b6a66', 'link': '#e8957f',
}
#  Those of the usual look that are not the system's (the links, in the
#  accent of the web page)
LIGHT_MUTED, LIGHT_ERROR, LIGHT_LINK = 'gray', '#b00020', '#8a2c1f'

#  The Tk (not ttk) widgets the option database colours
TK_CLASSES = ('Text', 'Listbox', 'Canvas', 'Toplevel', 'Tk', 'Frame',
              'Menu')


class Theme:
    """The look of one Tk application.  Use `Theme.of(widget)`, which
    makes it once (and applies the saved choice)."""

    @classmethod
    def of(cls, widget) -> 'Theme':
        root = widget._root()
        theme = getattr(root, '_py_words_theme', None)
        if theme is None:
            theme = root._py_words_theme = cls(root)
        return theme

    def __init__(self, root):
        self.root = root
        self.style = ttk.Style(root)
        self.usual_theme = self.style.theme_use()
        self.usual = self._usual_colours()
        self.dark = config.section(SECTION).get('dark_mode') is True
        self.apply()

    def _usual_colours(self) -> dict:
        """The colours of the Tk widgets, as the system gives them."""
        text = tk.Text(self.root)
        listbox = tk.Listbox(self.root)
        try:
            return {
                'background': self.root.cget('background'),
                'field': text.cget('background'),
                'foreground': text.cget('foreground'),
                'insert': text.cget('insertbackground'),
                'select': text.cget('selectbackground'),
                'select_fg': text.cget('selectforeground'),
                'list': listbox.cget('background'),
                'list_fg': listbox.cget('foreground')}
        finally:
            text.destroy()
            listbox.destroy()

    # Choosing ---------------------------------------------------------------

    def set(self, dark: bool):
        """Changes the look, and keeps the choice."""
        self.dark = bool(dark)
        self.apply()
        try:
            config.update(SECTION, {'dark_mode': self.dark})
        except (OSError, config.ConfigError):
            pass                        # (then it lasts for this session)

    # Applying ---------------------------------------------------------------

    def apply(self):
        if self.dark:
            self.style.theme_use(DARK_THEME)
            self._dark_styles()
            colours = self._tk_colours(DARK)
        else:
            self.style.theme_use(self.usual_theme)
            u = self.usual
            colours = {
                'background': u['background'], 'field': u['field'],
                'foreground': u['foreground'], 'insert': u['insert'],
                'select': u['select'], 'select_fg': u['select_fg'],
                'list': u['list'], 'list_fg': u['list_fg']}
        muted, error, link = (DARK['muted'], DARK['error'], DARK['link']) \
            if self.dark else (LIGHT_MUTED, LIGHT_ERROR, LIGHT_LINK)
        self.style.configure('Muted.TLabel', foreground=muted)
        self.style.configure('Error.TLabel', foreground=error)
        self.style.configure('Link.TLabel', foreground=link)
        self.colours = colours
        self._options(colours)
        self._recolour(self.root, colours)
        #  (for what has colours of its own, as the styled results)
        self.root.event_generate('<<ThemeChanged>>', when='tail')

    def _dark_styles(self):
        d = DARK
        s = self.style
        s.configure('.', background=d['background'],
                    foreground=d['foreground'], fieldbackground=d['field'],
                    bordercolor=d['border'], lightcolor=d['border'],
                    darkcolor=d['border'], troughcolor=d['field'],
                    selectbackground=d['select'],
                    selectforeground=d['select_fg'],
                    insertcolor=d['foreground'], arrowcolor=d['foreground'],
                    indicatorbackground=d['field'],
                    indicatorforeground=d['foreground'])
        s.map('.', foreground=[('disabled', d['disabled'])],
              background=[('active', d['active'])])
        s.configure('TButton', background=d['active'])
        s.map('TButton', background=[('pressed', d['border']),
                                     ('active', d['border'])])
        for name in ('TEntry', 'TCombobox', 'TSpinbox'):
            s.map(name, fieldbackground=[('readonly', d['field']),
                                         ('disabled', d['background'])],
                  foreground=[('disabled', d['disabled'])],
                  selectbackground=[('focus', d['select'])])
        #  (clam sets these widgets' own colours, which '.' does not
        #  change; the boxes are sized from the text)
        size = max(10, int(tkfont.nametofont('TkDefaultFont')
                           .metrics('linespace') * 0.7))
        for name in ('TCheckbutton', 'TRadiobutton'):
            s.configure(name, indicatorbackground=d['field'],
                        indicatorforeground=d['foreground'],
                        indicatorsize=size, upperbordercolor=d['border'],
                        lowerbordercolor=d['border'])
            s.map(name, indicatorbackground=[
                ('disabled', d['background']), ('pressed', d['active'])])
        for name in ('TCombobox', 'TSpinbox', 'TScrollbar'):
            s.configure(name, background=d['active'],
                        arrowcolor=d['foreground'], troughcolor=d['field'],
                        bordercolor=d['border'], lightcolor=d['border'],
                        darkcolor=d['border'])
            s.map(name, background=[('active', d['border']),
                                    ('pressed', d['border']),
                                    ('readonly', d['active'])],
                  arrowcolor=[('disabled', d['disabled'])])
        s.configure('TNotebook', background=d['background'])
        s.configure('TNotebook.Tab', background=d['background'])
        s.map('TNotebook.Tab', background=[('selected', d['active'])])

    @staticmethod
    def _tk_colours(d: dict) -> dict:
        return {'background': d['background'], 'field': d['field'],
                'foreground': d['foreground'], 'insert': d['foreground'],
                'select': d['select'], 'select_fg': d['select_fg'],
                'list': d['field'], 'list_fg': d['foreground']}

    def _options(self, c: dict):
        """The colours of the Tk widgets made from now on (also the lists
        of the comboboxes)."""
        add = self.root.option_add
        for cls in ('Toplevel', 'Tk', 'Frame', 'Canvas'):
            add(f'*{cls}.background', c['background'], 'interactive')
        for cls, bg, fg in (('Text', c['field'], c['foreground']),
                            ('Listbox', c['list'], c['list_fg'])):
            add(f'*{cls}.background', bg, 'interactive')
            add(f'*{cls}.foreground', fg, 'interactive')
            add(f'*{cls}.selectBackground', c['select'], 'interactive')
            add(f'*{cls}.selectForeground', c['select_fg'], 'interactive')
        add('*Text.insertBackground', c['insert'], 'interactive')
        add('*Scrollbar.background', c['background'], 'interactive')
        add('*Scrollbar.troughColor', c['field'], 'interactive')
        add('*TCombobox*Listbox.background', c['list'], 'interactive')
        add('*TCombobox*Listbox.foreground', c['list_fg'], 'interactive')
        #  (the menu bar, its menus and the menu of a right click)
        for option, value in self._menu_colours(c).items():
            add(f'*Menu.{option}', value, 'interactive')

    def _menu_colours(self, c: dict) -> dict:
        """The colours of the menus: those of the window, and of a
        selection for the item pointed at."""
        colours = {'background': c['background'],
                   'foreground': c['foreground'],
                   'activeBackground': c['select'],
                   'activeForeground': c['select_fg']}
        if self.dark:
            colours['disabledForeground'] = DARK['disabled']
        return colours

    def _recolour(self, widget, c: dict):
        """The colours of the Tk widgets already there."""
        cls = widget.winfo_class()
        try:
            if cls in ('Tk', 'Toplevel', 'Frame', 'Canvas'):
                widget.configure(background=c['background'])
                if cls == 'Canvas':
                    widget.configure(highlightbackground=c['background'])
            elif cls == 'Text':
                widget.configure(background=c['field'],
                                 foreground=c['foreground'],
                                 insertbackground=c['insert'],
                                 selectbackground=c['select'],
                                 selectforeground=c['select_fg'])
            elif cls == 'Scrollbar':
                widget.configure(background=c['background'],
                                 troughcolor=c['field'],
                                 activebackground=c['background'])
            elif cls == 'Listbox':
                widget.configure(background=c['list'],
                                 foreground=c['list_fg'],
                                 selectbackground=c['select'],
                                 selectforeground=c['select_fg'])
            elif cls == 'Menu':
                widget.configure(**{option.lower(): value for option, value
                                    in self._menu_colours(c).items()})
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._recolour(child, c)
