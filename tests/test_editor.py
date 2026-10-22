"""Tests of the dictionary editors (editor.py, edit_tui.py, edit_gui.py).

They work on a copy of the data files in a temporary directory.
"""

import os
import select
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the package, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

import xmldata
from editor import Editor, Editing, Fields, plain_message

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
DATA_FILES = ('dictionary.xml', 'inflections.xml', 'uniques.xml',
              'addons.xml', 'sources.xml', 'gloss.xml')

BLOGG = Fields('N', {'decl': '2 1', 'gender': 'M', 'kind': 'T',
                     'freq': 'E', 'source': 'Z'},
               ['blogg', 'blogg'], 'blog, online journal;')


class WithData(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        for name in DATA_FILES:
            shutil.copy(os.path.join(DATA, name), self.dir)
        self.path = os.path.join(self.dir, 'dictionary.xml')

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        with open(self.path, encoding='utf-8') as f:
            return f.read()


class EditorTests(WithData):

    def setUp(self):
        super().setUp()
        self.ed = Editor(self.dir)

    def test_search(self):
        found = self.ed.search('amicorum')
        self.assertEqual(found[0].stems[:2], ('amic', 'amic'))
        self.assertTrue(self.ed.search('friend'))
        self.assertEqual(self.ed.search('   '), [])

    def test_options(self):
        decls = dict(self.ed.options('decl', 'N'))
        self.assertTrue(decls['2 1'].startswith('like '))
        self.assertIn(('DEP', 'deponent'), self.ed.options('kind', 'V'))
        self.assertEqual(self.ed.options('value', 'NUM'), [])

    def test_fields_round_trip(self):
        entry = self.ed.search('amicorum')[0]
        again = Fields.of(entry).entry(entry.id)
        self.assertEqual(xmldata.entry_xml(again), xmldata.entry_xml(entry))

    def test_source_names_come_from_sources_xml(self):
        names = dict(self.ed.options('source', 'N'))
        self.assertEqual(names['U'], 'Du Cange')
        self.assertEqual(names['O'], 'Oxford Latin Dictionary')
        path = os.path.join(self.dir, 'sources.xml')
        text = open(path, encoding='utf-8').read()
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text.replace('name="(unused)"', 'name="A new source"'))
        names = dict(Editor(self.dir).options('source', 'N'))
        self.assertEqual(names['A'], 'A new source')
        os.remove(path)                 # without the file: codes only
        names = dict(Editor(self.dir).options('source', 'N'))
        self.assertEqual(names['O'], '')

    def test_change_of_part_of_speech(self):
        f = Fields.of(self.ed.search('amicorum')[0])
        f.set_pos('V')
        self.assertNotIn('gender', f.attrs)
        self.assertEqual(len(f.stem_labels()), 4)

    def test_messages(self):
        self.assertEqual(plain_message('<entry> needs a decl attribute'),
                         'the declension is missing')
        with self.assertRaises(xmldata.DataError) as cm:
            Fields('N', {'decl': '2', 'gender': 'M', 'kind': 'T'},
                   ['x', 'x'], 'y').entry()
        self.assertTrue(cm.exception.message.startswith('the declension'))

    def test_add_try_and_save(self):
        entry = self.ed.add(BLOGG.entry())
        self.assertTrue(self.ed.dirty)
        self.assertEqual(self.ed.describe(entry),
                         'bloggus, bloggi  noun, 2nd declension, masculine')
        self.assertIn('GEN.PL', self.ed.try_word('bloggorum'))
        self.ed.save()
        self.assertFalse(self.ed.dirty)
        self.assertTrue(os.path.exists(self.path + '.bak'))
        self.assertIn('<stem>blogg</stem>', self.read())
        # the saved file is read back as it was written
        self.assertIn('bloggus', Editor(self.dir).describe(
            Editor(self.dir).search('blogg')[0]))

    def test_change_and_delete_leave_the_rest_alone(self):
        with open(self.path, encoding='utf-8') as f:
            original = f.read()
        entry = self.ed.search('amicorum')[0]
        f = Fields.of(entry)
        f.meaning = 'friend (corrected);'
        new = self.ed.replace(entry, f.entry())
        self.ed.save()
        self.assertIn('friend (corrected);', self.read())
        self.ed.replace(new, entry)
        added = self.ed.add(BLOGG.entry())
        self.ed.delete(added)
        self.ed.save()
        self.assertEqual(self.read(), original)


