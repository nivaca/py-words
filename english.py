"""English-to-Latin lookup: an index of the English words in the meanings.

Each meaning is read sense by sense (senses are separated by ';').  A
phrase (separated by ',') with no spaces ("friend", "wild/stormy") gives
its words a high rank; words taken from longer phrases rank lower, and common words that say
little about the entry ("thing", "make", "of" ...) are not indexed from
them.  Text in parentheses is skipped; in "[idiom => translation]" only the
translation is used.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, NamedTuple

from model import Pos, Freq, Entry, pos_fits

#  Never indexed
NOISE = {"DECL", "DAT", "ACC", "ABL", "ADJ", "AD", "BC", "COMP", "SUPER",
         "DEMONST", "INDEF", "INF", "KLUDGE", "NE", "NW", "SE", "SW", "NT",
         "OT", "PASS", "St", "a", "an", "the", "The", "no", "ad", "de", "bi",
         "di", "re", "ex", "abb", "st", "nd", "rd", "th"}

#  Not indexed from a longer phrase, unless the entry is of the part of
#  speech given (None: whatever the part of speech)
COMMON = [
    ({"and", "or", "but", "if"}, (Pos.CONJ,)),
    ({"of", "to", "in", "into", "with", "w", "without", "for", "per", "on",
      "upon", "by", "from", "between", "at", "towards", "under", "before",
      "against", "around", "through", "after", "like", "similar", "than",
      "as"}, (Pos.PREP,)),
    ({"person", "man", "men", "woman", "member", "species", "instrument",
      "word", "words", "parts", "title", "office", "thing", "day", "land",
      "plant", "plants", "tree", "fish", "stone", "stones", "gem", "vessel",
      "pieces", "animal", "bird", "measure", "inhabitant", "place", "tribe",
      "group", "official", "things", "something", "law"}, (Pos.N,)),
    ({"something", "quality", "heap", "amount", "money", "part", "front",
      "preparation", "purpose", "bit", "way", "maker", "material", "action",
      "act", "form", "point", "right", "order", "area", "rest", "cover",
      "Rome", "rome", "praenomen", "gens", "offering", "note", "water",
      "ear", "end", "ritual", "rite", "hair", "time", "charactistic",
      "building", "sea", "ship"}, None),
    ({"some", "several", "another", "male", "legal", "female", "official",
      "no", "wild", "dark", "sacred", "Roman", "roman", "precious", "short",
      "long", "low", "young", "old", "large", "light", "round", "high",
      "near", "little", "small", "more", "military", "many", "suitable",
      "hot", "used", "joint", "proper", "great", "full", "sexual", "public",
      "white", "secret", "hard", "good", "fine", "common"}, (Pos.ADJ,)),
    ({"up", "out", "over", "down", "back", "forth", "foward", "about",
      "together", "off", "much", "throughly", "closly", "well", "very",
      "not", "too", "also", "when", "where", "then", "there", "so"},
     (Pos.ADV,)),
    ({"one", "ones", "he", "any", "anyone", "anything", "each", "every",
      "other", "you", "who", "whatever", "oneself", "self", "all", "it",
      "this", "she", "such", "what", "which", "that", "same"},
     (Pos.PRON, Pos.PACK)),
    ({"kind", "manner", "variety", "its", "own", "his", "ones", "pertaining",
      "belonging", "containing", "consisting", "relating", "resembling",
      "abounding", "concerned", "producing", "connected", "made", "used",
      "having"}, None),
    ({"take", "make", "go", "bring", "cut", "Put", "set", "grow", "give",
      "cause", "turn", "fall", "hold", "keep", "construct", "throw", "lay",
      "remove", "produce", "use", "order", "provide", "being", "making",
      "lacking"}, (Pos.V,)),
    ({"have", "has", "had", "was", "be", "become", "can", "do", "may", "must",
      "let", "is", "been", "begin"}, None),
]

SINGLE_WORD_FIRST_SENSE = 15
SINGLE_WORD = 10

_PARENS = re.compile(r'\([^)]*\)?')
_IDIOM = re.compile(r'\[[^\]]*?=>([^\]]*)\]?')
_WORD = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*([.:]?)")


class Hit(NamedTuple):
    """An English word found in the meaning of ENTRY."""
    entry: Entry
    sense: int          # 1 for the first sense
    kind: int           # SINGLE_WORD..., or 0 for a word of a phrase
    rank: int


#  word -> the parts of speech whose entries index it from a phrase
#  (an empty tuple: none)
_KEEP = {}
for _words, _keep in COMMON:
    for _w in _words:
        _KEEP.setdefault(_w, []).append(_keep)
_KEEP = {w: tuple(set.intersection(*(set(k or ()) for k in keeps)))
         for w, keeps in _KEEP.items()}


def is_common(word: str, pos: Pos) -> bool:
    keep = _KEEP.get(word)
    return keep is not None and pos not in keep


def words_of(meaning: str, pos: Pos):
    """(word, sense, kind) for the English words of MEANING worth
    indexing."""
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
                    if len(word) > 1 and word not in NOISE and \
                            (single or not is_common(word, pos)):
                        yield word, sense, kind


def rank(entry: Entry, sense: int, kind: int) -> int:
    freq = entry.codes.freq
    r = 80 - int(freq) * 10 + kind - 3 * (sense - 1)
    if freq == Freq.N:
        r += 25
    return r


class EnglishIndex:
    def __init__(self, index: Dict[str, List[Hit]]):
        self.index = index

    @classmethod
    def build(cls, entries: List[Entry]) -> 'EnglishIndex':
        best: Dict[tuple, Hit] = {}
        for entry in entries:
            p = entry.part
            if p.pos == Pos.V and p.decl.which == 8:
                continue                    # abbreviations of verb forms
            for word, sense, kind in words_of(entry.meaning, p.pos):
                key = (word.lower(), id(entry))
                old = best.get(key)
                if old is None or (kind, -sense) > (old.kind, -old.sense):
                    best[key] = Hit(entry, sense, kind,
                                    rank(entry, sense, kind))
        index = defaultdict(list)
        for (word, _), hit in best.items():
            index[word].append(hit)
        return cls(dict(index))

    def pack(self, entries: List[Entry]) -> dict:
        """The index with entries given by their position in ENTRIES (for
        the cache)."""
        where = {id(e): i for i, e in enumerate(entries)}
        return {word: [(where[id(h.entry)], h.sense, h.kind, h.rank)
                       for h in hits]
                for word, hits in self.index.items()}

    @classmethod
    def unpack(cls, packed: dict, entries: List[Entry]) -> 'EnglishIndex':
        return cls({word: [Hit(entries[i], sense, kind, rank)
                           for i, sense, kind, rank in hits]
                    for word, hits in packed.items()})

    def search(self, word: str, pos: Pos = Pos.X) -> List[Hit]:
        """The entries whose meaning has WORD, best first."""
        hits = [h for h in self.index.get(word.lower(), ())
                if pos_fits(h.entry.part.pos, pos)]
        hits.sort(key=lambda h: (-h.rank, h.entry.codes.freq, h.sense,
                                 h.entry.id))
        return hits
