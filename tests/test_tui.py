"""Tests of the full-screen terminal dictionary (words_tui.py), run in a
pseudo-terminal as a person would."""

import os
import select
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP, DOWN, PGDN = '\x1bOA', '\x1bOB', '\x1b[6~'
F5, F8 = '\x1b[15~', '\x1b[19~'
F1, F2, F3, F4, F9, F10 = ('\x1bOP', '\x1bOQ', '\x1bOR', '\x1bOS',
                           '\x1b[20~', '\x1b[21~')


def _pty_available():
    try:
        import pty  # noqa: F401
        import curses  # noqa: F401
        return sys.platform != 'win32'
    except ImportError:
        return False


@unittest.skipUnless(_pty_available(), 'needs a POSIX terminal')
class TerminalDictionaryTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.history = os.path.join(self.tmp.name, 'history')
        self.config = os.path.join(self.tmp.name, 'config')

    def tearDown(self):
        self.tmp.cleanup()

    def run_keys(self, keys, args=(), env=None):
        import fcntl
        import pty
        import struct
        import termios
        pid, fd = pty.fork()
        if pid == 0:
            os.environ.update(TERM='xterm', ESCDELAY='25',
                              PY_WORDS_HISTORY=self.history,
                              PY_WORDS_CONFIG=self.config)
            os.environ.pop('NO_COLOR', None)
            os.environ.update(env or {})
            os.execvp(sys.executable, [sys.executable,
                                       os.path.join(ROOT, 'words_tui.py'),
                                       *args])
        fcntl.ioctl(fd, termios.TIOCSWINSZ,
                    struct.pack('HHHH', 30, 100, 0, 0))
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
        end = time.time() + 15
        while True:
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                break
            if time.time() > end:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
                os.close(fd)
                self.fail('words_tui.py did not quit')
            pump(0.2)
        os.close(fd)
        return status, b''.join(output).decode(errors='replace')

    def test_look_up_and_scroll(self):
        status, out = self.run_keys([
            ('amicorum\r', 1.5),
            ('arma virumque cano Troiae qui primus ab oris\r', 2),
            (PGDN, 0.5), (F10, 1)])
        self.assertEqual(status, 0)
        self.assertIn('amīc-ōrum', out)
        self.assertIn('GEN.PL', out)
        self.assertIn('more ↓', out)            # (a long result scrolls)

    def test_colours(self):
        """The results in colour (the headword red: SGR 31), unless
        $NO_COLOR."""
        status, out = self.run_keys([('amicus\r', 1.5), (F10, 1)])
        self.assertEqual(status, 0)
        self.assertIn('\x1b[31m', out)
        status, out = self.run_keys([('amicus\r', 1.5), (F10, 1)],
                                    env={'NO_COLOR': '1'})
        self.assertIn('amic', out)
        self.assertNotIn('\x1b[31m', out)

    def test_history(self):
        with open(self.history, 'w') as f:
            f.write('laudatus\n')
        status, out = self.run_keys([
            ('amicorum\r', 1.5), (UP + UP + '\r', 1.5), (F10, 1)])
        self.assertEqual(status, 0)
        self.assertIn('laudāt-us', out)         # (from an earlier session)
        with open(self.history) as f:
            self.assertEqual(f.read().split(),
                             ['laudatus', 'amicorum', 'laudatus'])

    def test_clear_history(self):
        with open(self.history, 'w') as f:
            f.write('laudatus\n')
        status, out = self.run_keys([(F9, 0.8), ('y\r', 0.8), (F10, 1)])
        self.assertEqual(status, 0)
        self.assertFalse(os.path.exists(self.history))

    def test_english(self):
        status, out = self.run_keys([(F2, 0.5), ('friend\r', 2), (F10, 1)])
        self.assertEqual(status, 0)
        self.assertIn('English → Latin', out)
        self.assertIn('amicus', out)

    def test_source(self):
        """F8 changes the source to Logeion and back, and keeps it; F2 says
        that Logeion is searched in Latin only, and F4 that the editor is
        not for it.  (Logeion is not asked: see test_logeion.py.)"""
        import tomllib
        status, out = self.run_keys([(F8, 0.8), (F2, 0.8), (F4, 0.8),
                                     (F10, 1)])
        self.assertEqual(status, 0)
        self.assertIn('Searching in Logeion', out)
        self.assertIn('Logeion is searched in Latin only', out)
        self.assertIn('The dictionary editor edits this dictionary, not '
                      'Logeion', out)
        with open(os.path.join(self.config, 'config.toml'), 'rb') as f:
            self.assertEqual(tomllib.load(f)['logeion']['source'],
                             'logeion')
        status, out = self.run_keys([(F8, 0.8), (F10, 1)])
        self.assertIn('Searching in this dictionary.', out)
        with open(os.path.join(self.config, 'config.toml'), 'rb') as f:
            self.assertEqual(tomllib.load(f)['logeion']['source'], 'local')

    def test_direction_kept(self):
        """F2 is kept for the next start."""
        import tomllib
        status, out = self.run_keys([(F2, 0.8), (F10, 1)])
        with open(os.path.join(self.config, 'config.toml'), 'rb') as f:
            self.assertIs(tomllib.load(f)['search']['to_latin'], True)
        status, out = self.run_keys([(F10, 1)])
        self.assertEqual(status, 0)
        self.assertIn('English → Latin', out)

    def test_dictionary_of_logeion(self):
        """With Logeion, F5 chooses its dictionary (kept), not the
        language of the meanings."""
        import tomllib
        status, out = self.run_keys([(F8, 0.8), (F5, 0.8),
                                     (DOWN + '\r', 0.8), (F10, 1)])
        self.assertEqual(status, 0)
        self.assertIn('Dictionary (Enter chooses)', out)
        self.assertIn('Logeion: Lewis & Short.', out)
        with open(os.path.join(self.config, 'config.toml'), 'rb') as f:
            data = tomllib.load(f)['logeion']
        self.assertEqual((data['source'], data['dictionary']),
                         ('logeion', 'ls'))

    def test_language_of_the_meanings(self):
        import tomllib
        import spanish
        data = spanish.datadir(tempfile.mkdtemp(dir=self.tmp.name))
        status, out = self.run_keys([(F5, 1), (DOWN + '\r', 1),
                                     ('est\r', 1.5), (F10, 1)],
                                    ['--datadir', data])
        self.assertEqual(status, 0)
        self.assertIn('Meanings in', out)
        self.assertIn('The meanings are in Spanish.', out)
        self.assertIn('ser; existir;', out)
        with open(os.path.join(self.config, 'config.toml'), 'rb') as f:
            self.assertEqual(tomllib.load(f)['parameters']['language'], 'es')

    def test_settings(self):
        import tomllib
        # Show dictionary forms is the first setting: Space switches it
        # off
        status, out = self.run_keys([(F3, 1), (' ', 0.5), ('\x1b', 0.5),
                                     (F10, 1)])
        self.assertEqual(status, 0)
        self.assertIn('Settings', out)
        with open(os.path.join(self.config, 'config.toml'), 'rb') as f:
            data = tomllib.load(f)
        self.assertIs(data['parameters']['show_dictionary_forms'], False)
        # (the pause stays as saved, for the command line)
        self.assertIs(data['developer']['pause_in_screen_output'], True)

    def test_help_and_editor(self):
        status, out = self.run_keys([(F1, 0.8), ('\x1b', 0.5),
                                     (F4, 2), (F10, 1),     # the editor
                                     (F10, 1)])
        self.assertEqual(status, 0)
        self.assertIn('Help', out)
        self.assertIn('dictionary editor', out)


@unittest.skipUnless(_pty_available(), 'needs curses')
class KeyBarTests(unittest.TestCase):
    def test_help_and_quit_always_shown(self):
        """However narrow the terminal, the last line shows F1 (the help,
        which lists every key) and F10 (quit); the keys between them go
        from the end."""
        import interface
        import words_tui
        before = interface.code()
        self.addCleanup(interface.use, before)
        for code in ('en', 'es'):
            interface.use(code)
            for keys in (words_tui.BAR, words_tui.BAR_LOGEION):
                full = words_tui.key_bar(200, keys)
                self.assertNotIn('F10', full[:-12])
                for width in (40, 60, 79, 99):
                    bar = words_tui.key_bar(width, keys)
                    self.assertLessEqual(len(bar), width)
                    self.assertTrue(bar.startswith('F1 '), bar)
                    self.assertIn('F10 ', bar)
                    self.assertTrue(full.startswith(bar.rsplit('  ', 1)[0]))
        interface.use('en')
        self.assertIn('F5 dictionary',
                      words_tui.key_bar(200, words_tui.BAR_LOGEION))


if __name__ == '__main__':
    unittest.main()
