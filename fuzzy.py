"""Near spellings for the fuzzy search (the parameter fuzzy_search): what
gets tried when a word finds nothing as typed.

A near spelling is one change away from the word: a letter dropped,
added or changed, or two neighbouring letters swapped.  That covers most
typos (amicuss, amcius, puela; freind, recieve) and, going to Latin, other
forms of the same word too (tests, wolfs).  Words shorter than SHORTEST
are left alone, since almost every two-letter word is one change away
from another ("is": as, if, in).
"""

from __future__ import annotations

#  The letters of Latin words, without j and v unless the word has them.
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
