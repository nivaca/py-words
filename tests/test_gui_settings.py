"""Tests of the window's Settings dialogue (gui_settings.py)."""

import gc
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))), 'data')


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
class SettingsDialogTests(unittest.TestCase):

    def setUp(self):
        import tkinter as tk
        import words_gui
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ['WHITAKERS_WORDS_CONFIG']
        os.environ['WHITAKERS_WORDS_CONFIG'] = self.tmp.name
        self.root = tk.Tk()
        self.app = words_gui.App(self.root, DATA)
        for _ in range(800):            # (the dictionary loads in a thread)
            if self.app.session is not None:
                break
            self.root.update()
            self.root.after(25)
        self.assertIsNotNone(self.app.session)
        self.app.settings_dialog()
        self.dialog = self.app.settings_window

    def tearDown(self):
        self.root.destroy()
        del self.root, self.app, self.dialog
        gc.collect()        # (Tk must be freed here, not by another thread)
        os.environ['WHITAKERS_WORDS_CONFIG'] = self.old
        self.tmp.cleanup()

    def test_language_of_the_meanings(self):
        import spanish
        data = spanish.datadir(tempfile.mkdtemp(dir=self.tmp.name))
        self.app.datadir = data
        self.app.reload()                   # (the folder with Spanish)
        for _ in range(800):
            self.root.update()
            self.root.after(25)
            if 'Spanish' in self.app.language['values']:
                break
        self.assertEqual(self.app.language.get(), 'English')
        self.app.language.set('Spanish')
        self.app.choose_language()
        self.assertEqual(self.app.saved.language, 'es')
        self.assertEqual(self.app.session.language.code, 'es')
        self.assertEqual(self.app.to_latin['text'], 'Spanish → Latin')

    def toggle(self, name):
        var = self.dialog.vars[name]
        var.set(not var.get())
        self.dialog.toggled(name)

    def test_every_setting_is_offered(self):
        from settings import MODES, DEV_MODES, CHARACTERS, ON_SCREEN
        names = set(MODES) | set(DEV_MODES) | {n for _, n in CHARACTERS}
        self.assertEqual(set(self.dialog.vars), names - set(ON_SCREEN))

    def test_a_change_applies_and_is_saved(self):
        import config
        self.toggle('show_examples')
        self.assertTrue(self.app.session.settings.show_examples)
        self.assertIs(config.section('parameters')['show_examples'], True)
        # a change made otherwise shows in the dialogue
        self.app.change_setting('show_examples', False)
        self.assertFalse(self.dialog.vars['show_examples'].get())
        self.toggle('show_entry_source')
        self.assertIs(config.section('developer')['show_entry_source'],
                      True)

    def test_glosses(self):
        """Use glosses, in the dialogue, switches the analyses."""
        app = self.app
        self.assertTrue(self.dialog.vars['use_glosses'].get())
        self.assertIn('GEN.PL', app.session.lookup('amicorum'))
        self.toggle('use_glosses')
        self.assertIn('genitive plural', app.session.lookup('amicorum'))

    def boxes(self):
        """The boxes of the window (not of the dialogue)."""
        def boxes(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == 'TCheckbutton':
                    yield child
                yield from boxes(child)
        return [b for b in boxes(self.root)
                if b.winfo_toplevel() is self.root]

    def test_boxes_in_the_window(self):
        """The settings are in the dialogue, but for "Fuzzy search", beside
        "Meanings in"; and the window has the dark mode button: a moon,
        and a sun while the window is dark."""
        import words_gui
        self.assertEqual([b.cget('text') for b in self.boxes()],
                         ['Fuzzy search', words_gui.MOON])
        self.app.dark.set(True)
        self.assertEqual(self.app.dark_box.cget('text'), words_gui.SUN)
        self.app.dark.set(False)

    def test_fuzzy_search(self):
        """The "Fuzzy search" box changes the setting, and keeps it."""
        import config
        app = self.app
        box = self.boxes()[0]
        self.assertTrue(app.fuzzy.get())
        self.assertIn('(near spellings: amicus)',
                      app.session.lookup('amicuss'))
        box.invoke()
        self.assertFalse(app.session.settings.fuzzy_search)
        self.assertIs(config.section('parameters')['fuzzy_search'], False)
        self.assertNotIn('near spellings', app.session.lookup('amicuss'))
        app.change_setting('fuzzy_search', True)    # (as from elsewhere)
        self.assertTrue(app.fuzzy.get())

    def test_dependent_settings(self):
        box = self.dialog.boxes['medieval_spellings']
        self.assertFalse(box.instate(['disabled']))
        self.toggle('use_tricks')
        self.assertTrue(box.instate(['disabled']))
        self.toggle('use_tricks')
        self.assertFalse(box.instate(['disabled']))

    def test_pause_is_kept_for_the_command_line(self):
        import config
        self.assertFalse(self.app.session.settings.pause_in_screen_output)
        self.assertTrue(self.app.setting('pause_in_screen_output'))
        self.toggle('show_examples')              # saves the parameters
        self.toggle('show_entry_source')          # and the developer modes
        self.assertIs(config.section('developer')['pause_in_screen_output'],
                      True)                     # (not the window's False)
        self.toggle('pause_in_screen_output')
        self.assertIs(config.section('developer')['pause_in_screen_output'],
                      False)
        self.assertFalse(self.app.session.settings.pause_in_screen_output)

    def test_characters(self):
        import gui_settings
        errors = []
        old = gui_settings.messagebox.showerror
        gui_settings.messagebox.showerror = \
            lambda *a, **kw: errors.append(a[1])
        try:
            var = self.dialog.vars['start_file_character']
            var.set('%')
            self.dialog.character('start_file_character')
            self.assertEqual(self.app.setting('start_file_character'), '%')
            var.set('#')                        # (the parameters' one)
            self.dialog.character('start_file_character')
            self.assertEqual(self.app.setting('start_file_character'), '%')
            self.assertEqual(var.get(), '%')
            self.assertEqual(len(errors), 1)
        finally:
            gui_settings.messagebox.showerror = old

    def test_usual_settings(self):
        import gui_settings
        self.toggle('show_examples')
        self.toggle('trim_output')
        old = gui_settings.messagebox.askyesno
        gui_settings.messagebox.askyesno = lambda *a, **kw: True
        try:
            self.dialog.usual()
        finally:
            gui_settings.messagebox.askyesno = old
        self.assertFalse(self.app.setting('show_examples'))
        self.assertTrue(self.app.setting('trim_output'))
        self.assertTrue(self.dialog.vars['trim_output'].get())


if __name__ == '__main__':
    unittest.main()
