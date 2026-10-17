"""Tests of the history of the searches (history.py), in the command line
and the window."""

import os
import select
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

import history  # noqa: E402
from history import History  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class HistoryTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'state', 'history')

    def tearDown(self):
        self.tmp.cleanup()

    def test_kept_between_sessions(self):
        h = History(self.path)
        for line in ('amicorum', 'laudatus', 'laudatus', '  ', 'rem  acu'):
            h.add(line)
        self.assertEqual(h.items, ['amicorum', 'laudatus', 'rem acu'])
        self.assertEqual(History(self.path).items, h.items)   # (read back)

    def test_recent(self):
        h = History(self.path)
        for line in ('a', 'b', 'a', 'c'):
            h.add(line)
        self.assertEqual(h.recent(), ['c', 'a', 'b'])
        self.assertEqual(h.recent(2), ['c', 'a'])

    def test_only_the_last_are_kept(self):
        h = History(self.path)
        for i in range(history.MAX + 10):
            h.add(f'word{i}')
        self.assertEqual(len(h.items), history.MAX)
        self.assertEqual(h.items[0], 'word10')
        self.assertEqual(len(History(self.path).items), history.MAX)

    def test_clear(self):
        h = History(self.path)
        h.add('amicorum')
        h.clear()
        self.assertEqual(h.items, [])
        self.assertFalse(os.path.exists(self.path))
        h.clear()                               # (nothing to clear)

    def test_no_file(self):
        h = History(None)
        h.add('amicorum')
        self.assertEqual(h.items, ['amicorum'])
        os.environ['WHITAKERS_WORDS_HISTORY'], old = '', \
            os.environ['WHITAKERS_WORDS_HISTORY']
        try:
            self.assertIsNone(history.history_path())
        finally:
            os.environ['WHITAKERS_WORDS_HISTORY'] = old

    def test_where(self):
        if sys.platform in ('win32', 'darwin'):
            self.skipTest('Linux folders')
        old = os.environ.pop('WHITAKERS_WORDS_HISTORY')
        try:
            os.environ['XDG_STATE_HOME'] = '/somewhere'
            self.assertEqual(history.history_path(),
                             '/somewhere/py-words/history')
            del os.environ['XDG_STATE_HOME']
            self.assertEqual(history.history_path(), os.path.expanduser(
                '~/.local/state/py-words/history'))
        finally:
            os.environ['WHITAKERS_WORDS_HISTORY'] = old

    def test_unwritable(self):
        with open(os.path.join(self.tmp.name, 'state'), 'w'):
            pass                                # (a file, not a folder)
        h = History(self.path)
        h.add('amicorum')                       # (no error)
        self.assertEqual(h.items, ['amicorum'])


def _pty_available():
    try:
        import pty  # noqa: F401
        import readline  # noqa: F401
        return sys.platform != 'win32'
    except ImportError:
        return False


@unittest.skipUnless(_pty_available(), 'needs a POSIX terminal')
class CommandLineHistoryTests(unittest.TestCase):
    """Up brings back the searches of earlier sessions."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'history')

    def tearDown(self):
        self.tmp.cleanup()

    def session(self, keys):
        import pty
        pid, fd = pty.fork()
        if pid == 0:
            os.environ.update(TERM='xterm',
                              WHITAKERS_WORDS_HISTORY=self.path)
            os.execvp(sys.executable,
                      [sys.executable, os.path.join(ROOT, 'words.py')])
        out = []

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
                    out.append(data)
        pump(3)
        for key in keys:
            os.write(fd, key.encode())
            pump(1)
        os.kill(pid, 9)
        os.waitpid(pid, 0)
        os.close(fd)
        return b''.join(out).decode(errors='replace')

    def test_up(self):
        up = '\x1b[A'
        self.session(['amicorum\r', '#\r', 'n\r', ' \r', 'laudatus\r'])
        # the answers to the # dialogue are not searches
        self.assertEqual(History(self.path).items,
                         ['amicorum', '#', 'laudatus'])
        out = self.session([up + up + up + '\r'])
        self.assertIn('amic-orum', out)


class WindowHistoryTests(unittest.TestCase):

    def setUp(self):
        try:
            import tkinter
            tkinter.Tk().destroy()
        except Exception:
            self.skipTest('needs a display')
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ['WHITAKERS_WORDS_HISTORY']
        os.environ['WHITAKERS_WORDS_HISTORY'] = os.path.join(self.tmp.name,
                                                             'history')

    def tearDown(self):
        os.environ['WHITAKERS_WORDS_HISTORY'] = self.old
        self.tmp.cleanup()

    def test_searches_are_listed(self):
        import gc
        import tkinter as tk
        import words_gui
        History().add('rem acu tetigisti')      # (from the command line)
        root = tk.Tk()
        app = words_gui.App(root, os.path.join(ROOT, 'data'))
        try:
            self.assertEqual(list(app.entry.cget('values')),
                             ['rem acu tetigisti'])
            for _ in range(800):
                if app.session is not None:
                    break
                root.update()
                root.after(25)
            app.entry.insert(0, 'amicorum')
            app.lookup()
            for _ in range(800):
                if 'amic-orum' in app.text.get('1.0', 'end'):
                    break
                root.update()
                root.after(25)
            self.assertEqual(list(app.entry.cget('values')),
                             ['amicorum', 'rem acu tetigisti'])
            self.assertEqual(History().items,
                             ['rem acu tetigisti', 'amicorum'])
            app.clear_history()
            self.assertEqual(list(app.entry.cget('values') or ()), [])
            self.assertEqual(History().items, [])
        finally:
            root.destroy()
            del root, app
            gc.collect()


if __name__ == '__main__':
    unittest.main()
