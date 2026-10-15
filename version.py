"""The name, version and credits of this program, and the Python it needs.

This file is read before the rest of the program, so it must stay readable
by old versions of Python.
"""

import sys

NAME = 'py-words'
VERSION = '2.0.0'
URL = 'https://github.com/nivaca/py-whitaker-words'

CREDITS = (
    f'{NAME} {VERSION}, a Latin dictionary by Nicolas Vaughan\n'
    f'{URL}\n'
    'Based on WORDS by William Whitaker (1936-2010), via the Ada version at\n'
    'https://github.com/mk270/whitakers-words\n'
    'Code © 2026 Nicolas Vaughan (nivaca@fastmail.com); dictionary data '
    'by\n'
    'William Whitaker, free for any use.')


#  The oldest Python the program runs on
MIN_PYTHON = (3, 11)


def check_python():
    """Stops with a clear message if this Python is too old.  The programs
    (words.py, words_gui.py ...) call this before importing anything that
    needs a recent Python."""
    if sys.version_info < MIN_PYTHON:
        need = '.'.join(map(str, MIN_PYTHON))
        sys.exit(f'{NAME} needs Python {need} or later; this is Python '
                 f'{sys.version.split()[0]}.')
