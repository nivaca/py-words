"""The colours of the results in a terminal (words.py and words_tui.py), as
the window shows them (see gui_results.py): the word looked up in bold;
an entry in bold, its first word (the headword) also in red, and its
codes in brackets dimmed; the analysis of a form in blue; the notes and
details dimmed.  Each line is styled by what it is, which the layout of
the results tells (layout.py).

The colours are the terminal's own sixteen (ANSI), so they follow its
light or dark theme.  They are used only where the output is a terminal,
and not if $NO_COLOR is set (https://no-color.org) or $TERM is "dumb";
nor with the Pearse codes (a developer mode), whose lines have another
layout.  words_tui.py turns these ANSI codes into its own attributes.
"""

from __future__ import annotations

import os

from layout import CODES, FORM_LINE, HEADWORD, kind_of

#  The ANSI codes (SGR) of each kind of line, and of what is marked in them
WORD = '1'                      # bold
ENTRY = '1'
HEADWORD_STYLE = '1;31'         # bold red
CODES_STYLE = '2'               # dim
ANALYSIS = '34'                 # blue
NOTE = '2'
#  (the rest of a long line wrapped, by kind: words_tui.py)
KINDS = {'word': WORD, 'entry': ENTRY, 'note': NOTE, 'detail': NOTE,
         'meaning': '', 'form': ANALYSIS, 'blank': ''}


def enabled(stream=None) -> bool:
    """Whether to colour what is written to STREAM (None: only the
    variables of the environment are asked)."""
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
