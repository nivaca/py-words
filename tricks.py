"""Tricks: ways of finding words that are not spelled as in the dictionary.

* Roman numerals;
* syncopated perfects (amasti for amavisti);
* "slurs": assimilated prefixes (adp- written app-, conl- written coll-);
* spelling variants, by the first letter of the word, anywhere in it, and
  (with the medieval tricks) late and medieval spellings;
* two words written as one.

What a trick finds is marked with what was done (see results.Found), and
the trick's explanation goes in NOTES.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from collections.abc import Callable

from model import (Pos, Case, Number, NumeralSort, Decl, Form, Inflection,
                    Freq, medieval_fold)
from results import (Origin, Parse, Found, trick_mark, marked, found, chain,
                     parses_of, shown, from_dictionary)

if TYPE_CHECKING:
    from analyzer import Analyzer, Opts

# ---------------------------------------------------------------------------
#  The spelling tables: (kind, from, to).  A FLIP replaces an initial FROM
#  with TO; a FLIP_FLOP also tries the reverse; an INTERNAL replaces FROM
#  anywhere in the word; a SLUR tries an assimilated prefix.  A table stops
#  at the first rule that finds something.

FLIP_FLOP, FLIP, INTERNAL, SLUR = 'flip_flop', 'flip', 'internal', 'slur'

ANY_TRICKS = [
    (INTERNAL, 'ae', 'e'), (INTERNAL, 'bul', 'bol'),
    (INTERNAL, 'bol', 'bul'), (INTERNAL, 'cl', 'cul'),
    (INTERNAL, 'cu', 'quu'), (INTERNAL, 'f', 'ph'),
    (INTERNAL, 'ph', 'f'), (INTERNAL, 'h', ''),
    (INTERNAL, 'oe', 'e'), (INTERNAL, 'vul', 'vol'),
    (INTERNAL, 'vol', 'vul'), (INTERNAL, 'uol', 'vul'),
]

MEDIEVAL_TRICKS = [
    (INTERNAL, 'col', 'caul'), (INTERNAL, 'e', 'ae'),
    (INTERNAL, 'o', 'u'), (INTERNAL, 'i', 'y'),
    (INTERNAL, 'ism', 'sm'), (INTERNAL, 'isp', 'sp'),
    (INTERNAL, 'ist', 'st'), (INTERNAL, 'iz', 'z'),
    (INTERNAL, 'esm', 'sm'), (INTERNAL, 'esp', 'sp'),
    (INTERNAL, 'est', 'st'), (INTERNAL, 'ez', 'z'),
    (INTERNAL, 'di', 'z'), (INTERNAL, 'f', 'ph'),
    (INTERNAL, 'is', 'ix'), (INTERNAL, 'b', 'p'),
    (INTERNAL, 'd', 't'), (INTERNAL, 'v', 'b'),
    (INTERNAL, 'v', 'f'), (INTERNAL, 's', 'x'),
    (INTERNAL, 'ci', 'ti'), (INTERNAL, 'nt', 'nct'),
    (INTERNAL, 's', 'ns'), (INTERNAL, 'ch', 'c'),
    (INTERNAL, 'c', 'ch'), (INTERNAL, 'th', 't'),
    (INTERNAL, 't', 'th'),
]

INITIAL_TRICKS = {
    'a': [(FLIP_FLOP, 'adgn', 'agn'), (FLIP_FLOP, 'adsc', 'asc'),
          (FLIP_FLOP, 'adsp', 'asp'), (FLIP_FLOP, 'arqui', 'arci'),
          (FLIP_FLOP, 'arqu', 'arcu'), (FLIP, 'ae', 'e'),
          (FLIP, 'al', 'hal'), (FLIP, 'am', 'ham'),
          (FLIP, 'ar', 'har'), (FLIP, 'aur', 'or')],
    'd': [(FLIP, 'dampn', 'damn'), (FLIP_FLOP, 'dij', 'disj'),
          (FLIP_FLOP, 'dir', 'disr'), (FLIP_FLOP, 'dir', 'der'),
          (FLIP_FLOP, 'del', 'dil')],
    'e': [(FLIP_FLOP, 'ecf', 'eff'), (FLIP_FLOP, 'ecs', 'exs'),
          (FLIP_FLOP, 'es', 'ess'), (FLIP_FLOP, 'ex', 'exs'),
          (FLIP, 'eid', 'id'), (FLIP, 'el', 'hel'),
          (FLIP, 'e', 'ae')],
    'f': [(FLIP_FLOP, 'faen', 'fen'), (FLIP_FLOP, 'faen', 'foen'),
          (FLIP_FLOP, 'fed', 'foed'), (FLIP_FLOP, 'fet', 'foet'),
          (FLIP, 'f', 'ph')],
    'g': [(FLIP, 'gna', 'na')],
    'h': [(FLIP, 'har', 'ar'), (FLIP, 'hal', 'al'),
          (FLIP, 'ham', 'am'), (FLIP, 'hel', 'el'),
          (FLIP, 'hol', 'ol'), (FLIP, 'hum', 'um')],
    'k': [(FLIP, 'k', 'c'), (FLIP, 'c', 'k')],
    'l': [(FLIP_FLOP, 'lub', 'lib')],
    'm': [(FLIP_FLOP, 'mani', 'manu')],
    'n': [(FLIP, 'na', 'gna'), (FLIP_FLOP, 'nihil', 'nil')],
    'o': [(FLIP_FLOP, 'obt', 'opt'), (FLIP_FLOP, 'obs', 'ops'),
          (FLIP, 'ol', 'hol'), (FLIP, 'opp', 'op'),
          (FLIP, 'or', 'aur')],
    'p': [(FLIP, 'ph', 'f'), (FLIP_FLOP, 'pre', 'prae')],
    's': [(FLIP_FLOP, 'subsc', 'susc'), (FLIP_FLOP, 'subsp', 'susp'),
          (FLIP_FLOP, 'subc', 'susc'), (FLIP_FLOP, 'succ', 'susc'),
          (FLIP_FLOP, 'subt', 'supt'), (FLIP_FLOP, 'subt', 'sust')],
    't': [(FLIP_FLOP, 'transv', 'trav')],
    'u': [(FLIP, 'ul', 'hul'), (FLIP, 'uol', 'vul')],
    'y': [(FLIP, 'y', 'i')],
    'z': [(FLIP, 'z', 'di')],
}

SLUR_TRICKS = {
    'a': [(FLIP_FLOP, 'abs', 'aps'), (FLIP_FLOP, 'acq', 'adq'),
          (FLIP_FLOP, 'ante', 'anti'), (FLIP_FLOP, 'auri', 'aure'),
          (FLIP_FLOP, 'auri', 'auru'), (SLUR, 'ad', None)],
    'c': [(FLIP, 'circum', 'circun'), (FLIP_FLOP, 'con', 'com'),
          (FLIP, 'co', 'com'), (FLIP, 'co', 'con'),
          (FLIP_FLOP, 'conl', 'coll')],
    'i': [(SLUR, 'in', None), (FLIP_FLOP, 'inb', 'imb'),
          (FLIP_FLOP, 'inp', 'imp')],
    'n': [(FLIP, 'nun', 'non')],
    'o': [(SLUR, 'ob', None)],
    'q': [(FLIP_FLOP, 'quadri', 'quadru')],
    's': [(FLIP, 'se', 'ce'), (SLUR, 'sub', None)],
}

#  Not tried as the first of two words
COMMON_PREFIXES = ('dis', 'ex', 'in', 'per', 'prae', 'pro', 're', 'si',
                   'sub', 'super', 'trans')

VOWELS = 'aeiouy'


# ---------------------------------------------------------------------------
#  Roman numerals

ROMAN = re.compile(r'M{0,4}(CM|CD|D?C{0,4})(XC|XL|L?X{0,4})(IX|IV|V?I{0,4})')
ROMAN_DIGITS = {'M': 1000, 'D': 500, 'C': 100, 'L': 50, 'X': 10, 'V': 5,
                'I': 1}


def only_roman_digits(word: str) -> bool:
    return bool(word) and all(c in ROMAN_DIGITS for c in word.upper())


def _sum_digits(word: str) -> int:
    """Adds the digits, subtracting those before a larger one."""
    values = [ROMAN_DIGITS[c] for c in word.upper()]
    return sum(-v if v < n else v
               for v, n in zip(values, values[1:] + [0]))


def roman_number(word: str) -> int:
    """The value of a well-formed Roman numeral, or 0."""
    if not ROMAN.fullmatch(word.upper()):
        return 0
    return _sum_digits(word)


def bad_roman_number(word: str) -> int:
    """A guess at the value of an ill-formed numeral (IIX, LXXXXX ...)."""
    values = [ROMAN_DIGITS.get(c, 0) for c in word.upper()]
    total = decremented_from = values[-1]
    for v, n in zip(reversed(values[:-1]), reversed(values[1:]),
                    strict=True):
        if v < n:
            total -= v
            decremented_from = n
        elif v == n:
            total += -v if v < decremented_from else v
        else:
            total += v
            decremented_from = n
    return max(total, 0)


def _numeral(word: str, freq: Freq) -> Parse:
    return Parse(word, Inflection(Form(Pos.NUM, Decl(2, 0),
                                       sort=NumeralSort.CARD), freq=freq),
                 Origin.ROMAN)


def roman_numeral(word: str, notes: dict) -> list[Found]:
    value = roman_number(word)
    if not value:
        return []
    notes[Origin.ROMAN] = f'{value}  as a ROMAN NUMERAL;'
    return found([_numeral(word, Freq.A)])


# ---------------------------------------------------------------------------
#  Syncope

def _is_perfect(findings: list[Found]) -> bool:
    """Whether the last form found is a perfect (stem 3) of a verb."""
    parses = parses_of(findings)
    return bool(parses) and parses[-1].form.pos == Pos.V and \
        parses[-1].infl.key == 3


def _ends_with_tackon(findings: list[Found]) -> bool:
    """Whether the last thing found is a single form with an enclitic."""
    items = shown(findings)
    return len(items) >= 2 and items[-2].form.pos == Pos.TACKON


def syncope(az: Analyzer, word: str, opts: Opts,
            notes: dict) -> list[Found]:
    """Syncopated perfects: amasti (amavisti), audii (audivi), dixti
    (dixisti) ..."""
    s = word.lower()
    n = len(s)

    def first(positions, change, label):
        """The parses of the first changed word (rightmost change first)
        that is found."""
        for i in positions:
            new = change(i)
            if new is None:
                continue
            findings = az.word(new, opts, True)
            if findings:
                return marked(trick_mark(label, Origin.SYNCOPE),
                              findings), new
        return [], None

    rules = [
        (range(n - 1, 0, -1),
         lambda i: s[:i] + 'v' + s[i:] if s[i - 1:i + 1] == 'ii' else None,
         'Syncope  ii => ivi',
         "Syncopated perfect ivi can drop 'v' without contracting vowel",
         ' SYNCOPE  ivi at ', False),
        (range(n - 2, 0, -1),
         lambda i: s[:i] + 'vi' + s[i:]
         if s[i - 1:i + 1] in ('as', 'es', 'is', 'os') else None,
         'Syncope   s => vis',
         "Syncopated perfect often drops the 'v' and contracts vowel",
         'SYNCOPE  vis at ', True),
        (range(n - 2, 1, -1),
         lambda i: s[:i] + 've' + s[i:]
         if s[i - 1:i + 1] in ('ar', 'er', 'or') else None,
         'Syncope   r => v.r',
         "Syncopated perfect often drops the 'v' and contracts vowel",
         'SYNCOPE  ver at ', False),
        (range(n - 3, 0, -1),
         lambda i: s[:i] + 'v' + s[i:] if s[i - 1:i + 2] == 'ier' else None,
         'Syncope  ier=>iver',
         "Syncopated perfect often drops the 'v' and contracts vowel",
         'SYNCOPE  ier at ', False),
        (range(n - 2, 0, -1),
         lambda i: s[:i] + 'is' + s[i:] if s[i - 1] in 'sx' else None,
         'Syncope s/x => +is',
         "Syncopated perfect sometimes drops the 'is' after 's' or 'x'",
         'SYNCOPEx/sis at ', False),
    ]
    for positions, change, label, note, caption, any_form in rules:
        findings, new = first(positions, change, label)
        if _is_perfect(findings):
            notes[Origin.SYNCOPE] = note
            az.put_stat(caption, word, shown(findings)[1].stem)
            return findings
        if findings and any_form:
            return findings
    return []


# ---------------------------------------------------------------------------
#  Spelling tricks

def _places(s: str, sub: str):
    """Where SUB is in S (overlapping places too), first to last."""
    i = s.find(sub)
    while i >= 0:
        yield i
        i = s.find(sub, i + 1)


class _Tricks:
    """Applies spelling rules to a word, keeping the first that works."""

    def __init__(self, az: Analyzer, word: str, notes: dict,
                 lookup: Callable[[str], list[Found]], stat: str):
        self.az = az
        self.word = word
        self.s = word.lower()
        self.notes = notes
        self.lookup = lookup            # word -> findings
        self.stat_kind = stat           # 'TRICK' or 'SLURY'
        self.out: list[Found] = []

    def attempt(self, label: str, new: str, note: str, caption: str,
                accept=None, lookup=None) -> bool:
        findings = (lookup or self.lookup)(new)
        if accept is not None:
            findings = found(p for p in parses_of(findings) if accept(p))
        if findings and not _ends_with_tackon(findings):
            self.out = chain(self.out, marked(trick_mark(label), findings))
            self.notes[Origin.TRICK] = note
            self.az.put_stat(caption, self.word, label)
            return True
        return False

    def flip(self, x1, x2, note=None) -> bool:
        s = self.s
        if len(s) >= len(x1) + 2 and s.startswith(x1):
            return self.attempt(
                f'Word mod {x1}/{x2}', x2 + s[len(x1):],
                note or f"An initial '{x1}' may have replaced usual '{x2}'",
                f'{self.stat_kind:<5}   FLIP at ')
        return False

    def flip_flop(self, x1, x2) -> bool:
        s = self.s
        for a, b in ((x1, x2), (x2, x1)):
            if len(s) >= len(a) + 2 and s.startswith(a):
                if self.attempt(f'Word mod {a}/{b}', b + s[len(a):],
                                f"An initial '{a}' may be rendered by '{b}'",
                                f'{self.stat_kind:<5}  FLOP at '):
                    return True
                if self.stat_kind == 'SLURY':
                    return False        # slurs only try the reverse if
                                        # the word does not start with X1
        return False

    def internal(self, x1, x2) -> bool:
        s = self.s
        for i in _places(s, x1):
            if self.attempt(
                    f'Word mod {x1}/{x2}', s[:i] + x2 + s[i + len(x1):],
                    f"An internal '{x1}' might be rendered by '{x2}'",
                    'TRICK   INTR at '):
                return True
        return False

    def slur(self, x1) -> bool:
        """ad + consonant written as a doubled consonant (appono for
        adpono), and the reverse."""
        s = self.s
        n = len(x1)
        if len(s) < n + 2:
            return False
        if s.startswith(x1) and s[n] not in VOWELS:
            return self.attempt(
                f'Slur {x1}/{x1[:-1]}~', x1[:-1] + s[n] + s[n:],
                f"An initial '{x1}' may be rendered by {x1[:-1]}~",
                'SLURY   SLUR at ')
        if s.startswith(x1[:-1]) and s[n - 1] == s[n] and \
                s[n] not in VOWELS:
            return self.attempt(
                f'Slur {x1[:-1]}~/{x1}', x1 + s[n:],
                f"An initial '{x1[:-1]}~' may be rendered by {x1}",
                'SLURY   SLUR at ')
        return False

    def table(self, rules) -> bool:
        """Applies RULES until one finds something; returns whether one
        did."""
        for kind, x1, x2 in rules:
            if kind == FLIP_FLOP:
                self.flip_flop(x1, x2)
            elif kind == FLIP:
                self.flip(x1, x2)
            elif kind == INTERNAL:
                self.internal(x1, x2)
            else:
                self.slur(x1)
            if self.out:
                return True
        return False


def slury(az: Analyzer, word: str, opts: Opts,
          notes: dict) -> list[Found]:
    """Assimilated and variant prefixes (adq-/acq-, con-/com- ...)."""
    from analyzer import Opts
    plain = Opts(opts.do_fixes, opts.only_fixes, False)

    def lookup(new):
        findings = az.word(new, plain, True)
        if az.settings.do_syncope:
            findings = chain(findings, syncope(az, new, plain, notes))
        return findings
    t = _Tricks(az, word, notes, lookup, 'SLURY')
    if t.s and t.s[0] in SLUR_TRICKS:
        t.table(SLUR_TRICKS[t.s[0]])
    return t.out


def try_tricks(az: Analyzer, word: str, notes: dict,
               capitalized: bool = False) -> list[Found]:
    """Spelling variants, medieval spellings and two-word compounds, for a
    word that is not otherwise found."""
    s = az.settings
    opts = az.default_opts()

    def lookup(new):
        findings = az.word(new, opts, True)
        if s.do_syncope:
            findings = chain(findings, syncope(az, new, opts, notes))
        return findings
    t = _Tricks(az, word, notes, lookup, 'TRICK')
    w = t.s
    if not w:
        return []
    if w.startswith('is'):
        # Some forms of eo: its stem i- merges with endings in is- (iis).
        findings = lookup('i' + w)
        last = parses_of(findings)[-1:]
        if last and not _ends_with_tackon(findings) and \
                last[0].form.pos == Pos.V and \
                last[0].form.decl == Decl(6, 1):
            notes[Origin.TRICK] = ("Some forms of eo stem 'i' grates with an "
                                   "'is .. .' ending, so 'is' -> 'iis' ")
            return marked(trick_mark('Word mod is => iis'), findings)
    elif w[0] in INITIAL_TRICKS and t.table(INITIAL_TRICKS[w[0]]):
        return t.out
    if t.table(ANY_TRICKS):
        return t.out
    if len(w) > 3 and w.endswith('is'):
        # Adjectives of the 1st/2nd declension: -iis written -is
        t.attempt('Word mod iis -> is', w[:-2] + 'iis',
                  "A Terminal 'iis' on ADJ 1 1 DAT/ABL P might drop 'i'",
                  'TRICK  ADJIS at ',
                  accept=lambda p: p.form.pos == Pos.ADJ and
                  p.form.decl == Decl(1, 1) and
                  p.form.case in (Case.DAT, Case.ABL) and
                  p.form.number == Number.P,
                  lookup=lambda new: az.word(new, opts, True))
    if t.out:
        return t.out
    if s.do_medieval_tricks:
        if _medieval_spellings(t) or t.table(MEDIEVAL_TRICKS):
            return t.out
        _double_consonants(t)
    if s.do_two_words and not (s.ignore_unknown_names and capitalized):
        _two_words(az, t, opts)
    if only_roman_digits(word):
        notes.pop(Origin.TRICK, None)
        notes[Origin.ROMAN] = \
            f'{bad_roman_number(word)}  as ill-formed ROMAN NUMERAL?;'
        return [Found((_numeral(word, Freq.D),),
                      (trick_mark('Bad Roman Numeral?'),))]
    return t.out


#  At most this many respellings are tried for one word
MOST_RESPELLINGS = 40


def _medieval_spellings(t: _Tricks) -> bool:
    """Several medieval spellings in one word (hystorie for historiae,
    phylosophia for philosophia, michi for mihi), found by comparing its
    stems and endings with the dictionary's under `medieval_fold`.  The
    first group of respellings that finds something is kept, and of it
    those of the most frequent entries."""
    from analyzer import best_freq
    for group in _respellings(t.az.lex, t.s):
        kept = []
        for new in group:
            findings = t.lookup(new)
            if findings and not _ends_with_tackon(findings):
                kept.append((best_freq(findings), new, findings))
        if kept:
            best = min(freq for freq, *_ in kept)
            found_as = [new for freq, new, _ in kept if freq == best]
            for freq, new, findings in kept:
                if freq == best:
                    t.out = chain(t.out, marked(
                        trick_mark(f'Medieval {t.s} -> {new}'), findings))
            t.notes[Origin.TRICK] = (f"'{t.s}' may be a medieval spelling "
                                     f"of {', '.join(found_as)}")
            t.az.put_stat('TRICK   MEDV at ', t.word, ' '.join(found_as))
            return True
    return False


def _respellings(lex, word: str) -> list[list[str]]:
    """The classical spellings that WORD may stand for, in groups to try
    in turn: ch read as h (michi, nichil); then each dictionary stem and
    ending equal to a split of WORD under `medieval_fold`."""
    groups = [[word.replace('ch', 'h')]] if 'ch' in word else []
    out = {}
    for z in range(min(7, len(word) - 1), -1, -1):
        stems = lex.medieval_stems.get(medieval_fold(word[:len(word) - z]),
                                       ())
        if not stems:
            continue
        ends = [''] if z == 0 else \
            lex.medieval_endings.get(
                medieval_fold(word[-z:], doubles=False), ())
        for stem in stems:
            for end in ends:
                if stem + end != word:
                    out[stem + end] = None
    return groups + [list(out)[:MOST_RESPELLINGS]]


def _double_consonants(t: _Tricks):
    """Medieval writers often wrote a doubled consonant as one."""
    s = t.s
    for i in range(1, len(s) - 1):
        if s[i] not in VOWELS and s[i - 1] in VOWELS and s[i + 1] in VOWELS:
            if t.attempt(f'Word mod {s[i]} -> {s[i]}{s[i]}',
                         s[:i + 1] + s[i:],
                         'A doubled consonant may be rendered by just the '
                         'single  MEDIEVAL', 'TRICK   2CON at '):
                return


def _two_words(az: Analyzer, t: _Tricks, opts: Opts):
    """Two words written as one: the first is the shortest found word at
    the start that is not a common prefix."""
    s = t.s
    if len(s) < 5:
        return
    for i in range(2, len(s) - 2):
        if s[:i] in COMMON_PREFIXES:
            continue
        first = az.word(s[:i], opts, True)
        if not first:
            continue
        second = az.word(s[i:], opts, True)
        if not second or _ends_with_tackon(second):
            continue
        findings = chain(first, second)
        numbers = any(p.form.pos == Pos.NUM for p in parses_of(first)) and \
            any(p.form.pos == Pos.NUM for p in parses_of(second))
        if numbers and az.settings.trim_output:
            #  only the numerals (the marks stay)
            findings = chain([Found(tuple(
                p for p in f.parses if p.form.pos == Pos.NUM or
                not (from_dictionary(p.origin) or
                     p.origin == Origin.UNIQUE)), f.marks)
                for f in findings])
            t.notes[Origin.TRICK] = 'It is very likely a compound number' \
                f'    {s[:i]} + {s[i:]}'
            az.put_stat('TRICK   2NUM at ', t.word, s[:i] + '+' + s[i:])
        else:
            t.notes[Origin.TRICK] = (f'May be 2 words combined ({s[:i]}+'
                                     f'{s[i:]}) If not obvious, probably '
                                     'incorrect')
            az.put_stat('TRICK   2WDS at ', t.word, s[:i] + '+' + s[i:])
        t.out = chain(t.out, marked(trick_mark('Two words'), findings))
        return
