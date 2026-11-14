"""Runs a full-screen program of py-words (words_tui.py, words_edit.py)
in a terminal of its own (a pty) for the tests, types keys into it, and
keeps what it writes.

The waits are as short as the program allows: at the start, until READY
is on the screen (or, without READY, until the program has drawn it and
stopped writing); after each key, until the program has answered and
stopped writing for QUIET seconds, at most the time given with the key
(as long as it may take to answer).  What is typed meanwhile waits in the
terminal, and the program reads it in order.  The program must then
quit by itself (the last key is usually its quit key).
"""

import fcntl
import os
import pty
import select
import struct
import termios
import time

#  Seconds without output after which a program is taken to be waiting
#  for the next key
QUIET = 0.15


def run(test, argv: list[str], keys, env: dict, size=(30, 100),
        ready: bytes | None = None, start: float = 60, quit: float = 20,
        name: str = 'the program') -> tuple[int, bytes]:
    """Runs ARGV with ENV in a terminal of SIZE (lines, columns), types
    KEYS ((text, at most seconds), ...), and returns (its exit status,
    what it wrote).  TEST fails if it does not quit within QUIT seconds
    of the last key."""
    pid, fd = pty.fork()
    if pid == 0:                        # (the program)
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
