"""The layout of the results (see render.py): what each line is, as the
window (gui_results.py) and the web page (words_web.py) need to know for
showing it with some order.  No Tk here: the page also runs in the
browser, in Pyodide, which has no Tk.

The kinds, by the indentation of the line: the word looked up (no
indentation), an entry or a note (two spaces), a meaning or a form (four)
and the details below (more).  With the Pearse codes (a developer mode)
the lines have no indentation, and the programs show them as they are.
"""

from __future__ import annotations

import re

FORM_LINE = re.compile(r'( {4})(\S+)( {2,})(\S.*)')     # amic-us   NOM.SG
CODES = re.compile(r'\[([A-Z]{5})\]')
ANALYSIS = re.compile(r'[0-9A-Z]+(?:\.[0-9A-Z]+)*')
HEADWORD = re.compile(r' {2}([^\W\d_][^\s,(]*)')        # amicus, amici ...
WORD = re.compile(r'[^\W\d_]+')


def kind_of(line: str) -> str:
    """What a line of the results is: 'word' (looked up), 'entry', 'note',
    'meaning', 'form', 'detail' or 'blank'."""
    stripped = line.lstrip(' ')
    if not stripped:
        return 'blank'
    indent = len(line) - len(stripped)
    if indent == 0:
        return 'word'
    if indent == 2:
        #  (an entry has two spaces between its parts; a note or the label
        #  of a trick, such as "spelling: Word mod l -> ll", has not)
        if '  ' in stripped and not stripped.startswith('('):
            return 'entry'
        return 'note'
    if indent == 4:
        return 'form' if FORM_LINE.fullmatch(line) else 'meaning'
    return 'detail'


def analysis_of(rest: str) -> str:
    """The analysis in glossing abbreviations at the start of REST (the
    part of a form line after the form), or '' if it is in words."""
    m = ANALYSIS.match(rest)
    if m and any(c.isupper() for c in m.group(0)):
        return m.group(0)
    return ''
