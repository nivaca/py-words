"""La búsqueda desde un idioma hacia el latín (~E): un índice de las
palabras de los significados de las entradas, en ese idioma.

Cada significado se lee sentido por sentido (los sentidos se separan con
';').  Una frase (separada por ',') sin espacios ("friend", "wild/stormy")
da a sus palabras un rango alto; las palabras tomadas de frases más largas
quedan más abajo, y de estas no se indexan las palabras comunes que dicen
poco de la entrada ("thing", "make", "of" ...).  El texto entre paréntesis
se salta; en "[idiom => translation]" solo se usa la traducción.  Qué
palabras no se indexan nunca ("the", "abb" ...) y cuáles son comunes lo
dice el archivo del idioma (véase languages.py).  Las palabras se
comparan sin mayúsculas ni tildes: "corazon" encuentra "corazón".  Con la
búsqueda aproximada, una palabra que no encuentra nada se busca en sus
grafías cercanas (véase fuzzy.py).
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from functools import cached_property
from typing import NamedTuple

import fuzzy
from languages import Language
from model import Pos, Freq, Entry, pos_fits

SINGLE_WORD_FIRST_SENSE = 15
SINGLE_WORD = 10

_PARENS = re.compile(r'\([^)]*\)?')
_IDIOM = re.compile(r'\[[^\]]*?=>([^\]]*)\]?')
_WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*([.:]?)")


class Hit(NamedTuple):
    """A word found in the meaning of ENTRY."""
    entry: Entry
    sense: int          # 1 for the first sense
    kind: int           # SINGLE_WORD..., o 0 si es de una frase
    rank: int


def fold(word: str) -> str:
    """WORD without capitals and accents, as it is indexed."""
    return ''.join(c for c in unicodedata.normalize('NFD', word.casefold())
                   if not unicodedata.combining(c))


class Words:
    """Which words of a language are indexed."""

    def __init__(self, language: Language):
        self.noise = language.data.noise
        #  palabra -> las clases de palabra cuyas entradas la indexan desde
        #  una frase (una tupla vacía: ninguna)
        keep = {}
        for words, parts in language.data.common:
            for w in words:
                keep.setdefault(w, []).append(parts)
        self.keep = {w: tuple(set.intersection(*(set(k or ())
                                                   for k in keeps)))
                     for w, keeps in keep.items()}

    def is_common(self, word: str, pos: Pos) -> bool:
        keep = self.keep.get(word)
        return keep is not None and pos not in keep


def words_of(meaning: str, pos: Pos, words: Words):
    """(word, sense, kind) for the words of MEANING worth indexing."""
    first = 3 if meaning.startswith('|') else 1
    meaning = _IDIOM.sub(r'\1', meaning.lstrip('|'))
    for sense, text in enumerate(meaning.split(';'), first):
        text = _PARENS.sub(' ', text).replace('"', ' ')
        for place, phrase in enumerate(text.split(',')):
            matches = list(_WORD.finditer(phrase))
            #  ("a friend", "to love": the article or "to" of a definition
            #  does not make it a phrase)
            plain = [w for w in phrase.split()
                     if w.lower() not in ('a', 'an', 'the', 'to')]
            single = bool(matches) and len(plain) == 1
            if single:
                kind = SINGLE_WORD_FIRST_SENSE if sense == 1 else SINGLE_WORD
                kind += place == 0          # (la primera de su sentido)
            else:
                kind = 0
            for m in matches:
                if m.group(1):               # abbreviation ("abb.", "e.g:")
                    continue
                pieces = m.group(0).split('-')
                if len(pieces) > 1:
                    pieces.append(''.join(pieces))
                for word in pieces:
                    if len(word) > 1 and word not in words.noise and \
                            (single or not words.is_common(word, pos)):
                        yield word, sense, kind


def spelled(word: str, meaning: str) -> str:
    """WORD (folded, as the index keeps it) spelled the way MEANING spells
    it: "corazon" -> "corazón"."""
    #  El índice no guarda tildes; se las devolvemos tomándolas del
    #  significado.
    for m in _WORD.finditer(meaning):
        for piece in m.group(0).split('-') + [m.group(0).replace('-', '')]:
            if fold(piece) == word:
                return piece.lower()
    return word


def rank(entry: Entry, sense: int, kind: int) -> int:
    freq = entry.codes.freq
    r = 80 - int(freq) * 10 + kind - 3 * (sense - 1)
    if freq == Freq.N:
        r += 25
    return r


class ReverseIndex:
    def __init__(self, index: dict[str, list[Hit]]):
        self.index = index

    @classmethod
    def build(cls, entries: list[Entry],
              language: Language) -> ReverseIndex:
        """The index of the meanings of ENTRIES in LANGUAGE (those it
        translates)."""
        words = Words(language)
        best: dict[tuple, Hit] = {}
        for entry in entries:
            p = entry.part
            if p.pos == Pos.V and p.decl.which == 8:
                continue                    # las abreviaturas de verbos
            meaning = language.translated(entry)
            if meaning is None:
                continue
            if language.is_reference and meaning != entry.meaning:
                #  (English from Lewis and Short: the meaning of the data
                #  files is searched too)
                meaning = f'{meaning}{entry.meaning.lstrip("|")}'
            for word, sense, kind in words_of(meaning, p.pos, words):
                key = (fold(word), id(entry))
                old = best.get(key)
                if old is None or (kind, -sense) > (old.kind, -old.sense):
                    best[key] = Hit(entry, sense, kind,
                                    rank(entry, sense, kind))
        index = defaultdict(list)
        for (word, _), hit in best.items():
            index[word].append(hit)
        return cls(dict(index))

    def pack(self, entries: list[Entry]) -> dict:
        """The index with entries given by their position in ENTRIES (for
        the cache)."""
        where = {id(e): i for i, e in enumerate(entries)}
        return {word: [(where[id(h.entry)], h.sense, h.kind, h.rank)
                       for h in hits]
                for word, hits in self.index.items()}

    @classmethod
    def unpack(cls, packed: dict, entries: list[Entry]) -> ReverseIndex:
        return cls({word: [Hit(entries[i], sense, kind, rank)
                           for i, sense, kind, rank in hits]
                    for word, hits in packed.items()})

    def search(self, word: str, pos: Pos = Pos.X) -> list[Hit]:
        """The entries whose meaning has WORD, best first."""
        hits = [h for h in self.index.get(fold(word), ())
                if pos_fits(h.entry.part.pos, pos)]
        hits.sort(key=lambda h: (-h.rank, h.entry.codes.freq, h.sense,
                                 h.entry.id))
        return hits

    @cached_property
    def letters(self) -> str:
        """The letters of the indexed words."""
        return ''.join(sorted({c for word in self.index for c in word}))

    def near(self, word: str, pos: Pos = Pos.X, most: int = 3) -> list[str]:
        """The indexed words one change away from WORD that find entries
        (of part of speech POS), at most MOST: those of the best entries,
        and the likeliest mistakes, first."""
        w = fold(word)
        if len(w) < fuzzy.SHORTEST:
            return []
        ranked = []
        for near in fuzzy.edits(w, self.letters):
            hits = self.search(near, pos) if near in self.index else ()
            if hits:
                ranked.append((-hits[0].rank, fuzzy.likely(w, near), near))
        return [near for *_, near in sorted(ranked)[:most]]
