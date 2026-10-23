"""The grammatical vocabulary of WORDS and the records built from it.

The codes (N, ADJ, NOM, PRES, ...) are those used in the data files.  Every
enumeration has an X member meaning "unknown" or "any", which is also the
default.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum
from typing import NamedTuple


class Pos(IntEnum):
    """Part of speech."""
    X = 0
    N = 1          # noun
    PRON = 2       # pronoun
    PACK = 3       # pronoun that takes a tackon (qui -> quicumque)
    ADJ = 4
    NUM = 5
    ADV = 6
    V = 7
    VPAR = 8       # participle
    SUPINE = 9
    PREP = 10
    CONJ = 11
    INTERJ = 12
    TACKON = 13
    PREFIX = 14
    SUFFIX = 15


class Gender(IntEnum):
    X = 0
    M = 1
    F = 2
    N = 3
    C = 4          # common: masculine or feminine


class Case(IntEnum):
    X = 0
    NOM = 1
    VOC = 2
    GEN = 3
    LOC = 4
    DAT = 5
    ABL = 6
    ACC = 7


class Number(IntEnum):
    X = 0
    S = 1
    P = 2


class Comparison(IntEnum):
    X = 0
    POS = 1
    COMP = 2
    SUPER = 3


class NumeralSort(IntEnum):
    X = 0
    CARD = 1
    ORD = 2
    DIST = 3
    ADVERB = 4


class Tense(IntEnum):
    X = 0
    PRES = 1
    IMPF = 2
    FUT = 3
    PERF = 4
    PLUP = 5
    FUTP = 6


class Voice(IntEnum):
    X = 0
    ACTIVE = 1
    PASSIVE = 2


class Mood(IntEnum):
    X = 0
    IND = 1
    SUB = 2
    IMP = 3
    INF = 4
    PPL = 5


class NounKind(IntEnum):
    X = 0
    S = 1          # singular only
    M = 2          # plural or multiple
    A = 3          # abstract idea
    G = 4          # group or collective
    N = 5          # proper name
    P = 6          # a person
    T = 7          # a thing
    L = 8          # a place
    W = 9          # where (a locative-like place)


class PronounKind(IntEnum):
    X = 0
    PERS = 1
    REL = 2
    REFLEX = 3
    DEMONS = 4
    INTERR = 5
    INDEF = 6
    ADJECT = 7


class VerbKind(IntEnum):
    X = 0
    TO_BE = 1
    TO_BEING = 2
    GEN = 3
    DAT = 4
    ABL = 5
    TRANS = 6
    INTRANS = 7
    IMPERS = 8
    DEP = 9
    SEMIDEP = 10
    PERFDEF = 11


class Age(IntEnum):
    X = 0
    A = 1          # archaic
    B = 2          # early
    C = 3          # classical
    D = 4          # late
    E = 5          # later
    F = 6          # medieval
    G = 7          # scholarly
    H = 8          # modern


class Freq(IntEnum):
    X = 0
    A = 1          # very frequent
    B = 2
    C = 3
    D = 4
    E = 5
    F = 6          # very rare
    I = 7          # inscriptions only
    M = 8          # graffiti only
    N = 9          # Pliny only


class Area(IntEnum):
    X = 0
    A = 1
    B = 2
    D = 3
    E = 4
    G = 5
    L = 6
    P = 7
    S = 8
    T = 9
    W = 10
    Y = 11


class Geo(IntEnum):
    X = 0
    A = 1
    B = 2
    C = 3
    D = 4
    E = 5
    F = 6
    G = 7
    H = 8
    I = 9
    J = 10
    K = 11
    N = 12
    P = 13
    Q = 14
    R = 15
    S = 16
    U = 17


class Source(IntEnum):
    X = 0
    A = 1
    B = 2
    C = 3
    D = 4
    E = 5
    F = 6
    G = 7
    H = 8
    I = 9
    J = 10
    K = 11
    L = 12
    M = 13
    N = 14
    O = 15
    P = 16
    Q = 17
    R = 18
    S = 19
    T = 20
    U = 21
    V = 22
    W = 23
    Y = 24
    Z = 25


Kind = NounKind | PronounKind | VerbKind | None


class Decl(NamedTuple):
    """A declension or conjugation and its variant, as in "2 1".  Zeros are
    wildcards: "0 0" is any (but 9), "3 0" any variant of the third."""
    which: int = 0
    var: int = 0

    def __str__(self):
        return f'{self.which} {self.var}'

    def fits(self, pattern: Decl) -> bool:
        """Whether this declension is one that PATTERN describes."""
        return pattern == self or pattern == (self.which, 0) or \
            (pattern == (0, 0) and self.which != 9)


ANY_DECL = Decl(0, 0)


def gender_fits(gender: Gender, pattern: Gender) -> bool:
    return pattern in (gender, Gender.X) or \
        (pattern == Gender.C and gender in (Gender.M, Gender.F))


def pos_fits(pos: Pos, pattern: Pos) -> bool:
    return pattern in (pos, Pos.X) or (pos == Pos.PACK and pattern == Pos.PRON)


def key_fits(key: int, pattern: int) -> bool:
    return pattern in (key, 0)


def matches(value, pattern) -> bool:
    """For cases, numbers and comparisons: X in PATTERN matches anything."""
    return pattern == value or pattern == 0


@dataclass(frozen=True, slots=True)
class Codes:
    """When, where, how often and on whose authority a word is used.
    SOURCE is the main source; MORE, the other sources of the entry (as
    source="O M" in the files)."""
    age: Age = Age.X
    area: Area = Area.X
    geo: Geo = Geo.X
    freq: Freq = Freq.X
    source: Source = Source.X
    more: tuple[Source, ...] = ()

    @property
    def sources(self) -> tuple[Source, ...]:
        """All the sources, the main one first."""
        return (self.source,) + self.more

    def __str__(self):
        """The five letters ([XXXAO]), and +M for each other source."""
        return ''.join(c.name for c in (self.age, self.area, self.geo,
                                        self.freq, self.source)) + \
            ''.join('+' + s.name for s in self.more)


NO_CODES = Codes()


@dataclass(frozen=True, slots=True)
class Part:
    """The grammar of a dictionary word.  Only the fields that its part of
    speech uses are set (decl is the conjugation of a verb, case the case a
    preposition takes); the others keep their defaults."""
    pos: Pos = Pos.X
    decl: Decl = ANY_DECL
    gender: Gender = Gender.X
    kind: Kind = None
    comparison: Comparison = Comparison.X
    sort: NumeralSort = NumeralSort.X
    value: int = 0
    case: Case = Case.X


NO_PART = Part()


@dataclass(frozen=True, slots=True)
class Form:
    """The grammar of an inflected form, as given by an ending.  Only the
    fields that its part of speech uses are set (decl is the conjugation of
    a verb, participle or supine)."""
    pos: Pos = Pos.X
    decl: Decl = ANY_DECL
    case: Case = Case.X
    number: Number = Number.X
    gender: Gender = Gender.X
    comparison: Comparison = Comparison.X
    sort: NumeralSort = NumeralSort.X
    tense: Tense = Tense.X
    voice: Voice = Voice.X
    mood: Mood = Mood.X
    person: int = 0

    def order(self) -> tuple:
        """The key by which forms of an entry are listed."""
        match self.pos:
            case Pos.N | Pos.PRON | Pos.PACK | Pos.VPAR | Pos.SUPINE:
                rest = (self.decl, self.number, self.case, self.gender)
            case Pos.ADJ:
                rest = (self.decl, self.number, self.case, self.gender,
                        self.comparison)
            case Pos.NUM:
                rest = (self.decl, self.number, self.case, self.gender,
                        self.sort)
            case Pos.ADV:
                rest = (self.comparison,)
            case Pos.V:
                rest = (self.decl, self.number, self.tense, self.voice,
                        self.mood, self.person)
            case Pos.PREP:
                rest = (self.case,)
            case _:
                rest = ()
        return (self.pos, rest)

    @property
    def tvm(self) -> tuple[Tense, Voice, Mood]:
        return (self.tense, self.voice, self.mood)


NO_FORM = Form()


@dataclass(frozen=True, slots=True)
class Inflection:
    """An ending: added to stem number KEY (1-4; 0 for any) of a word whose
    grammar fits FORM, it makes that form.  LONG is the ending with its
    long vowels marked (abat -> ābat), or '' if it has none or they are
    not known."""
    form: Form
    key: int = 0
    ending: str = ''
    age: Age = Age.X
    freq: Freq = Freq.X
    long: str = ''


NO_INFLECTION = Inflection(NO_FORM)


# ---------------------------------------------------------------------------
#  Dictionary entries, irregular forms and affixes.  These are compared by
#  identity: two entries with the same text are still two entries.

@dataclass(frozen=True, eq=False, slots=True)
class Entry:
    """A dictionary entry.  STEMS has four items ('' for a blank stem and
    'zzz' for a form that does not exist).  ID is the entry's position in
    its dictionary file, counted from 1; UID its id attribute, which stays
    the same when entries are added or moved (the translations of the
    meanings refer to it)."""
    id: int
    stems: tuple[str, str, str, str]
    part: Part
    codes: Codes
    meaning: str
    dictionary: str = 'general'
    uid: int = 0

    def __repr__(self):
        return (f'<Entry {self.dictionary}:{self.id} {self.stems[0]} '
                f'{self.part.pos.name}>')


@dataclass(frozen=True, eq=False, slots=True)
class Unique:
    """An irregular form that is not made of a stem and an ending."""
    id: int
    word: str
    form: Form
    kind: Kind | int          # a numeral's value for NUM
    codes: Codes
    meaning: str
    uid: int = 0                    # (as for Entry)

    def __repr__(self):
        return f'<Unique {self.id} {self.word}>'


@dataclass(frozen=True, eq=False, slots=True)
class Prefix:
    id: int
    fix: str
    connect: str                    # the letter that must follow, or ''
    root: Pos                       # it attaches to words of this part
    target: Pos                     # making words of this part
    meaning: str
    uid: int = 0                    # (as for Entry)


@dataclass(frozen=True, eq=False, slots=True)
class Suffix:
    id: int
    fix: str
    connect: str                    # the letter that must precede, or ''
    root: Pos
    root_key: int                   # attached to this stem of the root
    target: Part                    # making a word with this grammar
    target_key: int                 # of which it is this stem
    meaning: str
    uid: int = 0                    # (as for Entry)


@dataclass(frozen=True, eq=False, slots=True)
class Tackon:
    """An enclitic (-que, -ne, -cumque ...).  A packon is one that attaches
    only to qu- pronouns (qui -> quicumque)."""
    id: int
    fix: str
    base: Part                      # what it attaches to (pos X: anything)
    meaning: str
    uid: int = 0                    # (as for Entry)

    @property
    def is_packon(self) -> bool:
        return self.base.pos == Pos.PACK and self.base.decl.which in (1, 2) \
            and self.meaning.startswith('PACKON w/')


Addon = Prefix | Suffix | Tackon


def stems_used(pos: Pos) -> int:
    """How many of an entry's four stems its part of speech uses."""
    return {Pos.N: 2, Pos.PRON: 2, Pos.PACK: 2, Pos.ADJ: 4, Pos.NUM: 4,
            Pos.ADV: 3, Pos.V: 4, Pos.PREP: 1, Pos.CONJ: 1,
            Pos.INTERJ: 1}.get(pos, 0)


