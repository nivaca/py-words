"""Tricks: ways of finding words that are not spelled as in the dictionary.

* Roman numerals;
* syncopated perfects (amasti for amavisti);
* "slurs": assimilated prefixes (adp- written app-, conl- written coll-);
* spelling variants, by the first letter of the word, anywhere in it, and
  (with the medieval tricks) late and medieval spellings;
* two words written as one.

Each trick that works adds a marker (a Parse labelled with what was done)
before the parses it found, and an explanation to NOTES.
"""

import re
from typing import TYPE_CHECKING
from collections.abc import Callable

from model import (Pos, Case, Number, NumeralSort, Decl, Form, Inflection,
                    Freq)
from results import Origin, Parse, trick_marker, from_dictionary

if TYPE_CHECKING:
    from analyzer import Analyzer, Opts

# ---------------------------------------------------------------------------
#  The spelling tables: (kind, limit, from, to).  A FLIP replaces an initial
#  FROM with TO; a FLIP_FLOP also tries the reverse; an INTERNAL replaces
#  FROM anywhere in the word; a SLUR tries an assimilated prefix.  A table
#  stops at the first rule after which there are more than LIMIT results.

FLIP_FLOP, FLIP, INTERNAL, SLUR = 'flip_flop', 'flip', 'internal', 'slur'

ANY_TRICKS = [
    (INTERNAL, 0, 'ae', 'e'), (INTERNAL, 0, 'bul', 'bol'),
    (INTERNAL, 0, 'bol', 'bul'), (INTERNAL, 0, 'cl', 'cul'),
    (INTERNAL, 0, 'cu', 'quu'), (INTERNAL, 0, 'f', 'ph'),
    (INTERNAL, 0, 'ph', 'f'), (INTERNAL, 0, 'h', ''),
    (INTERNAL, 0, 'oe', 'e'), (INTERNAL, 0, 'vul', 'vol'),
    (INTERNAL, 0, 'vol', 'vul'), (INTERNAL, 0, 'uol', 'vul'),
]

MEDIEVAL_TRICKS = [
    (INTERNAL, 0, 'col', 'caul'), (INTERNAL, 0, 'e', 'ae'),
    (INTERNAL, 0, 'o', 'u'), (INTERNAL, 0, 'i', 'y'),
    (INTERNAL, 0, 'ism', 'sm'), (INTERNAL, 0, 'isp', 'sp'),
    (INTERNAL, 0, 'ist', 'st'), (INTERNAL, 0, 'iz', 'z'),
    (INTERNAL, 0, 'esm', 'sm'), (INTERNAL, 0, 'esp', 'sp'),
    (INTERNAL, 0, 'est', 'st'), (INTERNAL, 0, 'ez', 'z'),
    (INTERNAL, 0, 'di', 'z'), (INTERNAL, 0, 'f', 'ph'),
    (INTERNAL, 0, 'is', 'ix'), (INTERNAL, 0, 'b', 'p'),
    (INTERNAL, 0, 'd', 't'), (INTERNAL, 0, 'v', 'b'),
    (INTERNAL, 0, 'v', 'f'), (INTERNAL, 0, 's', 'x'),
    (INTERNAL, 0, 'ci', 'ti'), (INTERNAL, 0, 'nt', 'nct'),
    (INTERNAL, 0, 's', 'ns'), (INTERNAL, 0, 'ch', 'c'),
    (INTERNAL, 0, 'c', 'ch'), (INTERNAL, 0, 'th', 't'),
    (INTERNAL, 0, 't', 'th'),
]

