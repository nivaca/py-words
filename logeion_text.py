"""Limpieza del texto y ancho de presentación en la terminal.

Tomado de py-logeion 0.2.1 (https://github.com/nivaca/py-logeion), cuyo
motor usa py-words para mostrar las entradas de Logeion (véase logeion.py).
"""

from __future__ import annotations

import re
import unicodedata

#  SGR codes and OSC 8 hyperlinks ("\033]8;;URL\033\\" opens one, an empty
#  URL closes it): group 1 is the SGR codes, group 2 the URL
ESC_RE = re.compile(r"\033\[([0-9;]*)m|\033\]8;[^;\033\a]*;([^\033\a]*)(?:\033\\|\a)")
#  Los códigos SGR que apagan otros: 22 la negrita y el tenue, 23 la
#  cursiva, 24 el subrayado, 39 el color
OFF = {22: {1, 2}, 23: {3}, 24: {4}, 39: set(range(30, 38)) | set(range(90, 98))}
_ZERO_WIDTH = "​‌‍‎‏"


def clean_inline(s: str) -> str:
    """Normalise whitespace and spacing around punctuation in extracted text."""
    s = s.replace(" ", " ").replace("‎", "").replace("‏", "")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\( +", "(", s)
    s = re.sub(r" +([),.;:!?])", r"\1", s)
    s = re.sub(r"\[ +", "[", s)
    s = re.sub(r" +\]", "]", s)
    return s.strip()


def strip_ansi(s: str) -> str:
    """S without its colour codes and hyperlinks."""
    return ESC_RE.sub("", s)


def char_width(ch: str) -> int:
    """Terminal columns taken by one character (0, 1 or 2)."""
    if unicodedata.combining(ch) or ch in _ZERO_WIDTH:
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def display_width(s: str) -> int:
    """Terminal columns taken by a string, ignoring ANSI colour codes."""
    return sum(char_width(c) for c in strip_ansi(s))


def styled_segments(line: str) -> list[tuple[str, tuple[int, ...], str | None]]:
    """Split a line with ANSI SGR codes and OSC 8 hyperlinks into (text,
    active codes, link URL or None) runs, e.g. '\\033[1;36mLatin\\033[0m x'
    -> [('Latin', (1, 36), None), (' x', (), None)].  Front ends map the
    codes to their own attributes (curses, Tk tags)."""
    out: list[tuple[str, tuple[int, ...], str | None]] = []
    active: list[int] = []
    url: str | None = None
    pos = 0
    for m in ESC_RE.finditer(line):
        if m.start() > pos:
            out.append((line[pos:m.start()], tuple(active), url))
        if m.group(1) is None:
            url = m.group(2) or None
        else:
            codes = [int(x) for x in m.group(1).split(";") if x] or [0]
            for c in codes:
                if c == 0:
                    active = []
                elif c in OFF:
                    active = [a for a in active if a not in OFF[c]]
                elif c not in active:
                    active.append(c)
        pos = m.end()
    if pos < len(line):
        out.append((line[pos:], tuple(active), url))
    return out