class EditingTests(WithData):
    """What the two editors share (editor.Editing)."""

    def setUp(self):
        super().setUp()
        self.ed = Editor(self.dir)
        self.editing = Editing(self.ed)
        self.amicus = self.editing.find('amicorum')[0]
        self.fields = Fields.of(self.amicus)
        self.editing.start(self.amicus, self.fields)

    def test_pending(self):
        self.assertFalse(self.editing.pending(self.fields))
        self.fields.meaning = 'friend (changed);'
        self.assertTrue(self.editing.pending(self.fields))
        self.assertEqual(self.editing.label(), '“amicus, amici”')

    def test_apply_replaces_the_entry_in_the_results(self):
        n = len(self.editing.results)
        self.fields.meaning = 'friend (changed);'
        entry, done = self.editing.apply(self.fields)
        self.assertEqual(done, 'Changed')
        self.assertIs(self.editing.current, entry)
        self.assertIs(self.editing.results[0], entry)
        self.assertNotIn(self.amicus, self.editing.results)   # (not twice)
        self.assertEqual(len(self.editing.results), n)
        self.assertFalse(self.editing.pending(self.fields))

    def test_leave(self):
        asked = []

        def answer(reply):
            def ask(label):
                asked.append(label)
                return reply
            return ask
        self.assertTrue(self.editing.leave(self.fields, answer(None)))
        self.assertEqual(asked, [])                 # nothing to apply
        self.fields.meaning = 'friend (changed);'
        self.assertFalse(self.editing.leave(self.fields, answer(None)))
        self.assertTrue(self.editing.leave(self.fields, answer(False)))
        self.assertFalse(self.ed.dirty)             # left out
        self.assertTrue(self.editing.leave(self.fields, answer(True)))
        self.assertTrue(self.ed.dirty)              # applied
        self.assertEqual(asked, ['“amicus, amici”'] * 3)
        self.fields.attrs['decl'] = '2'             # cannot be applied
        with self.assertRaises(xmldata.DataError):
            self.editing.leave(self.fields, answer(True))

    def test_new_entry_and_delete(self):
        self.editing.start(None, BLOGG)
        self.assertEqual(self.editing.label(), 'the new entry')
        entry, done = self.editing.apply(BLOGG)
        self.assertEqual(done, 'Added')
        self.assertIs(self.editing.delete(), entry)
        self.assertIsNone(self.editing.current)
        self.assertNotIn(entry, self.editing.results)
        with self.assertRaises(ValueError):
            self.editing.delete()

    def test_save_applies_first(self):
        self.fields.meaning = 'friend (saved);'
        entry, done = self.editing.save(self.fields)
        self.assertEqual(done, 'Changed')
        self.assertIn('<meaning>friend (saved);</meaning>', self.read())
        self.assertIsNone(self.editing.save(self.fields))   # nothing new
        self.fields.attrs['decl'] = '2'
        with self.assertRaises(xmldata.DataError):
            self.editing.save(self.fields)
        self.assertNotIn('decl="2"', self.read())         # not written


def _pty_available():
    try:
        import pty  # noqa: F401
        import termios  # noqa: F401
        return sys.platform != 'win32'
    except ImportError:
        return False