INITIAL_TRICKS = {
    'a': [(FLIP_FLOP, 0, 'adgn', 'agn'), (FLIP_FLOP, 0, 'adsc', 'asc'),
          (FLIP_FLOP, 0, 'adsp', 'asp'), (FLIP_FLOP, 0, 'arqui', 'arci'),
          (FLIP_FLOP, 0, 'arqu', 'arcu'), (FLIP, 0, 'ae', 'e'),
          (FLIP, 0, 'al', 'hal'), (FLIP, 0, 'am', 'ham'),
          (FLIP, 0, 'ar', 'har'), (FLIP, 0, 'aur', 'or')],
    'd': [(FLIP, 0, 'dampn', 'damn'), (FLIP_FLOP, 0, 'dij', 'disj'),
          (FLIP_FLOP, 0, 'dir', 'disr'), (FLIP_FLOP, 0, 'dir', 'der'),
          (FLIP_FLOP, 0, 'del', 'dil')],
    'e': [(FLIP_FLOP, 0, 'ecf', 'eff'), (FLIP_FLOP, 0, 'ecs', 'exs'),
          (FLIP_FLOP, 0, 'es', 'ess'), (FLIP_FLOP, 0, 'ex', 'exs'),
          (FLIP, 0, 'eid', 'id'), (FLIP, 0, 'el', 'hel'),
          (FLIP, 0, 'e', 'ae')],
    'f': [(FLIP_FLOP, 0, 'faen', 'fen'), (FLIP_FLOP, 0, 'faen', 'foen'),
          (FLIP_FLOP, 0, 'fed', 'foed'), (FLIP_FLOP, 0, 'fet', 'foet'),
          (FLIP, 0, 'f', 'ph')],
    'g': [(FLIP, 0, 'gna', 'na')],
    'h': [(FLIP, 0, 'har', 'ar'), (FLIP, 0, 'hal', 'al'),
          (FLIP, 0, 'ham', 'am'), (FLIP, 0, 'hel', 'el'),
          (FLIP, 0, 'hol', 'ol'), (FLIP, 0, 'hum', 'um')],
    'k': [(FLIP, 0, 'k', 'c'), (FLIP, 0, 'c', 'k')],
    'l': [(FLIP_FLOP, 1, 'lub', 'lib')],
    'm': [(FLIP_FLOP, 1, 'mani', 'manu')],
    'n': [(FLIP, 0, 'na', 'gna'), (FLIP_FLOP, 0, 'nihil', 'nil')],
    'o': [(FLIP_FLOP, 1, 'obt', 'opt'), (FLIP_FLOP, 1, 'obs', 'ops'),
          (FLIP, 0, 'ol', 'hol'), (FLIP, 1, 'opp', 'op'),
          (FLIP, 0, 'or', 'aur')],
    'p': [(FLIP, 0, 'ph', 'f'), (FLIP_FLOP, 1, 'pre', 'prae')],
    's': [(FLIP_FLOP, 0, 'subsc', 'susc'), (FLIP_FLOP, 0, 'subsp', 'susp'),
          (FLIP_FLOP, 0, 'subc', 'susc'), (FLIP_FLOP, 0, 'succ', 'susc'),
          (FLIP_FLOP, 0, 'subt', 'supt'), (FLIP_FLOP, 0, 'subt', 'sust')],
    't': [(FLIP_FLOP, 0, 'transv', 'trav')],
    'u': [(FLIP, 0, 'ul', 'hul'), (FLIP, 0, 'uol', 'vul')],
    'y': [(FLIP, 0, 'y', 'i')],
    'z': [(FLIP, 0, 'z', 'di')],
}

