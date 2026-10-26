"""The name, version and credits of this program, and the Python it needs.

This file is read before the rest of the program, so it must stay readable
by old versions of Python.
"""

import os
import re
import subprocess
import sys

NAME = 'py-words'
#  Al subir la versión: también el nombre del zip en los dos README, el
#  título de docs/DESCRIPCIÓN_es.md y las notas de "Version"/"Versiones".
VERSION = '3.3'
URL = 'https://github.com/nivaca/py-words'

HERE = os.path.dirname(os.path.abspath(__file__))
#  The commit the program was made from, written into the zip and the site
#  by bundle-zip.py and pages/build.py (a clone asks git instead)
COMMIT_FILE = 'COMMIT'

#  The credits, with {name}, {version} and {url} for those above
CREDITS_TEXT = (
    '{name} {version}, a Latin dictionary by Nicolas Vaughan\n'
    '{url}\n'
    'Started from WORDS by William Whitaker (1936-2010), in the Ada version\n'
    'at https://github.com/mk270/whitakers-words; code and data redesigned,\n'
    'with a new English dictionary (Lewis and Short) and two new Spanish\n'
    'ones (Echave-Sustaeta and De Miguel).\n'
    'Sources of the dictionary: WORDS, by William Whitaker; R. E. Latham,\n'
    'Revised Medieval Latin Word-List (medieval words, senses and '
    'spellings);\n'
    'J. Echave-Sustaeta, Lengua latina. Vocabulario básico (Latin-'
    'Spanish);\n'
    'C. T. Lewis and C. Short, A Latin Dictionary (rare words and names,\n'
    'English definitions; text of the Perseus Digital Library, CC BY-SA '
    '4.0);\n'
    'R. de Miguel and the Marqués de Morante, Nuevo diccionario latino-\n'
    'español etimológico, 1867 (rare words and proper names, Latin-'
    'Spanish);\n'
    'Collatinus, by Yves Ouvrard and Philippe Verkerk (long vowels).\n'
    'Code © 2026 Nicolas Vaughan (nivaca@fastmail.com), under the GNU '
    'General\n'
    'Public License, version 3 or later (see LICENCE.txt).  The data of '
    'WORDS,\n'
    'by William Whitaker, are free for any use.\n'
    'The Spanish meanings come from De Miguel and Echave-Sustaeta; for the\n'
    'words that neither has, they were translated from the English.  The\n'
    'English meanings of the words taken from De Miguel were translated\n'
    'from his Spanish.')
CREDITS = CREDITS_TEXT.format(name=NAME, version=VERSION, url=URL)

#  A word about the author
AUTHOR = ('Nicolas Vaughan is Associate Professor of Literature at the '
          'School of\nArts and Humanities of the Universidad de los Andes, '
          'Bogotá, Colombia.')

#  The credits with a word about the author, in English
ABOUT = CREDITS + '\n\n' + AUTHOR


def commit(folder=HERE):
    """The commit (its full hash) of the program in FOLDER: that of its
    COMMIT_FILE or, in a clone, git's; None if neither says."""
    try:
        with open(os.path.join(folder, COMMIT_FILE), encoding='ascii') as f:
            text = f.read().strip()
    except (OSError, ValueError):
        text = _git_commit(folder)
    return text if text and re.fullmatch('[0-9a-f]{40}', text) else None


def _git_commit(folder):
    """HEAD of the git repository whose top is FOLDER (not of one that
    only contains it), or None."""
    try:
        out = subprocess.run(
            ['git', '-C', folder, 'rev-parse', '--show-toplevel', 'HEAD'],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except Exception:           # (no git; no processes, as in Pyodide)
        return None
    lines = out.stdout.split('\n')
    if out.returncode != 0 or len(lines) < 2:
        return None
    if os.path.normcase(os.path.realpath(lines[0])) != \
            os.path.normcase(os.path.realpath(folder)):
        return None
    return lines[1].strip()


def about():
    """The credits with a word about the author (the About box,
    --version), in the language of the interface, with the commit after
    the address of the project when it is known."""
    from interface import tr
    lines = tr(CREDITS_TEXT, name=NAME, version=VERSION, url=URL).split('\n')
    hash = commit()
    if hash:
        lines.insert(2, f'Commit: {URL}/commit/{hash}')
    return '\n'.join(lines) + '\n\n' + tr(AUTHOR)


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