@unittest.skipUnless(_pty_available(), 'needs a POSIX terminal')
class TranslationTests(WithData):
    """Editing the meanings in another language too."""

    def setUp(self):
        super().setUp()
        entries = [e for e, _ in xmldata.read_dictionary(self.path)]
        self.amicus = next(e for e in entries if e.stems[:2] ==
                           ('amic', 'amic') and e.meaning.startswith(
                               'friend, ally'))
        self.last = max(e.uid for e in entries)
        os.mkdir(os.path.join(self.dir, 'languages'))
        self.es = os.path.join(self.dir, 'languages', 'es.xml')
        with open(self.es, 'w', encoding='utf-8') as f:
            f.write(f'''<?xml version="1.0" encoding="UTF-8"?>
<language code="es" name="Spanish" native="Español">
  <noise>el la</noise>
  <text en="noun">sustantivo</text>
  <meaning unique="1">que sean tratados;</meaning>
  <meaning entry="1">a, ab (abr.);</meaning> <!-- A. -->
  <meaning entry="{self.amicus.uid}">amigo, aliado;</meaning> <!-- amicus -->
</language>
''')
        self.ed = Editor(self.dir, 'es')

    def es_text(self):
        with open(self.es, encoding='utf-8') as f:
            return f.read()

    def test_language(self):
        self.assertEqual(self.ed.language_name, 'Spanish')
        self.assertEqual(self.ed.translation(self.amicus), 'amigo, aliado;')
        self.assertEqual(self.ed.fields(self.amicus).translation,
                         'amigo, aliado;')
        found = self.ed.search('amigo')
        self.assertEqual(found[0].uid, self.amicus.uid)
        self.assertIn('amigo, aliado;', self.ed.summary(found[0], 200))
        self.assertIn('amicus, amici  sustantivo',
                      self.ed.describe(self.amicus))
        self.ed.set_language('en')
        self.assertIsNone(self.ed.fields(self.amicus).translation)
        self.assertEqual(Editor(self.dir, 'xx').language, 'en')

    def test_change_add_delete_and_save(self):
        editing = Editing(self.ed)
        editing.find('amicorum')
        amicus = editing.results[0]
        f = self.ed.fields(amicus)
        editing.start(amicus, f)
        f.translation = 'amigo (corregido);'
        self.assertTrue(editing.pending(f))
        editing.apply(f)
        self.assertIn('amigo (corregido);', self.ed.try_word('amicorum'))
        new = Fields(BLOGG.pos, BLOGG.attrs, BLOGG.stems, BLOGG.meaning,
                     'blog, diario en línea;')
        editing.start(None, Fields())
        blogg, done = editing.apply(new)
        self.assertEqual(done, 'Added')
        self.assertEqual(blogg.uid, self.last + 1)
        first = next(e for e in self.ed.entries if e.uid == 1)
        self.ed.delete(first)
        self.ed.save()
        text = self.es_text()
        self.assertIn(f'<meaning entry="{self.amicus.uid}">amigo '
                      '(corregido);</meaning> <!-- amicus, amici -->', text)
        self.assertTrue(text.index(f'entry="{self.amicus.uid}"') <
                        text.index(f'entry="{blogg.uid}"') <
                        text.index('</language>'))
        self.assertIn('blog, diario en línea;</meaning> <!-- bloggus, '
                      'bloggi -->', text)
        self.assertNotIn('entry="1"', text)
        self.assertIn('<meaning unique="1">', text)
        self.assertTrue(os.path.exists(self.es + '.bak'))
        self.assertNotIn('amigo (corregido)', self.read())
        # read back
        self.assertEqual(Editor(self.dir, 'es').translation(blogg),
                         'blog, diario en línea;')

    def test_an_empty_translation_is_taken_out(self):
        amicus = next(e for e in self.ed.entries
                      if e.uid == self.amicus.uid)
        f = self.ed.fields(amicus)
        f.translation = ''
        self.assertIn('there is no meaning in Spanish',
                      ' '.join(self.ed.warnings(self.amicus, '')))
        editing = Editing(self.ed)
        editing.start(amicus, self.ed.fields(amicus))
        editing.save(f)
        self.assertNotIn(f'entry="{self.amicus.uid}"', self.es_text())

    def test_update_language(self):
        changes = {('entry', 2): 'dos;', ('entry', 5): None,
                   ('entry', 1): 'a, ab (abr.);'}
        before = self.es_text()
        xmldata.update_language(self.es, {('entry', 1): 'a, ab (abr.);'})
        self.assertEqual(self.es_text(), before)       # (no change)
        self.assertTrue(xmldata.update_language(self.es, changes))
        text = self.es_text()
        self.assertTrue(text.index('entry="1"') < text.index('entry="2"') <
                        text.index(f'entry="{self.amicus.uid}"'))
        self.assertTrue(xmldata.update_language(self.es,
                                                {('unique', 9): 'nueva;'}))
        self.assertLess(self.es_text().index('unique="1"'),
                        self.es_text().index('unique="9"'))
        xmldata.read_language(self.es)                  # (still good)

    def test_terminal(self):
        """The meaning in Spanish, changed in words_edit.py; then F7 to
        English."""
        down = '\x1bOB'
        keys = [('amigo', 0.3), ('\r', 1.5), ('\r', 0.5)]
        keys += [(down, 0.1)] * 11                      # to the Spanish
        keys += [('\x1bOF', 0.2), (' (terminal)', 0.5),
                 ('\x13', 2),                           # Ctrl-S: save
                 ('\x1b[18~', 1), ('\x1bOA', 0.3),      # F7, up: English
                 ('\r', 1), ('\x11', 1)]                # quit
        status, output = TerminalEditorTests.run_keys(
            self, keys, '--language', 'es')
        self.assertEqual(status, 0, output[-500:])
        self.assertIn(b'meaning in Spanish', output)
        self.assertIn(b'English only', output)
        self.assertIn('amigo, aliado; (terminal)</meaning>', self.es_text())


