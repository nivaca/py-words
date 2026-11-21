"""Lo importa primero cada módulo de pruebas: las pruebas (y los
programas que corren) usan una caché, una carpeta de ajustes y un
historial de búsquedas propios, vacíos al principio, para que ni la caché
del usuario ni su config.toml cambien los resultados, y para que las
pruebas no cambien ninguno de los dos.  Con la caché, el diccionario se
lee de su XML una vez (cerca de un segundo) y de la caché de ahí en
adelante (un cuarto de segundo); tools/test.py, que corre a la vez los
archivos de pruebas, les da a todos la misma ($PY_WORDS_TEST_CACHE).

Sus ventanas se abren, como las de tools/screenshots.py, en un Xvfb
propio si lo hay (fuera de la vista, e iguales en todos los computadores:
sin el escalado ni las fuentes del escritorio), que se arranca aquí una
vez para toda la corrida y se detiene al final; los programas que corren
las pruebas también lo usan.  Sin Xvfb usan la pantalla actual, o se
omiten (display()).  $PY_WORDS_TEST_DISPLAY=screen deja la pantalla
actual, para verlas.
"""

import atexit
import os
import shutil
import subprocess
import sys
import tempfile

CACHE = os.environ.get('PY_WORDS_TEST_CACHE')
if not CACHE:
    CACHE = tempfile.mkdtemp(prefix='py-words-cache-')
    atexit.register(shutil.rmtree, CACHE, ignore_errors=True)
os.environ['PY_WORDS_CACHE'] = CACHE
CONFIG = tempfile.mkdtemp(prefix='py-words-config-')
os.environ['PY_WORDS_CONFIG'] = CONFIG
atexit.register(shutil.rmtree, CONFIG, ignore_errors=True)
#  (y el historial de búsquedas también es el de las pruebas)
os.environ['PY_WORDS_HISTORY'] = os.path.join(CONFIG, 'history')

#  La pantalla del Xvfb: cabe la ventana más grande de las pruebas
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
    if not number:                      # (no arrancó: como si no lo hubiera)
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
