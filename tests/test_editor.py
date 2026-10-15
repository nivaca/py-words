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
os.environ['WHITAKERS_WORDS_CACHE'] = ''     # the tests leave the user's cache alone

import xmldata
from editor import Editor, Fields, plain_message

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
DATA_FILES = ('dictionary.xml', 'inflections.xml', 'uniques.xml',
              'addons.xml')

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
        self.assertIn('genitive plural', self.ed.try_word('bloggorum'))
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


def _pty_available():
    try:
        import pty  # noqa: F401
        import termios  # noqa: F401
        return sys.platform != 'win32'
    except ImportError:
        return False


@unittest.skipUnless(_pty_available(), 'needs a POSIX terminal')
class TerminalEditorTests(WithData):
    """Runs words-edit in a pseudo-terminal, as a person would."""

    def run_keys(self, keys):
        import fcntl
        import pty
        import struct
        import termios
        pid, fd = pty.fork()
        if pid == 0:
            os.environ.update(TERM='xterm', ESCDELAY='25')
            os.execvp(sys.executable, [sys.executable,
                                       os.path.join(ROOT, 'words_edit.py'),
                                       '--datadir', self.dir])
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
        _, status = os.waitpid(pid, 0)
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

    def test_quit_without_saving(self):
        status, _ = self.run_keys([('\x0e', 0.5), ('blogg', 0.3),
                                   ('\x11', 1)])
        self.assertEqual(status, 0)
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
            self.assertIn('genitive plural', w.output.get('1.0', 'end'))
            w.save()
        finally:
            w.win.destroy()
        text = self.read()
        self.assertIn('friend (corrected);', text)
        self.assertIn('<stem>blogg</stem>', text)
        self.assertEqual(saved, [1])


if __name__ == '__main__':
    unittest.main()
