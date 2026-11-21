"""Los colores de los resultados en una terminal (words.py y words_tui.py),
como los muestra la ventana (véase gui_results.py): la palabra buscada en
negrita; una entrada en negrita, con su primera palabra (el lema) también
en rojo y sus códigos entre corchetes atenuados; el análisis de una forma
en azul; las notas y los detalles atenuados.  Cada línea recibe el estilo
de lo que es, y eso lo dice la disposición de los resultados (layout.py).

Los colores son los dieciséis de la propia terminal (ANSI), así que siguen
su tema claro u oscuro.  Solo se usan cuando la salida es una terminal, y
no si $NO_COLOR está definida (https://no-color.org) o $TERM es "dumb";
tampoco con los códigos de Pearse (un modo de desarrollador), cuyas líneas
tienen otra disposición.  words_tui.py convierte estos códigos ANSI en sus
propios atributos.
"""

from __future__ import annotations

import os

from layout import CODES, FORM_LINE, HEADWORD, kind_of

#  Los códigos ANSI (SGR) de cada clase de línea y de lo que se marca en
#  ella
WORD = '1'                      # en negrita
ENTRY = '1'
HEADWORD_STYLE = '1;31'         # en negrita y rojo
CODES_STYLE = '2'               # dim
ANALYSIS = '34'                 # blue
NOTE = '2'
#  (el resto de una línea larga que se parte, por clase: words_tui.py)
KINDS = {'word': WORD, 'entry': ENTRY, 'note': NOTE, 'detail': NOTE,
         'meaning': '', 'form': ANALYSIS, 'blank': ''}


def enabled(stream=None) -> bool:
    """Whether to colour what is written to STREAM (None: only the
    environment variables are checked)."""
    if os.environ.get('NO_COLOR') or os.environ.get('TERM') == 'dumb':
        return False
    if stream is None:
        return True
    try:
        return stream.isatty()
    except (AttributeError, ValueError):
        return False


def styled(text: str, sgr: str) -> str:
    return f'\033[{sgr}m{text}\033[0m' if sgr and text else text


def line(text: str) -> str:
    """One line of the results, coloured by what it is."""
    kind = kind_of(text)
    if kind == 'entry':
        return _entry(text)
    if kind == 'form':
        m = FORM_LINE.fullmatch(text)
        return m.group(1) + m.group(2) + m.group(3) + \
            styled(m.group(4), ANALYSIS)
    return styled(text, KINDS.get(kind, ''))


def _entry(text: str) -> str:
    """An entry: bold, its headword red, its codes dimmed."""
    spans = []                  # (start, end, codes)
    m = HEADWORD.match(text)
    if m:
        spans.append((m.start(1), m.end(1), HEADWORD_STYLE))
    spans += [(c.start(), c.end(), CODES_STYLE)
              for c in CODES.finditer(text)]
    out, at = [], 0
    for start, end, sgr in sorted(spans):
        out.append(styled(text[at:start], ENTRY))
        out.append(styled(text[start:end], sgr))
        at = end
    out.append(styled(text[at:], ENTRY))
    return ''.join(out)


def results(text: str) -> str:
    """The results TEXT (lines of render.py's layout), coloured."""
    return '\n'.join(line(t) for t in text.split('\n'))