_FOLD = str.maketrans('vjVJ', 'uiUI')


def fold(s: str) -> str:
    """S in lower case with v as u and j as i: the key under which WORDS
    compares Latin spellings."""
    return s.lower().translate(_FOLD)


#  The long vowels, as data/quantities.xml marks them (see `unmarked`)
LONG_VOWELS = 'āēīōūȳĀĒĪŌŪȲ'
_UNMARK = str.maketrans(LONG_VOWELS, 'aeiouyAEIOUY')


def unmarked(s: str) -> str:
    """S without its long marks: amīc -> amic."""
    return s.translate(_UNMARK)


def marked_like(s: str, marked: str) -> str:
    """S with the long marks of MARKED, the same letters (compared by
    `fold`) with long marks: ('amic', 'amīc') -> 'amīc'.  S itself if
    they are not the same letters."""
    if fold(unmarked(marked)) != fold(s):
        return s
    return ''.join(m if m in LONG_VOWELS else c for c, m in zip(s, marked))


_SPELLINGS = [('ae', 'e'), ('oe', 'e'), ('y', 'i'), ('ph', 'f'), ('h', '')]
_TI = re.compile(r'ti(?=[aeiou]|$)')
_MPN = re.compile(r'mpn')
_DOUBLE = re.compile(r'([^aeiou])\1')


def medieval_fold(s: str, doubles: bool = True) -> str:
    """S folded (see `fold`) and with the spellings that vary in late and
    medieval Latin made alike: e for ae and oe, i for y, f for ph, no h,
    ci for ti before a vowel (or at the end of S: a stem), mn for mpn and
    (if DOUBLES) single consonants for doubled ones."""
    s = fold(s)
    for old, new in _SPELLINGS:
        s = s.replace(old, new)
    s = _TI.sub('ci', s)
    s = _MPN.sub('mn', s)
    return _DOUBLE.sub(r'\1', s) if doubles else s

