"""The search from a language to Latin (~E): an index of the words in the
meanings of the entries, in that language.

Each meaning is read sense by sense (senses are separated by ';').  A
phrase (separated by ',') with no spaces ("friend", "wild/stormy") gives
its words a high rank; words taken from longer phrases rank lower, and
common words that say little about the entry ("thing", "make", "of" ...)
are not indexed from them.  Text in parentheses is skipped; in
"[idiom => translation]" only the translation is used.  Which words are
never indexed ("the", "abb" ...) and which are common, the language file
says (see languages.py).  Words are compared without capitals and
accents: "corazon" finds "corazón".  With the fuzzy search, a word that
finds nothing is looked up in its near spellings (see fuzzy.py).
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
    kind: int           # SINGLE_WORD..., or 0 for a word of a phrase
    rank: int


def fold(word: str) -> str:
    """WORD without capitals and accents, as it is indexed."""
    return ''.join(c for c in unicodedata.normalize('NFD', word.casefold())
                   if not unicodedata.combining(c))


class Words:
    """Which words of a language are indexed."""

    def __init__(self, language: Language):
        self.noise = language.data.noise
        #  word -> the parts of speech whose entries index it from a
        #  phrase (an empty tuple: none)
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
        for phrase in text.split(','):
            matches = list(_WORD.finditer(phrase))
            single = bool(matches) and len(phrase.split()) == 1
            if single:
                kind = SINGLE_WORD_FIRST_SENSE if sense == 1 else SINGLE_WORD
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
                continue                    # abbreviations of verb forms
            meaning = language.translated(entry)
            if meaning is None:
                continue
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
