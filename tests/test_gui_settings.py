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

    def toggle(self, name):
        var = self.dialog.vars[name]
        var.set(not var.get())
        self.dialog.toggled(name)

    def test_every_setting_is_offered(self):
        from settings import MODES, DEV_MODES, CHARACTERS
        names = set(MODES) | set(DEV_MODES) | {n for _, n in CHARACTERS}
        self.assertEqual(set(self.dialog.vars), names)

    def test_a_change_applies_and_is_saved(self):
        import config
        self.toggle('do_examples')
        self.assertTrue(self.app.session.settings.do_examples)
        self.assertIs(config.section('parameters')['do_examples'], True)
        # the window's own checkbox follows
        self.assertTrue(self.app.option_vars['do_examples'].get())
        # and the other way round
        self.app.option_vars['do_examples'].set(False)
        self.app.apply_options()
        self.assertFalse(self.dialog.vars['do_examples'].get())
        self.toggle('show_dictionary_line')
        self.assertIs(config.section('developer')['show_dictionary_line'],
                      True)

    def test_dependent_settings(self):
        here = os.getcwd()
        os.chdir(self.tmp.name)                 # (WORD.OUT is made here)
        self.addCleanup(os.chdir, here)
        box = self.dialog.boxes['write_output_to_file']
        self.assertTrue(box.instate(['disabled']))
        self.toggle('have_output_file')
        self.assertFalse(box.instate(['disabled']))
        self.toggle('write_output_to_file')
        self.assertTrue(self.app.setting('write_output_to_file'))
        self.toggle('have_output_file')         # off again: so is this
        self.assertFalse(self.app.setting('write_output_to_file'))
        self.assertTrue(box.instate(['disabled']))
        self.app.session.close()

    def test_pause_is_kept_for_the_command_line(self):
        import config
        self.assertFalse(self.app.session.settings.pause_in_screen_output)
        self.assertTrue(self.app.setting('pause_in_screen_output'))
        self.toggle('do_examples')              # saves the parameters
        self.toggle('show_dictionary')          # and the developer modes
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
        self.toggle('do_examples')
        self.toggle('trim_output')
        old = gui_settings.messagebox.askyesno
        gui_settings.messagebox.askyesno = lambda *a, **kw: True
        try:
            self.dialog.usual()
        finally:
            gui_settings.messagebox.askyesno = old
        self.assertFalse(self.app.setting('do_examples'))
        self.assertTrue(self.app.setting('trim_output'))
        self.assertTrue(self.app.option_vars['trim_output'].get())


if __name__ == '__main__':
    unittest.main()
