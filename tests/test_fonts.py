"""Tests of the fonts of the windows (gui_fonts.py)."""

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
        del self.root
        gc.collect()        # (Tk must be freed here, not by another thread)
        if self.old is None:
            os.environ.pop('WHITAKERS_WORDS_CONFIG', None)
        else:
            os.environ['WHITAKERS_WORDS_CONFIG'] = self.old
        self.tmp.cleanup()

    def wait_for(self, app, root):
        """Until the window has loaded the dictionary (in a thread, which
        must not outlive the window)."""
        for _ in range(800):
            if app.session is not None:
                return
            root.update()
            root.after(25)
        self.fail('the dictionary was not loaded')

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
        """Ctrl (Command) and + - 0 are bound in every window.  (Which
        window gets a key press is up to the window manager, so the
        bindings are checked, and the handler called, rather than keys
        pressed.)"""
        fonts = self.gui_fonts.Fonts.of(self.root)
        text = fonts.text.cget('size')
        mod = 'Command' if sys.platform == 'darwin' else 'Control'
        for key in ('plus', 'equal', 'KP_Add', 'minus', 'KP_Subtract', '0',
                    'KP_0'):
            self.assertTrue(self.root.bind_all(f'<{mod}-{key}>'), key)
        self.assertEqual(fonts.key(1), 'break')
        self.assertEqual(fonts.text.cget('size'), text + 1)
        fonts.key(-1)
        fonts.key(-1)
        self.assertEqual(fonts.text.cget('size'), text - 1)
        fonts.key(0)
        self.assertEqual(fonts.text.cget('size'), text)

    def test_dialog(self):
        fonts = self.gui_fonts.Fonts.of(self.root)
        self.root.update()      # (a dialogue shows only over a shown window)
        win = fonts.dialog(self.root)
        for _ in range(200):            # (until the window manager shows it)
            self.root.update()
            if win.winfo_ismapped() and \
                    win.winfo_height() >= win.winfo_reqheight() - 2:
                break
            self.root.after(20)
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
        self.wait_for(app, self.root)
        self.assertFalse(app.option_vars['do_examples'].get())
        app.option_vars['do_examples'].set(True)
        app.apply_options()
        self.assertIs(config.section('parameters')['do_examples'], True)
        # the next window starts with it
        self.assertTrue(app.session.settings.do_examples)
        root = self.tk.Tk()
        again = None
        try:
            again = words_gui.App(root, data)
            self.wait_for(again, root)
            self.assertTrue(again.option_vars['do_examples'].get())
        finally:
            root.destroy()
            del again, root
            gc.collect()

    def test_about(self):
        import words_gui
        data = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'data')
        app = words_gui.App(self.root, data)
        self.wait_for(app, self.root)
        before = set(self.root.winfo_children())
        app.about()
        [win] = set(self.root.winfo_children()) - before
        texts = [w.cget('text') for w in win.winfo_children()[0]
                 .winfo_children() if w.winfo_class() == 'TLabel']
        self.assertIn('Universidad de los Andes', texts[0])
        self.assertIn('William Whitaker', texts[0])
        win.destroy()

    def test_windows_use_the_fonts(self):
        import words_gui
        from words_edit_gui import EditorWindow
        data = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'data')
        app = words_gui.App(self.root, data)
        self.wait_for(app, self.root)
        fonts = self.gui_fonts.Fonts.of(self.root)
        self.assertEqual(str(app.text.cget('font')), str(fonts.text))
        self.assertEqual(str(app.entry.cget('font')), str(fonts.entry))
        editor = EditorWindow(self.root, data)
        self.assertIs(editor.fonts, fonts)
        self.assertEqual(str(editor.output.cget('font')), str(fonts.text))
        editor.win.destroy()


if __name__ == '__main__':
    unittest.main()