SLUR_TRICKS = {
    'a': [(FLIP_FLOP, 0, 'abs', 'aps'), (FLIP_FLOP, 0, 'acq', 'adq'),
          (FLIP_FLOP, 0, 'ante', 'anti'), (FLIP_FLOP, 0, 'auri', 'aure'),
          (FLIP_FLOP, 0, 'auri', 'auru'), (SLUR, 0, 'ad', None)],
    'c': [(FLIP, 0, 'circum', 'circun'), (FLIP_FLOP, 0, 'con', 'com'),
          (FLIP, 0, 'co', 'com'), (FLIP, 0, 'co', 'con'),
          (FLIP_FLOP, 0, 'conl', 'coll')],
    'i': [(SLUR, 1, 'in', None), (FLIP_FLOP, 1, 'inb', 'imb'),
          (FLIP_FLOP, 1, 'inp', 'imp')],
    'n': [(FLIP, 0, 'nun', 'non')],
    'o': [(SLUR, 0, 'ob', None)],
    'q': [(FLIP_FLOP, 0, 'quadri', 'quadru')],
    's': [(FLIP, 0, 'se', 'ce'), (SLUR, 0, 'sub', None)],
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
    for v, n in zip(reversed(values[:-1]), reversed(values[1:])):
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


def roman_numeral(word: str, notes: dict) -> list[Parse]:
    value = roman_number(word)
    if not value:
        return []
    notes[Origin.ROMAN] = '%d  as a ROMAN NUMERAL;' % value
    return [_numeral(word, Freq.A)]


# ---------------------------------------------------------------------------
#  Syncope

def _is_perfect(found: list[Parse]) -> bool:
    return bool(found) and found[-1].form.pos == Pos.V and \
        found[-1].infl.key == 3


def syncope(az: Analyzer, word: str, opts: Opts, notes: dict,
            prior: int) -> list[Parse]:
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
            found = az.word(new, opts, prior + 1)
            if found:
                return [trick_marker(label, Origin.SYNCOPE)] + found, new
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
        found, new = first(positions, change, label)
        if _is_perfect(found):
            notes[Origin.SYNCOPE] = note
            az.put_stat(caption, word, found[1].stem)
            return found
        if found and any_form:
            return found
    return []


# ---------------------------------------------------------------------------
#  Spelling tricks

class _Tricks:
    """Applies spelling rules to a word, keeping the first that works."""

    def __init__(self, az: Analyzer, word: str, notes: dict,
                 lookup: Callable[[str, int], list[Parse]], stat: str):
        self.az = az
        self.word = word
        self.s = word.lower()
        self.notes = notes
        self.lookup = lookup            # (word, prior) -> parses
        self.stat_kind = stat           # 'TRICK' or 'SLURY'
        self.out: list[Parse] = []

    def attempt(self, label: str, new: str, note: str, caption: str,
                accept=None, lookup=None) -> bool:
        found = (lookup or self.lookup)(new, len(self.out) + 1)
        if accept is not None:
            found = [p for p in found if accept(p)]
        if found and not (len(found) >= 2 and
                          found[-2].form.pos == Pos.TACKON):
            self.out += [trick_marker(label)] + found
            self.notes[Origin.TRICK] = note
            self.az.put_stat(caption, self.word, label)
            return True
        return False

    def flip(self, x1, x2, note=None) -> bool:
        s = self.s
        if len(s) >= len(x1) + 2 and s.startswith(x1):
            return self.attempt(
                'Word mod %s/%s' % (x1, x2), x2 + s[len(x1):],
                note or "An initial '%s' may have replaced usual '%s'"
                % (x1, x2), '%-5s   FLIP at ' % self.stat_kind)
        return False

    def flip_flop(self, x1, x2) -> bool:
        s = self.s
        for a, b in ((x1, x2), (x2, x1)):
            if len(s) >= len(a) + 2 and s.startswith(a):
                if self.attempt('Word mod %s/%s' % (a, b), b + s[len(a):],
                                "An initial '%s' may be rendered by '%s'"
                                % (a, b), '%-5s  FLOP at ' % self.stat_kind):
                    return True
                if self.stat_kind == 'SLURY':
                    return False        # slurs only try the reverse if
                                        # the word does not start with X1
        return False

    def internal(self, x1, x2) -> bool:
        s = self.s
        for i in range(len(s) - len(x1) + 1):
            if s[i:i + len(x1)] == x1 and self.attempt(
                    'Word mod %s/%s' % (x1, x2), s[:i] + x2 + s[i + len(x1):],
                    "An internal '%s' might be rendered by '%s'" % (x1, x2),
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
                'Slur %s/%s~' % (x1, x1[:-1]), x1[:-1] + s[n] + s[n:],
                "An initial '%s' may be rendered by %s~" % (x1, x1[:-1]),
                'SLURY   SLUR at ')
        if s.startswith(x1[:-1]) and s[n - 1] == s[n] and \
                s[n] not in VOWELS:
            return self.attempt(
                'Slur %s~/%s' % (x1[:-1], x1), x1 + s[n:],
                "An initial '%s~' may be rendered by %s" % (x1[:-1], x1),
                'SLURY   SLUR at ')
        return False

    def table(self, rules) -> bool:
        """Applies RULES; True if one gave more results than its limit."""
        for kind, limit, x1, x2 in rules:
            if kind == FLIP_FLOP:
                self.flip_flop(x1, x2)
            elif kind == FLIP:
                self.flip(x1, x2)
            elif kind == INTERNAL:
                self.internal(x1, x2)
            else:
                self.slur(x1)
            if len(self.out) > limit:
                return True
        return False


def slury(az: Analyzer, word: str, opts: Opts, notes: dict,
          prior: int) -> list[Parse]:
    """Assimilated and variant prefixes (adq-/acq-, con-/com- ...)."""
    from analyzer import Opts
    plain = Opts(opts.do_fixes, opts.only_fixes, False)

    def lookup(new, n):
        found = az.word(new, plain, prior + n)
        if az.settings.do_syncope:
            found += syncope(az, new, plain, notes, prior + n + len(found))
        return found
    t = _Tricks(az, word, notes, lookup, 'SLURY')
    if t.s and t.s[0] in SLUR_TRICKS:
        t.table(SLUR_TRICKS[t.s[0]])
    return t.out


def try_tricks(az: Analyzer, word: str, notes: dict,
               capitalized: bool = False) -> list[Parse]:
    """Spelling variants, medieval spellings and two-word compounds, for a
    word that is not otherwise found."""
    s = az.settings
    opts = az.default_opts()

    def lookup(new, n):
        found = az.word(new, opts, n)
        if s.do_syncope:
            found += syncope(az, new, opts, notes, n + len(found))
        return found
    t = _Tricks(az, word, notes, lookup, 'TRICK')
    w = t.s
    if not w:
        return []
    if w.startswith('is'):
        # Some forms of eo: its stem i- merges with endings in is- (iis).
        found = lookup('i' + w, 1)
        if found and not (len(found) >= 2 and
                          found[-2].form.pos == Pos.TACKON) and \
                found[-1].form.pos == Pos.V and \
                found[-1].form.decl == Decl(6, 1):
            notes[Origin.TRICK] = ("Some forms of eo stem 'i' grates with an "
                                   "'is .. .' ending, so 'is' -> 'iis' ")
            return [trick_marker('Word mod is => iis')] + found
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
                  lookup=lambda new, n: az.word(new, opts, n))
    if t.out:
        return t.out
    if s.do_medieval_tricks:
        if t.table(MEDIEVAL_TRICKS):
            return t.out
        _double_consonants(t)
    if s.do_two_words and not (s.ignore_unknown_names and capitalized):
        _two_words(az, t, opts)
    if only_roman_digits(word):
        notes.pop(Origin.TRICK, None)
        notes[Origin.ROMAN] = '%d  as ill-formed ROMAN NUMERAL?;' % \
            bad_roman_number(word)
        return [trick_marker('Bad Roman Numeral?'), _numeral(word, Freq.D)]
    return t.out


