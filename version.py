"""The name, version and credits of this program, and the Python it needs.

This file is read before the rest of the program, so it must stay readable
by old versions of Python.
"""

import sys

NAME = 'py-words'
#  Al subir la versión: también el nombre del zip en los dos README, el
#  título de docs/DESCRIPCIÓN_es.md y las notas de "Version"/"Versiones".
VERSION = '3.1'
URL = 'https://github.com/nivaca/py-words'

#  The credits, with {name}, {version} and {url} for those above
CREDITS_TEXT = (
    '{name} {version}, a Latin dictionary by Nicolas Vaughan\n'
    '{url}\n'
    'Based on WORDS by William Whitaker (1936-2010), via the Ada version at\n'
    'https://github.com/mk270/whitakers-words\n'
    'Sources of the dictionary: WORDS, by William Whitaker; R. E. Latham,\n'
    'Revised Medieval Latin Word-List (medieval words, senses and '
    'spellings);\n'
    'J. Echave-Sustaeta, Lengua latina. Vocabulario básico (Latin-'
    'Spanish);\n'
    'C. T. Lewis and C. Short, A Latin Dictionary (rare words; text of the\n'
    'Perseus Digital Library, CC BY-SA 4.0);\n'
    'R. de Miguel and the Marqués de Morante, Nuevo diccionario latino-\n'
    'español etimológico, 1867 (rare words and proper names, Latin-'
    'Spanish);\n'
    'Collatinus, by Yves Ouvrard and Philippe Verkerk (long vowels).\n'
    'Code © 2026 Nicolas Vaughan (nivaca@fastmail.com), under the GNU '
    'General\n'
    'Public License, version 3 or later (see LICENCE.txt).  The data of '
    'WORDS,\n'
    'by William Whitaker, are free for any use.\n'
    'The Spanish meanings were translated from the English (those of De '
    'Miguel,\n'
    'the other way round) with the help of Claude (the model Claude Opus '
    '5.5,\n'
    'by Anthropic).')
CREDITS = CREDITS_TEXT.format(name=NAME, version=VERSION, url=URL)

#  A word about the author
AUTHOR = ('Nicolas Vaughan is Associate Professor of Literature at the '
          'School of\nArts and Humanities of the Universidad de los Andes, '
          'Bogotá, Colombia.')

#  The credits with a word about the author, in English
ABOUT = CREDITS + '\n\n' + AUTHOR


def about():
    """The credits with a word about the author (the About box,
    --version), in the language of the interface."""
    from interface import tr
    return tr(CREDITS_TEXT, name=NAME, version=VERSION, url=URL) + \
        '\n\n' + tr(AUTHOR)


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
