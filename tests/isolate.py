"""Imported first by every test module: the tests (and the programs they
run) use no cache and an empty settings folder, so that neither the
user's cache nor their config.toml changes the results, and the tests
change neither.

Their windows are opened, as those of tools/screenshots.py, on an Xvfb
of their own if there is one (out of sight, and the same on every
computer: no scaling or fonts of the desktop), started here once for the
whole run and stopped at its end; the programs the tests run use it too.
Without Xvfb they use the display there is, or are skipped (display()).
$PY_WORDS_TEST_DISPLAY=screen keeps the display there is, to watch them.
"""

import atexit
import os
import shutil
import subprocess
import sys
import tempfile

os.environ['PY_WORDS_CACHE'] = ''
CONFIG = tempfile.mkdtemp(prefix='py-words-config-')
os.environ['PY_WORDS_CONFIG'] = CONFIG
atexit.register(shutil.rmtree, CONFIG, ignore_errors=True)
#  (and the history of the searches is the tests' own)
os.environ['PY_WORDS_HISTORY'] = os.path.join(CONFIG, 'history')

#  The screen of the Xvfb: room for the largest window of the tests
SCREEN = '1600x1200x24'


def _xvfb():
    """Starts an Xvfb and makes it the display of the tests (and of the
    programs they start), if there is one, on systems with X."""
    if sys.platform in ('win32', 'darwin') or \
            os.environ.get('PY_WORDS_TEST_DISPLAY') == 'screen' or \
            not shutil.which('Xvfb'):
        return
    read, write = os.pipe()
    try:
        server = subprocess.Popen(
            ['Xvfb', '-displayfd', str(write), '-screen', '0', SCREEN,
             '-nolisten', 'tcp'], pass_fds=(write,),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        os.close(read)
        os.close(write)
        return
    os.close(write)
    with os.fdopen(read) as f:
        number = f.readline().strip()
    if not number:                      # (it did not start: as without it)
        server.kill()
        server.wait()
        return

    def stop():
        server.terminate()
        try:
            server.wait(5)
        except subprocess.TimeoutExpired:
            server.kill()
    atexit.register(stop)
    os.environ['DISPLAY'] = f':{number}'
    #  (Tk uses X, but GTK programs and the browser would go to Wayland)
    os.environ.pop('WAYLAND_DISPLAY', None)


_xvfb()
_has_display = None


def display() -> bool:
    """Whether windows can be opened (a Tk made and destroyed), for
    unittest.skipUnless."""
    global _has_display
    if _has_display is None:
        _has_display = False
        if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY') \
                or sys.platform in ('win32', 'darwin'):
            try:
                import tkinter
                tkinter.Tk().destroy()
                _has_display = True
            except Exception:
                pass
    return _has_display