def _double_consonants(t: _Tricks):
    """Medieval writers often wrote a doubled consonant as one."""
    s = t.s
    for i in range(1, len(s) - 1):
        if s[i] not in VOWELS and s[i - 1] in VOWELS and s[i + 1] in VOWELS:
            if t.attempt('Word mod %s -> %s%s' % (s[i], s[i], s[i]),
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
    base = len(t.out)
    for i in range(2, len(s) - 2):
        if s[:i] in COMMON_PREFIXES:
            continue
        first = az.word(s[:i], opts, base + 1)
        if not first:
            continue
        second = az.word(s[i:], opts, base + 2 + len(first))
        if not second or (len(second) >= 2 and
                          second[-2].form.pos == Pos.TACKON):
            continue
        found = first + second
        numbers = any(p.form.pos == Pos.NUM for p in first) and \
            any(p.form.pos == Pos.NUM for p in second)
        if numbers and az.settings.trim_output:
            found = [p for p in found if p.form.pos == Pos.NUM or
                     not (from_dictionary(p.origin) or
                          p.origin == Origin.UNIQUE)]
            t.notes[Origin.TRICK] = 'It is very likely a compound number' \
                '    %s + %s' % (s[:i], s[i:])
            az.put_stat('TRICK   2NUM at ', t.word, s[:i] + '+' + s[i:])
        else:
            t.notes[Origin.TRICK] = 'May be 2 words combined (%s+%s) If ' \
                'not obvious, probably incorrect' % (s[:i], s[i:])
            az.put_stat('TRICK   2WDS at ', t.word, s[:i] + '+' + s[i:])
        t.out += [trick_marker('Two words')] + found
        return
