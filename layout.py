"""La disposición de los resultados (véase render.py): qué es cada línea,
cosa que la ventana (gui_results.py) y la página web (words_web.py)
necesitan saber para disponerla.  Aquí no hay Tk: la página web no lo
tiene.

Las clases de línea, según su sangría: la palabra buscada (sin sangría),
una entrada o una nota (dos espacios), un significado o una forma (cuatro)
y los detalles de debajo (más).  Con los códigos de Pearse (un modo de
desarrollador) las líneas no tienen sangría, y los programas las muestran
tal como vienen.
"""

from __future__ import annotations

import re

FORM_LINE = re.compile(r'( {4})(\S+)( {2,})(\S.*)')     # amic-us   NOM.SG
CODES = re.compile(r'\[([A-Z]{4}[A-Za-z](?:\+[A-Za-z])*)\]')   # [XXXCO+m]
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
        #  (una entrada tiene dos espacios entre sus partes; una nota o la
        #  etiqueta de un truco, como "spelling: Word mod l -> ll", no)
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