class TerminalEditorTests(WithData):
    """Runs words-edit in a pseudo-terminal, as a person would."""

    def run_keys(self, keys, *args):
        import fcntl
        import pty
        import struct
        import termios
        pid, fd = pty.fork()
        if pid == 0:
            os.environ.update(TERM='xterm', ESCDELAY='25')
            os.execvp(sys.executable, [sys.executable,
                                       os.path.join(ROOT, 'words_edit.py'),
                                       '--datadir', self.dir, *args])
        fcntl.ioctl(fd, termios.TIOCSWINSZ,
                    struct.pack('HHHH', 30, 110, 0, 0))
        output = []

        def pump(seconds):
            end = time.time() + seconds
            while time.time() < end:
                ready, _, _ = select.select([fd], [], [], 0.05)
                if ready:
                    try:
                        data = os.read(fd, 65536)
                    except OSError:
                        return
                    if not data:
                        return
                    output.append(data)
        pump(4)
        for key, wait in keys:
            os.write(fd, key.encode())
            pump(wait)
        pump(2)
        end = time.time() + 20          # (a prompt left unanswered)
        while True:
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                break
            if time.time() > end:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
                os.close(fd)
                self.fail('the editor did not quit: '
                          + b''.join(output)[-300:].decode(errors='replace'))
            pump(0.2)
        os.close(fd)
        return status, b''.join(output)

    def test_add_an_entry(self):
        down = '\x1bOB'
        keys = [('\x0e', 0.5),                          # Ctrl-N: new
                ('blogg' + down, 0.3), ('blogg' + down, 0.3),
                ('2 1' + down, 0.3), ('M', 0.3), (down + 'T', 0.3)]
        keys += [(down, 0.1)] * 6
        keys += [('blog, online journal;', 0.5),
                 ('\x01', 1.5),                         # Ctrl-A: add
                 ('\x13', 2),                           # Ctrl-S: save
                 ('\x11', 1)]                           # Ctrl-Q: quit
        status, output = self.run_keys(keys)
        self.assertEqual(status, 0, output[-500:])
        self.assertIn('    <stem>blogg</stem>\n    <stem>blogg</stem>\n'
                      '    <meaning>blog, online journal;</meaning>\n',
                      self.read())
        self.assertTrue(os.path.exists(self.path + '.bak'))

    def test_change_an_entry(self):
        """Find an entry of the dictionary, change its meaning, save."""
        down = '\x1bOB'
        keys = [('amicorum', 0.3), ('\r', 1.5),        # find
                ('\r', 0.5)]                            # edit the first
        keys += [(down, 0.1)] * 10                      # to the meaning
        keys += [('\x1bOF', 0.2),                       # End
                 (' (changed)', 0.5),
                 ('\x01', 1.5),                         # Ctrl-A: apply
                 ('\x13', 2),                           # Ctrl-S: save
                 ('\x11', 1)]                           # Ctrl-Q: quit
        status, output = self.run_keys(keys)
        self.assertEqual(status, 0, output[-500:])
        self.assertIn('counselor/courtier (to a prince); (changed)'
                      '</meaning>', self.read())

    def test_save_without_applying(self):
        """F2 straight after changing an entry applies and saves it."""
        down = '\x1bOB'
        keys = [('amicorum', 0.3), ('\r', 1.5), ('\r', 0.5)]
        keys += [(down, 0.1)] * 10
        keys += [('\x1bOF', 0.2), (' (saved directly)', 0.5),
                 ('\x13', 2),                           # Ctrl-S: save
                 ('\x11', 1)]                           # Ctrl-Q: quit
        status, output = self.run_keys(keys)
        self.assertEqual(status, 0, output[-500:])
        self.assertIn('(to a prince); (saved directly)</meaning>',
                      self.read())

    def test_quit_asks_about_changes(self):
        """Quitting with changes not applied asks; y applies them, and the
        save question follows."""
        down = '\x1bOB'
        keys = [('amicorum', 0.3), ('\r', 1.5), ('\r', 0.5)]
        keys += [(down, 0.1)] * 10
        keys += [('\x1bOF', 0.2), (' (on quitting)', 0.5),
                 ('\x11', 1),                           # Ctrl-Q
                 ('y\r', 1),                            # apply them
                 ('y\r', 2)]                            # and save
        status, output = self.run_keys(keys)
        self.assertEqual(status, 0, output[-500:])
        self.assertIn(b'not applied', output)
        self.assertIn('(to a prince); (on quitting)</meaning>', self.read())

    def test_quit_without_saving(self):
        """A new entry typed but not applied: quitting asks about it, and
        n leaves it out."""
        status, output = self.run_keys([('\x0e', 0.5), ('blogg', 0.3),
                                        ('\x11', 1),       # Ctrl-Q
                                        ('n\r', 1)])       # don't apply
        self.assertEqual(status, 0)
        self.assertIn(b'not applied', output)
        self.assertNotIn('blogg', self.read())


