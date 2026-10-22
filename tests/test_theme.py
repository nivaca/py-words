"""Tests of the light and dark look of the windows (gui_theme.py)."""

import gc
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)


def _display():
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')
            or sys.platform in ('win32', 'darwin')):
        return False
    try:
        import tkinter
        tkinter.Tk().destroy()
        return True
    except Exception:
        return False


@unittest.skipUnless(_display(), 'needs a display')
class ThemeTests(unittest.TestCase):

    def setUp(self):
        import tkinter as tk
        import config
        import gui_theme
        self.tk, self.config, self.gui_theme = tk, config, gui_theme
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get('WHITAKERS_WORDS_CONFIG')
        os.environ['WHITAKERS_WORDS_CONFIG'] = self.tmp.name
        self.root = tk.Tk()

    def tearDown(self):
        self.root.destroy()
        del self.root
        gc.collect()        # (Tk must be freed here, not by another thread)
        if self.old is None:
            os.environ.pop('WHITAKERS_WORDS_CONFIG', None)
        else:
            os.environ['WHITAKERS_WORDS_CONFIG'] = self.old
        self.tmp.cleanup()

    def test_dark_and_back(self):
        tk, dark = self.tk, self.gui_theme.DARK
        theme = self.gui_theme.Theme.of(self.root)
        self.assertIs(self.gui_theme.Theme.of(self.root), theme)
        self.assertFalse(theme.dark)
        usual = theme.style.theme_use()
        before = tk.Text(self.root)
        light_bg = before.cget('background')
        theme.set(True)
        self.assertEqual(theme.style.theme_use(), 'clam')
        self.assertEqual(before.cget('background'), dark['field'])
        self.assertEqual(self.root.cget('background'), dark['background'])
        after = tk.Listbox(self.root)           # (made later: the options)
        self.assertEqual(after.cget('background'), dark['field'])
        self.assertEqual(theme.style.lookup('Error.TLabel', 'foreground'),
                         dark['error'])
        self.assertEqual(self.config.section('appearance'),
                         {'dark_mode': True})
        theme.set(False)
        self.assertEqual(theme.style.theme_use(), usual)
        self.assertEqual(before.cget('background'), light_bg)
        self.assertEqual(self.config.section('appearance'),
                         {'dark_mode': False})      # (the web page too)

    def test_kept_for_next_time(self):
        self.config.update('appearance', {'dark_mode': True})
        theme = self.gui_theme.Theme.of(self.root)
        self.assertTrue(theme.dark)
        self.assertEqual(theme.style.theme_use(), 'clam')

    def test_the_box_of_the_main_window(self):
        import words_gui
        app = words_gui.App(self.root, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data'))
        for _ in range(800):                    # (the dictionary loads)
            if app.session is not None:
                break
            self.root.update()
            self.root.after(25)
        boxes = [w for w in self.widgets(self.root)
                 if w.winfo_class() == 'TCheckbutton' and
                 str(w.cget('variable')) == str(app.dark)]
        self.assertEqual(len(boxes), 1)
        boxes[0].invoke()
        self.assertTrue(app.theme.dark)
        self.assertEqual(self.config.section('appearance'),
                         {'dark_mode': True})
        boxes[0].invoke()
        self.assertFalse(app.theme.dark)

    def widgets(self, widget):
        yield widget
        for child in widget.winfo_children():
            yield from self.widgets(child)


if __name__ == '__main__':
    unittest.main()
