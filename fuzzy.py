"""Grafías cercanas para la búsqueda aproximada (el parámetro
fuzzy_search): lo que se prueba cuando una palabra no encuentra nada tal
como se escribió.

Una grafía cercana está a un cambio de la palabra: una letra que falta,
sobra o cambia, o dos letras vecinas intercambiadas.  Eso cubre la mayoría
de las erratas (amicuss, amcius, puela; freind, recieve) y, en la búsqueda
hacia el latín, también otras formas de la misma palabra (tests, wolfs).
Las palabras de menos de SHORTEST letras se dejan como están, porque casi
toda palabra de dos letras está a un cambio de otra.
"""

from __future__ import annotations

#  Las letras de las palabras latinas, sin j ni v salvo que la palabra las
#  tenga.
#  (Ni j ni v: el léxico ya las busca como i y u, así que probarlas solo
#  daría resultados repetidos.)
LATIN = 'abcdefghiklmnopqrstuxyz'

SHORTEST = 3        # no bajarlo: con 2 salía puro ruido ("is": as, if, in)


def edits(word: str, letters: str) -> set[str]:
    """The spellings one change away from WORD, with LETTERS."""
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    out = {a + b[1:] for a, b in splits if b}
    out |= {a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1}
    out |= {a + c + b[1:] for a, b in splits if b for c in letters}
    out |= {a + c + b for a, b in splits for c in letters}
    out.discard(word)
    return out


def latin_letters(word: str) -> str:
    """The letters to try in the near spellings of the Latin WORD."""
    return LATIN + ''.join(c for c in 'jv' if c in word)


def likely(word: str, near: str) -> int:
    """How usual a mistake NEAR is for WORD: 0 for two letters swapped or
    a letter doubled or undoubled (the commonest), 1 for the rest."""
    if len(near) == len(word) and sorted(near) == sorted(word):
        return 0
    longer, shorter = (near, word) if len(near) > len(word) \
        else (word, near)
    for i in range(len(longer)):
        if longer[:i] + longer[i + 1:] == shorter:
            if longer[i] in longer[max(0, i - 1):i] + longer[i + 1:i + 2]:
                return 0
    return 1
