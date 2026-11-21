"""Corre un programa de pantalla completa de py-words (words_tui.py,
words_edit.py) en una terminal propia (una pty) para las pruebas, teclea
en ella y guarda lo que el programa escribe.

Las esperas son tan cortas como el programa lo permite: al principio,
hasta que READY aparece en la pantalla (o, sin READY, hasta que el
programa la ha dibujado y ha dejado de escribir); tras cada tecla, hasta
que el programa ha respondido y lleva QUIET segundos sin escribir, como
mucho el tiempo dado con la tecla (lo que pueda tardar en responder).  Lo
que se teclea mientras tanto espera en la terminal, y el programa lo lee
en orden.  Al final el programa tiene que salir por sí solo (la última
tecla suele ser la de salir).
"""

import fcntl
import os
import pty
import select
import struct
import termios
import time

#  Segundos sin salida tras los cuales se da por hecho que el programa
#  espera la siguiente tecla
QUIET = 0.15


def run(test, argv: list[str], keys, env: dict, size=(30, 100),
        ready: bytes | None = None, start: float = 60, quit: float = 20,
        name: str = 'the program') -> tuple[int, bytes]:
    """Runs ARGV with ENV in a terminal of SIZE (lines, columns), types
    KEYS ((text, at most seconds), ...), and returns (its exit status,
    what it wrote).  TEST fails if it does not quit within QUIT seconds
    of the last key."""
    pid, fd = pty.fork()
    if pid == 0:                        # (el programa)
        os.environ.update(env)
        os.execvp(argv[0], argv)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', *size, 0, 0))
    output = bytearray()

    def read(timeout: float):
        """Reads what comes within TIMEOUT: True if something came, False
        if nothing, None at the end (the program is gone)."""
        ready_now, _, _ = select.select([fd], [], [], max(0, timeout))
        if not ready_now:
            return False
        try:
            data = os.read(fd, 65536)
        except OSError:
            return None
        if not data:
            return None
        output.extend(data)
        return True

    def settle(first: float):
        """Waits for output (at most FIRST seconds), then until there is
        none for QUIET seconds."""
        end = time.time() + first
        while True:
            got = read(end - time.time())
            if got is None:
                return
            if got:
                break
            if time.time() >= end:
                return
        while read(QUIET):
            pass

    if ready is None:
        settle(start)
    else:
        end = time.time() + start
        while ready not in output and time.time() < end:
            if read(0.5) is None:
                break
        while read(QUIET):
            pass
    for key, wait in keys:
        os.write(fd, key.encode() if isinstance(key, str) else key)
        settle(wait)
    end = time.time() + quit
    while True:
        done, status = os.waitpid(pid, os.WNOHANG)
        if done:
            break
        if time.time() > end:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
            os.close(fd)
            test.fail(f'{name} did not quit: '
                      + bytes(output[-300:]).decode(errors='replace'))
        read(0.2)
    while read(0.05):                   # (what is left)
        pass
    os.close(fd)
    return status, bytes(output)