def _display():
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return False
    try:
        import tkinter
        tkinter.Tk().destroy()
        return True
    except Exception:
        return False


@unittest.skipUnless(_display(), 'needs a display')
class WindowEditorTests(WithData):

    def test_find_change_add_save(self):
        from words_edit_gui import EditorWindow
        saved = []
        w = EditorWindow(None, self.dir, on_save=lambda: saved.append(1))
        try:
            w.query.insert(0, 'amicorum')
            w.find()
            self.assertTrue(w.listbox.get(0).startswith('amicus, amici'))
            w.vars['meaning'].set('friend (corrected);')
            w.apply()
            w.new()
            for key, value in (('stem0', 'blogg'), ('stem1', 'blogg'),
                               ('decl', '2 1'), ('gender', 'M'),
                               ('meaning', 'blog;')):
                w.vars[key].set(value)
            w.vars['decl'].set('2')
            self.assertIn('declension', w.problems.cget('text'))
            self.assertTrue(w.apply_button.instate(['disabled']))
            w.vars['decl'].set('2 1')
            w.apply()
            w.word.insert(0, 'bloggorum')
            w.try_word()
            self.assertIn('GEN.PL', w.output.get('1.0', 'end'))
            w.save()
        finally:
            w.win.destroy()
        text = self.read()
        self.assertIn('friend (corrected);', text)
        self.assertIn('<stem>blogg</stem>', text)
        self.assertEqual(saved, [1])

    def test_a_changed_entry_is_listed_once(self):
        from words_edit_gui import EditorWindow
        w = EditorWindow(None, self.dir)
        try:
            w.query.insert(0, 'amicorum')
            w.find()
            n = w.listbox.size()
            w.vars['meaning'].set('friend (once);')
            w.apply()
            self.assertEqual(w.listbox.size(), n)
            self.assertIn('friend (once);', w.listbox.get(0))
            self.assertEqual(w.apply_button.cget('text'), 'Apply changes')
            w.new()
            self.assertEqual(w.apply_button.cget('text'),
                             'Add to the dictionary')
        finally:
            w.win.destroy()

    def test_save_applies_the_entry_shown(self):
        """Changing an entry and saving without "Apply changes" keeps the
        change."""
        from words_edit_gui import EditorWindow
        w = EditorWindow(None, self.dir)
        try:
            w.query.insert(0, 'amicorum')
            w.find()
            w.vars['meaning'].set('friend (saved directly);')
            self.assertTrue(w.pending())
            w.save()
            self.assertFalse(w.pending())
            self.assertFalse(w.editor.dirty)
        finally:
            w.win.destroy()
        self.assertIn('<meaning>friend (saved directly);</meaning>',
                      self.read())

    def test_leaving_an_entry_asks(self):
        import words_edit_gui
        from words_edit_gui import EditorWindow
        answers, asked = [], []

        def ask(title, message, **kw):
            asked.append(message)
            return answers.pop(0)
        old = words_edit_gui.messagebox.askyesnocancel
        words_edit_gui.messagebox.askyesnocancel = ask
        w = EditorWindow(None, self.dir)
        try:
            w.query.insert(0, 'amicorum')
            w.find()
            amicus = w.current
            w.vars['meaning'].set('friend (kept);')
            # another entry, cancelled: the form stays as it is
            answers.append(None)
            w.listbox.selection_clear(0, 'end')
            w.listbox.selection_set(1)
            w.select()
            self.assertIs(w.current, amicus)
            self.assertEqual(w.vars['meaning'].get(), 'friend (kept);')
            self.assertIn('Apply the changes to “amicus, amici” first?',
                          asked[0])
            # New, answered yes: the change is applied first
            answers.append(True)
            w.new()
            self.assertIsNone(w.current)
            self.assertTrue(any(e.meaning == 'friend (kept);'
                                for e in w.editor.entries))
            # a new entry left unfinished, answered no: nothing added
            n = len(w.editor.entries)
            w.vars['meaning'].set('something;')
            answers.append(False)
            w.new()
            self.assertEqual(len(w.editor.entries), n)
            # an untouched form asks nothing
            w.new()
            self.assertEqual(len(asked), 3)
        finally:
            words_edit_gui.messagebox.askyesnocancel = old
            w.win.destroy()



@unittest.skipUnless(_display(), 'needs a display')
class WindowTranslationTests(TranslationTests):
    """The window editor with the meanings in Spanish too."""

    test_language = test_change_add_delete_and_save = \
        test_an_empty_translation_is_taken_out = test_update_language = \
        test_terminal = None

    def test_window(self):
        from words_edit_gui import EditorWindow
        w = EditorWindow(None, self.dir, language='es')
        try:
            self.assertEqual(w.language_box.get(), 'Spanish')
            w.query.insert(0, 'amigo')
            w.find()
            self.assertEqual(w.current.uid, self.amicus.uid)
            self.assertEqual(w.vars['translation'].get(), 'amigo, aliado;')
            w.vars['translation'].set('amigo (en la ventana);')
            w.save()
            self.assertIn('amigo (en la ventana);', self.es_text())
            w.language_box.set('English')
            w.choose_language()
            self.assertNotIn('translation', w.vars)
            self.assertFalse(w.editor.translating)
        finally:
            w.win.destroy()



if __name__ == '__main__':
    unittest.main()
