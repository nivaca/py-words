"""Tests of the fonts of the windows (gui_fonts.py)."""

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
class FontTests(unittest.TestCase):

    def setUp(self):
        import tkinter as tk
        from tkinter import font
        import gui_fonts
        self.tk, self.font, self.gui_fonts = tk, font, gui_fonts
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get('WHITAKERS_WORDS_CONFIG')
        os.environ['WHITAKERS_WORDS_CONFIG'] = self.tmp.name
        self.root = tk.Tk()
        self.path = os.path.join(self.tmp.name, 'config.toml')

    def tearDown(self):
        self.root.destroy()
        if self.old is None:
            os.environ.pop('WHITAKERS_WORDS_CONFIG', None)
        else:
            os.environ['WHITAKERS_WORDS_CONFIG'] = self.old
        self.tmp.cleanup()

    def size(self, name):
        return self.font.nametofont(name).cget('size')

    def test_zoom_and_reset(self):
        fonts = self.gui_fonts.Fonts.of(self.root)
        self.assertIs(self.gui_fonts.Fonts.of(self.root), fonts)
        text, ui = fonts.text.cget('size'), self.size('TkDefaultFont')
        self.assertFalse(os.path.exists(self.path))
        fonts.zoom(2)
        self.assertEqual(fonts.text.cget('size'), text + 2)
        self.assertEqual(self.size('TkDefaultFont'), ui + 2)
        self.assertEqual(fonts.entry.cget('size'),
                         ui + 2 + self.gui_fonts.ENTRY_EXTRA)
        import config
        self.assertEqual(config.section('fonts')['text_size'], text + 2)
        fonts.reset()
        self.assertEqual(fonts.text.cget('size'), text)
        self.assertEqual(self.size('TkDefaultFont'), ui)
        self.assertEqual(config.section('fonts'), {})   # all usual again

    def test_sizes_are_limited(self):
        fonts = self.gui_fonts.Fonts.of(self.root)
        fonts.zoom(100)
        self.assertEqual(fonts.text.cget('size'), self.gui_fonts.MAX_SIZE)
        fonts.zoom(-200)
        self.assertEqual(fonts.text.cget('size'), self.gui_fonts.MIN_SIZE)

    def test_saved_choice_is_used(self):
        family = self.font.nametofont('TkFixedFont').actual()['family']
        with open(self.path, 'w') as f:
            f.write(f'[fonts]\ntext_family = "{family}"\ntext_size = 17\n'
                    'ui_size = "big"\n')       # (a bad value is ignored)
        fonts = self.gui_fonts.Fonts.of(self.root)
        self.assertEqual(fonts.text.cget('size'), 17)
        self.assertEqual(fonts.text.cget('family'), family)
        self.assertEqual(fonts.values['ui_size'],
                         fonts.defaults['ui_size'])

    def test_keys(self):
        fonts = self.gui_fonts.Fonts.of(self.root)
        text = fonts.text.cget('size')
        entry = self.tk.Entry(self.root)
        entry.pack()
        entry.focus_force()
        self.root.update()
        mod = 'Command' if sys.platform == 'darwin' else 'Control'
        entry.event_generate(f'<{mod}-plus>')
        self.root.update()
        self.assertEqual(fonts.text.cget('size'), text + 1)
        entry.event_generate(f'<{mod}-0>')
        self.root.update()
        self.assertEqual(fonts.text.cget('size'), text)

    def test_dialog(self):
        fonts = self.gui_fonts.Fonts.of(self.root)
        win = fonts.dialog(self.root)
        for _ in range(20):
            self.root.update()
        # it opens big enough for its contents
        self.assertGreaterEqual(win.winfo_height(),
                                win.winfo_reqheight() - 2)
        self.assertIn(fonts.values['text_family'], fonts.fixed_families())
        win.variables['text_size'].set('15')
        self.assertEqual(fonts.text.cget('size'), 15)
        win.variables['ui_size'].set('')        # (being typed) ignored
        self.assertEqual(fonts.values['text_size'], 15)
        fonts.zoom(1)
        win.refresh()
        self.assertEqual(win.variables['text_size'].get(), '16')
        win.destroy()

    def test_options_are_saved(self):
        import config
        import words_gui
        data = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'data')
        app = words_gui.App(self.root, data)
        for _ in range(400):
            if app.session is not None:
                break
            self.root.update()
            self.root.after(25)
        self.assertIsNotNone(app.session)
        self.assertFalse(app.option_vars['do_examples'].get())
        app.option_vars['do_examples'].set(True)
        app.apply_options()
        self.assertIs(config.section('parameters')['do_examples'], True)
        # the next window starts with it
        self.assertTrue(app.session.settings.do_examples)
        root = self.tk.Tk()
        try:
            again = words_gui.App(root, data)
            for _ in range(400):
                if again.session is not None:
                    break
                root.update()
                root.after(25)
            self.assertTrue(again.option_vars['do_examples'].get())
        finally:
            root.destroy()

    def test_windows_use_the_fonts(self):
        import words_gui
        from words_edit_gui import EditorWindow
        data = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'data')
        app = words_gui.App(self.root, data)
        fonts = self.gui_fonts.Fonts.of(self.root)
        self.assertEqual(str(app.text.cget('font')), str(fonts.text))
        self.assertEqual(str(app.entry.cget('font')), str(fonts.entry))
        editor = EditorWindow(self.root, data)
        self.assertIs(editor.fonts, fonts)
        self.assertEqual(str(editor.output.cget('font')), str(fonts.text))
        editor.win.destroy()


if __name__ == '__main__':
    unittest.main()
