"""Analysis of Latin words: finding the dictionary entries and forms that a
word can be.

A word is tried as, in order: an irregular form (uniques.xml); a qu-
pronoun (qui, quisquam, ...); a stem from the dictionary plus an ending;
the same with a prefix and/or suffix ("fixes"); a word with an enclitic
(-que, -ne, ...).  If all that fails, spelling tricks are tried (see
tricks.py).  Finally participles followed by a form of esse are read as
compound tenses, and the results are ordered and grouped (results.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from collections.abc import Callable

import tricks
from lexicon import Lexicon, StemRef, ENDING_LETTERS
from model import (Pos, Case, Number, Gender, Comparison, NumeralSort,
                    Tense, Voice, Mood, Freq, Decl, Form, Inflection,
                    Prefix, Suffix, Tackon, fold, pos_fits, key_fits)
from results import (Origin, Parse, WordResult, marker, sweep, group,
                      AFFIX_POS)
from settings import Settings

MAX_STEM = 18
ENCLITICS = 4       # the first tackons of addons.xml (que, ne, ve, est) are
                    # tried on every word; the others only on unknown ones

#  Which entries a dictionary search may return
REGULAR, QU_PRONOUNS, PACKONS = 'regular', 'qu-pronouns', 'packons'


@dataclass(frozen=True, slots=True)
class Opts:
    """How a word is looked up."""
    do_fixes: bool = True           # try prefixes and suffixes ...
    only_fixes: bool = False        # ... and nothing else
    use_prefixes: bool = True


def _origin(ref: StemRef) -> Origin:
    return Origin.SPECIAL if ref.entry.dictionary == 'special' \
        else Origin.GENERAL


def _gender_fits(gender: Gender, pattern: Gender) -> bool:
    """C (common) in an ending matches any gender but neuter."""
    return pattern in (gender, Gender.X) or \
        (pattern == Gender.C and gender != Gender.N)


def _adj_comparison(key: int) -> Comparison:
    if key in (0, 1, 2):
        return Comparison.POS
    return {3: Comparison.COMP, 4: Comparison.SUPER}.get(key, Comparison.X)


def _adv_comparison(key: int) -> Comparison:
    return {1: Comparison.POS, 2: Comparison.COMP,
            3: Comparison.SUPER}.get(key, Comparison.X)


def _form_of(part, key: int, infl: Inflection) -> Form | None:
    """The form that INFL makes of a word with grammar PART whose stem
    number is KEY, or None if the ending does not fit the word."""
    q = infl.form
    match part.pos:
        case Pos.N:
            if part.decl.fits(q.decl) and \
                    _gender_fits(part.gender, q.gender):
                return Form(Pos.N, part.decl, q.case, q.number, part.gender)
        case Pos.PRON:
            if part.decl.fits(q.decl):
                return Form(Pos.PRON, part.decl, q.case, q.number, q.gender)
        case Pos.ADJ:
            if part.decl.fits(q.decl) and (
                    part.comparison in (q.comparison, Comparison.X) or
                    q.comparison == Comparison.X):
                if part.comparison != Comparison.X:
                    comparison = part.comparison
                else:
                    comparison = _adj_comparison(key)
                return Form(Pos.ADJ, part.decl, q.case, q.number, q.gender,
                            comparison)
        case Pos.NUM:
            if part.decl.fits(q.decl) and key == infl.key:
                sort = part.sort if part.sort != NumeralSort.X \
                    else NumeralSort(key) if 1 <= key <= 4 else NumeralSort.X
                return Form(Pos.NUM, part.decl, q.case, q.number, q.gender,
                            sort=sort)
        case Pos.ADV:
            if q.comparison in (part.comparison, Comparison.X) or \
                    part.comparison == Comparison.X:
                comparison = part.comparison if part.comparison != \
                    Comparison.X else _adv_comparison(key)
                return Form(Pos.ADV, comparison=comparison)
        case Pos.V:
            if part.decl.fits(q.decl):
                return replace(q, decl=part.decl)
        case Pos.PREP:
            if part.case == q.case:
                return q
        case Pos.CONJ | Pos.INTERJ:
            return q
    return None


def _verbal(pos: Pos) -> Pos:
    return Pos.V if pos in (Pos.VPAR, Pos.SUPINE) else pos


def _key_matches(key: int, pos: Pos, ending_key: int) -> bool:
    """Whether an ending for stem ENDING_KEY goes on a stem numbered KEY.
    Key 0 (a word whose first two stems are equal) takes the endings of
    both."""
    return key_fits(key, ending_key) or \
        (key == 0 and pos in (Pos.N, Pos.ADJ, Pos.V) and ending_key in (1, 2))


def _uv(s: str) -> str:
    """Affixes are matched with u and v as the same letter (but i and j
    distinct)."""
    return s.lower().replace('v', 'u')


def _abbreviation(part) -> bool:
    return part.pos in (Pos.N, Pos.ADJ) and part.decl == Decl(9, 8)


class Analyzer:
    def __init__(self, lexicon: Lexicon, settings: Settings,
                 stat: Callable[[str], None] | None = None):
        self.lex = lexicon
        self.settings = settings
        self.stat = stat or (lambda line: None)
        self.line_number = 0
        self.word_number = 0
        self._cache: dict[tuple, tuple[Parse, ...]] = {}

    def reset(self):
        """Forget cached results (after the settings have changed)."""
        self._cache.clear()

    def default_opts(self) -> Opts:
        s = self.settings
        return Opts(s.do_fixes, s.do_only_fixes, s.use_prefixes)

    def put_stat(self, caption: str, word: str, detail: str):
        """A line for the statistics file (WORD.STA)."""
        self.stat(f'{caption}{self.line_number:<8d}{self.word_number:<4d}   '
                  f'{word[:20]:<20}   {detail}')

    # -----------------------------------------------------------------
    #  Affixes

    def strip_prefix(self, word: str, prefix: Prefix, opts: Opts) -> str:
        fix = prefix.fix
        if opts.use_prefixes and len(word) > len(fix) and \
                _uv(word[:len(fix)]) == _uv(fix) and \
                (not prefix.connect or word[len(fix)] == prefix.connect):
            return word[len(fix):]
        return word

    def strip_suffix(self, word: str, suffix: Suffix) -> str:
        fix = suffix.fix
        n = len(word) - len(fix)
        if self.settings.use_suffixes and n > 0 and \
                _uv(word[n:]) == _uv(fix) and \
                (not suffix.connect or word[n - 1] == suffix.connect):
            return word[:n]
        return word

    def strip_tackon(self, word: str, tackon: Tackon) -> str:
        fix = tackon.fix
        n = len(word) - len(fix)
        if self.settings.use_tackons and n > 0 and \
                _uv(word[n:]) == _uv(fix):
            return word[:n]
        return word

    # -----------------------------------------------------------------
    #  Dictionary search

    def search(self, stems, restriction=REGULAR) -> list[StemRef]:
        """The dictionary stems equal to one of STEMS; general dictionary
        first."""
        refs = []
        for dictionary in ('general', 'special'):
            for stem in stems:
                for ref in self.lex.stems.get(fold(stem), ()):
                    if ref.entry.dictionary != dictionary:
                        continue
                    part = ref.part
                    qu = part.pos == Pos.PRON and part.decl.which == 1
                    if restriction == REGULAR:
                        if part.pos == Pos.PACK or qu:
                            continue
                    elif restriction == PACKONS:
                        if part.pos != Pos.PACK:
                            continue
                    elif not qu:
                        continue
                    refs.append(ref)
        return refs

    def candidates(self, word: str) -> tuple[list[Parse], list[str]]:
        """The ways WORD can be split into a stem and an ending, and the
        stems (shortest first)."""
        parses = []
        stems = {}
        if len(word) <= MAX_STEM and self.lex.blank_endings:
            parses += [Parse(word, infl, Origin.NONE)
                       for infl in self.lex.blank_endings]
            stems[len(word)] = word
        if word[-1] in ENDING_LETTERS:
            for z in range(min(7, len(word)), 0, -1):
                stem = word[:-z]
                if len(stem) > MAX_STEM:
                    continue
                for infl in self.lex.endings.get(fold(word[-z:]), ()):
                    parses.append(Parse(stem, infl, Origin.NONE))
                    stems[len(stem)] = stem
        return parses, [stems[n] for n in sorted(stems)]

    def match(self, candidates: list[Parse], refs: list[StemRef],
              prefix: Prefix | None = None,
              suffix: Suffix | None = None,
              opts: Opts = Opts()) -> list[Parse]:
        """The candidate (stem, ending) splits that fit the dictionary stems
        REFS, perhaps with a prefix and/or suffix."""
        out = []
        for ref in refs:
            part, key = ref.part, ref.key
            if suffix is not None:
                if _abbreviation(part):
                    continue
                if not (pos_fits(part.pos, suffix.root) and
                        _key_matches(key, part.pos, suffix.root_key)):
                    continue
                if suffix.target.pos in (Pos.N, Pos.PRON, Pos.ADJ, Pos.NUM,
                                         Pos.ADV, Pos.V):
                    part = suffix.target
                key = suffix.target_key
            if prefix is not None:
                if _abbreviation(part) or part.pos in (Pos.INTERJ, Pos.CONJ):
                    continue
                if prefix.root not in (part.pos, Pos.X):
                    continue
            length = len(ref.stem)
            if prefix is not None and opts.use_prefixes:
                length += len(prefix.fix)
            if suffix is not None and self.settings.use_suffixes:
                length += len(suffix.fix)
            for c in candidates:
                if len(c.stem) != length:
                    continue
                infl = c.infl
                if not (_key_matches(key, part.pos, infl.key) and
                        part.pos == _verbal(infl.form.pos)):
                    continue
                form = _form_of(part, key, infl)
                if form is None:
                    continue
                stem = c.stem if prefix is None else \
                    self.strip_prefix(c.stem, prefix, opts)
                out.append(Parse(stem, replace(infl, form=form),
                                 _origin(ref), ref.entry))
        return out

    @staticmethod
    def arrange(parses: list[Parse]) -> list[Parse]:
        """Orders the parses of a word by entry, then ending, then form,
        dropping repeats."""
        ordered = sorted(parses, key=lambda p: (
            p.id, len(p.infl.ending), p.form.order(), p.origin))
        out = []
        for p in ordered:
            if out and out[-1].form == p.form and out[-1].id == p.id:
                continue
            out.append(p)
        return out

    # -----------------------------------------------------------------
    #  WORD

    def word(self, word: str, opts: Opts, prior: int = 0) -> list[Parse]:
        """The analyses of WORD as a dictionary word, irregular form or
        qu- pronoun, with prefixes, suffixes and tackons.  PRIOR is the
        number of results the caller already has: prefixes and suffixes
        are only tried when there are none."""
        key = (word, opts, prior > 0)
        found = self._cache.get(key)
        if found is None:
            found = self._cache[key] = tuple(self._word(word, opts, prior))
        return list(found)

    def _word(self, word: str, opts: Opts, prior: int) -> list[Parse]:
        w = word.lower().strip()
        if not w:
            return []
        out = [Parse(u.word, Inflection(u.form), Origin.UNIQUE, u)
               for u in self.lex.uniques.get(fold(w), ())]
        out += self._qu_words(w, opts)
        candidates, stems = self.candidates(w)
        if candidates:
            out += self._stems(candidates, stems, opts, prior + len(out))
        if not out:
            out = self._tackons(w, opts, prior)
        return out

    def _stems(self, candidates, stems, opts: Opts,
               have: int) -> list[Parse]:
        refs = [] if opts.only_fixes else self.search(stems)
        if opts.do_fixes and ((have == 0 and not refs) or
                              self.settings.do_fixes_anyway):
            # No stem of the word is in the dictionary: a prefix first
            return self._prefixed(stems, candidates, opts) or \
                self._suffixed(stems, candidates, opts)
        found = self.match(candidates, refs, opts=opts)
        if found:
            return self.arrange(found)
        if opts.do_fixes and have == 0:
            # Its stems are, but with other endings: a suffix first
            return self._suffixed(stems, candidates, opts) or \
                self._prefixed(stems, candidates, opts)
        return []

    def _prefixed(self, stems, candidates, opts: Opts,
                  suffix: Suffix | None = None) -> list[Parse]:
        """[prefix marker, parses] for the first prefix that works."""
        if not opts.use_prefixes:
            return []
        for prefix in self.lex.prefixes:
            bare = [s[len(prefix.fix):] for s in stems
                    if s[:1] == prefix.fix[:1] and
                    self.strip_prefix(s, prefix, opts) != s]
            if not bare:
                continue
            refs = self.search(bare)
            if not refs:
                continue
            found = self.match(candidates, refs, prefix, suffix, opts)
            if found:
                return [marker(prefix)] + self.arrange(found)
        return []

    def _suffixed(self, stems, candidates, opts: Opts) -> list[Parse]:
        """[(prefix marker), suffix marker, parses] for every suffix that
        works."""
        out = []
        for suffix in self.lex.suffixes:
            bare = [self.strip_suffix(s, suffix) for s in stems
                    if self.strip_suffix(s, suffix) != s]
            if not bare:
                continue
            refs = self.search(bare)
            if refs:
                found = self.arrange(self.match(candidates, refs,
                                                suffix=suffix, opts=opts))
                prefix_marker = []
            else:
                found = self._prefixed(bare, candidates, opts, suffix)
                prefix_marker, found = found[:1], found[1:]
            if found:
                out += prefix_marker + [marker(suffix)] + found
        return out

    # -----------------------------------------------------------------
    #  qu- pronouns and packons

    def _qu_words(self, w: str, opts: Opts) -> list[Parse]:
        """qui, quis, aliquis ...; with a tickon (a prefix that goes on qu-
        pronouns: ecquis ...) or a packon (an enclitic that does:
        quicumque ...)."""
        for tickon in self.lex.tickons + [None]:
            q = w if tickon is None else self.strip_prefix(w, tickon, opts)
            if tickon is not None and q == w:
                continue
            if len(q) >= 3 and q[:2] in ('qu', 'cu'):
                found = self._qu_pronouns(q, 1 if q[:2] == 'qu' else 2)
                if not found:
                    found = self._packons(q)
            elif len(w) >= 6 and w[:5] in ('aliqu', 'alicu'):
                found = self._qu_pronouns(w, 1 if w[:5] == 'aliqu' else 2)
            else:
                found = []
            if found:
                return ([marker(tickon)] if tickon else []) + found
        return []

    def _qu_split(self, w: str, longest: int, test) -> list[Parse]:
        out = []
        for z in range(min(longest, len(w)), 0, -1):
            for infl in self.lex.qu_endings.get(fold(w[-z:]), ()):
                if test(infl):
                    out.append(Parse(w[:-z], infl, Origin.NONE))
        return out

    @staticmethod
    def _as_pronoun(c: Parse, ref: StemRef) -> Parse:
        f = c.form
        form = Form(Pos.PRON, ref.part.decl, f.case, f.number, f.gender)
        return Parse(c.stem, replace(c.infl, form=form), _origin(ref),
                     ref.entry)

    def _qu_pronouns(self, w: str, qkey: int) -> list[Parse]:
        candidates = self._qu_split(w, 4, lambda i: i.key == qkey)
        out = []
        for ref in self.search({c.stem for c in candidates}, QU_PRONOUNS):
            for c in candidates:
                if fold(c.stem) == fold(ref.stem) and \
                        ref.part.decl == c.form.decl:
                    out.append(self._as_pronoun(c, ref))
        return out

    def _packons(self, w: str) -> list[Parse]:
        out = []
        for packon in self.lex.packons:
            x = self.strip_tackon(w, packon)
            if x == w:
                continue
            if packon.fix.startswith('dam') and x.endswith('n'):
                x = x[:-1] + 'm'                # quendam -> quem + dam
            candidates = self._qu_split(
                x, 6, lambda i: i.form.decl.fits(packon.base.decl))
            found = []
            for ref in self.search({c.stem for c in candidates}, PACKONS):
                if not ref.entry.meaning.strip().startswith(
                        '(w/-' + packon.fix):
                    continue
                for c in candidates:
                    if fold(c.stem) == fold(ref.stem) and \
                            ref.part.decl == c.form.decl:
                        found.append(self._as_pronoun(c, ref))
            if found:
                out += [marker(packon)] + found
        return out

    # -----------------------------------------------------------------
    #  Tackons

    def _tackons(self, w: str, opts: Opts, prior: int) -> list[Parse]:
        """The less common enclitics, which attach to particular words."""
        for tackon in self.lex.tackons[ENCLITICS:]:
            less = self.strip_tackon(w, tackon)
            if less == w:
                continue
            found = self.word(less, opts, prior)
            if not found:
                continue
            base = tackon.base
            if base.pos == Pos.X:
                return [marker(tackon)] + found
            kept = []
            hit = on = False
            for p in reversed(found):
                pos = p.form.pos
                if pos in (Pos.PREFIX, Pos.SUFFIX) and on:
                    on = False
                elif pos == base.pos and (
                        pos == Pos.ADJ or (pos in (Pos.N, Pos.PRON) and
                                           p.form.decl.fits(base.decl))):
                    hit = on = True
                else:
                    continue
                kept.insert(0, p)
            if hit:
                return [marker(tackon)] + kept
        return []

    def enclitic(self, w: str, out: list[Parse], opts: Opts,
                 notes: dict) -> bool:
        """Tries the word without -que, -ne, -ve or -est (only -que if it
        already has analyses).  Appends to OUT; returns whether one
        worked."""
        for tackon in self.lex.tackons[:ENCLITICS if not out else 1]:
            less = self.strip_tackon(w.lower(), tackon)
            if less == w.lower():
                continue
            found = self.word(less, opts, len(out))
            if not out and not found:
                found = tricks.slury(self, less, opts, notes, len(out))
            if self.settings.do_syncope and not _is_esse(out + found):
                found += tricks.syncope(self, less, opts, notes,
                                        len(out) + len(found))
            if found:
                out += [marker(tackon)] + found
                return True
            return False
        return False

    # -----------------------------------------------------------------
    #  A word in a line

    def analyze_word(self, word: str, next_word: str = '',
                     capitalized: bool = False, all_caps: bool = False,
                     followed_by_period: bool = False,
                     meanings_only: bool = False) -> tuple[WordResult, bool]:
        """Returns the result and whether NEXT_WORD (a form of esse) was
        used to make a compound tense."""
        s = self.settings
        notes: dict[Origin, str] = {}
        self.word_number += 1
        out = self._passes(word, notes)
        if not out and not (s.ignore_unknown_names and capitalized):
            if s.do_tricks:
                found = tricks.try_tricks(self, word, notes, capitalized)
                if not found:
                    found = self._tricks_enclitic(word, notes, capitalized)
                out += found
        used_next = False
        if out and s.do_compounds and not meanings_only:
            out, used_next = compounds(out, next_word, notes)
        if s.do_fixes and not any(p.form.pos == Pos.ADV for p in out):
            out += adverbs(out, notes)
        parses, trimmed = sweep(out, s, all_caps, followed_by_period)
        return WordResult(word, group(parses), notes, trimmed), used_next

    def _passes(self, word: str, notes: dict) -> list[Parse]:
        s = self.settings
        out = tricks.roman_numeral(word, notes)
        first = Opts(False, s.do_only_fixes, s.use_prefixes)
        out += self.word(word, first, len(out))
        if not out:
            out += tricks.slury(self, word, first, notes, 0)
        if s.do_syncope and not _is_esse(out):
            out += tricks.syncope(self, word, first, notes, len(out))
        done = self.enclitic(word, out, first, notes)
        if not out and s.do_fixes:
            second = Opts(True, True, s.use_prefixes)
            out += self.word(word, second, 0)
            if s.do_syncope:
                out += tricks.syncope(self, word, second, notes, len(out))
            if not done:
                self.enclitic(word, out, second, notes)
        return out

    def _tricks_enclitic(self, word: str, notes: dict,
                         capitalized: bool) -> list[Parse]:
        for tackon in self.lex.tackons[:ENCLITICS]:
            less = self.strip_tackon(word.lower(), tackon)
            if less != word.lower():
                found = tricks.try_tricks(self, less, notes, capitalized)
                return [marker(tackon)] + found if found else []
        return []

    def analyze_line(self, line: str,
                     meanings_only: bool = False) -> list[WordResult]:
        """Analyses each word of a line of Latin.  Text after '--' is a
        comment."""
        self.line_number += 1
        self.word_number = 0
        words = split_line(line)
        results = []
        skip = False
        for i, raw in enumerate(words):
            if skip:
                skip = False
                continue
            followed_by_period = raw.endswith('.')
            word = qv_to_qu(raw.rstrip('.'))
            next_word = words[i + 1] if i + 1 < len(words) else ''
            result, skip = self.analyze_word(
                word, next_word, is_capitalized(word), is_all_caps(word),
                followed_by_period, meanings_only)
            results.append(result)
            if self.settings.do_only_initial_word:
                break
        return results


# ---------------------------------------------------------------------------
#  Lines and words

def split_line(line: str) -> list[str]:
    """The words of LINE: runs of letters, each with a following '.' if
    there is one."""
    line = line.split('--', 1)[0]
    return re.findall(r'[A-Za-z]+\.?', line)


def qv_to_qu(word: str) -> str:
    """QVAE (inscriptional capitals) is QUAE."""
    return word.replace('qv', 'qu').replace('QV', 'QU')


def is_capitalized(word: str) -> bool:
    return len(word) > 1 and word[0].isupper() and word[1].islower()


def is_all_caps(word: str) -> bool:
    return word.isupper()


def _is_esse(parses: list[Parse]) -> bool:
    """A form of esse is not tried as a syncopated perfect."""
    return any(p.form.pos == Pos.V and p.form.decl == Decl(5, 1)
               for p in parses)


# ---------------------------------------------------------------------------
#  Compound tenses: participle + esse

PERF_PASSIVE = (Tense.PERF, Voice.PASSIVE, Mood.PPL)
FUT_ACTIVE = (Tense.FUT, Voice.ACTIVE, Mood.PPL)
FUT_PASSIVE = (Tense.FUT, Voice.PASSIVE, Mood.PPL)

WITH_SUM = {
    PERF_PASSIVE: 'PERF PASSIVE PPL + verb TO_BE => PASSIVE perfect system',
    FUT_ACTIVE: 'FUT ACTIVE PPL + verb TO_BE => ACTIVE Periphrastic - '
                'about to, going to',
    FUT_PASSIVE: 'FUT PASSIVE PPL + verb TO_BE => PASSIVE Periphrastic - '
                 'should/ought/had to',
}
WITH_ESSE = {
    PERF_PASSIVE: 'PERF PASSIVE PPL + esse => PERF PASSIVE INF',
    FUT_ACTIVE: 'FUT ACTIVE PPL + esse => PRES Periphastic/FUT ACTIVE INF - '
                'be about/going to',
    FUT_PASSIVE: 'FUT PASSIVE PPL + esse => PRES PASSIVE INF',
}
WITH_FUISSE = {
    PERF_PASSIVE: 'PERF PASSIVE PPL + esse => PERF PASSIVE INF',
    FUT_ACTIVE: 'FUT ACT PPL+fuisse => PERF ACT INF Periphrastic - to have '
                'been about/going to',
    FUT_PASSIVE: 'FUT PASSIVE PPL + fuisse => PERF PASSIVE INF Periphrastic '
                 '- about to, going to',
}
SUPINE_IRI = 'SUPINE + iri => FUT PASSIVE INF - to be about/going/ready to ' \
    'be ~'

_SUM = {
    Mood.IND: {
        Tense.PRES: ('sum es est', 'sumus estis sunt'),
        Tense.IMPF: ('eram eras erat', 'eramus eratis erant'),
        Tense.FUT: ('ero eris erit', 'erimus eritis erunt'),
        Tense.PERF: ('fui fuisti fuit', 'fuimus fuistis fuerunt'),
        Tense.PLUP: ('fueram fueras fuerat', 'fueramus fueratis fuerant'),
        Tense.FUTP: ('fuero fueris fuerit', 'fuerimus fueritis fuerunt'),
    },
    Mood.SUB: {
        Tense.PRES: ('sim sis sit', 'simus sitis sint'),
        Tense.IMPF: ('essem esses esset', 'essemus essetis essent'),
        Tense.PERF: ('fuerim fueris fuerit', 'fuerimus fueritis fuerint'),
        Tense.PLUP: ('fuissem fuisses fuisset',
                     'fuissemus fuissetis fuissent'),
    },
}


def form_of_sum(word: str) -> Form | None:
    """The form of sum that WORD is (the first, if it is several)."""
    for mood, tenses in _SUM.items():
        for tense, numbers in tenses.items():
            for number, forms in zip((Number.S, Number.P), numbers,
                                     strict=True):
                for person, form in enumerate(forms.split(), 1):
                    if word == form:
                        return Form(Pos.V, Decl(5, 1), number=number,
                                    tense=tense, voice=Voice.ACTIVE,
                                    mood=mood, person=person)
    return None


def compounds(parses: list[Parse], next_word: str,
              notes: dict) -> tuple[list[Parse], bool]:
    """If NEXT_WORD is a form of esse (or iri) that makes a compound tense
    with a participle (or supine) among PARSES, keeps only those and adds
    the compound.  Returns the parses and whether NEXT_WORD was used."""
    sum_form = form_of_sum(next_word)

    def keep_affixes(test, update):
        """Keeps the parses that pass TEST, and the affix markers of those
        that UPDATE (called on each, last first) accepts."""
        kept = []
        on = False
        for p in reversed(parses):
            if p.form.pos in AFFIX_POS and on:
                kept.insert(0, p)
            elif test(p):
                if update(p):
                    on = True
                kept.insert(0, p)
            else:
                on = False
        return kept

    if sum_form is not None:
        if not any(p.form.pos == Pos.VPAR and p.form.case == Case.NOM and
                   p.form.number == sum_form.number and
                   p.form.tvm in WITH_SUM for p in parses):
            return parses, False
        found = {}

        def update(p):
            if p.form.tvm not in WITH_SUM:
                return False
            if p.form.tvm == PERF_PASSIVE:
                tense = {Tense.PRES: Tense.PERF, Tense.PERF: Tense.PERF,
                         Tense.IMPF: Tense.PLUP, Tense.PLUP: Tense.PLUP,
                         Tense.FUT: Tense.FUTP}.get(sum_form.tense, Tense.X)
            else:
                tense = sum_form.tense
            found.update(decl=p.form.decl, tense=tense, voice=p.form.voice,
                         note=WITH_SUM[p.form.tvm])
            return True
        kept = keep_affixes(
            lambda p: p.form.pos == Pos.VPAR and p.form.case == Case.NOM and
            p.form.number == sum_form.number, update)
        if 'note' in found:
            notes[Origin.COMPOUND] = found['note']
        kept.append(Parse('PPL+' + next_word, Inflection(
            Form(Pos.V, found.get('decl', Decl()), number=sum_form.number,
                 tense=found.get('tense', Tense.X),
                 voice=found.get('voice', Voice.X), mood=sum_form.mood,
                 person=sum_form.person), freq=Freq.A), Origin.COMPOUND))
        return kept, True

    if next_word in ('esse', 'fuisse'):
        esse = next_word == 'esse'
        if not any(p.form.pos == Pos.VPAR and (
                (p.form.tvm == PERF_PASSIVE and esse) or
                p.form.tvm in (FUT_ACTIVE, FUT_PASSIVE)) for p in parses):
            return parses, False
        found = {}

        def update(p):
            tvm = p.form.tvm
            if tvm not in WITH_ESSE:
                return False
            if p.form.tense == Tense.FUT:
                if not esse:
                    tense = Tense.PERF
                else:
                    tense = Tense.FUT if p.form.voice == Voice.ACTIVE \
                        else Tense.PRES
            else:
                tense = p.form.tense
            found.update(decl=p.form.decl, tense=tense, voice=p.form.voice,
                         note=(WITH_ESSE if esse else WITH_FUISSE)[tvm])
            return True
        kept = keep_affixes(lambda p: p.form.pos == Pos.VPAR, update)
        if 'note' in found:
            notes[Origin.COMPOUND] = found['note']
        kept.append(Parse('PPL+' + next_word, Inflection(
            Form(Pos.V, found.get('decl', Decl()),
                 tense=found.get('tense', Tense.X),
                 voice=found.get('voice', Voice.X), mood=Mood.INF),
            freq=Freq.A), Origin.COMPOUND))
        return kept, True

    if next_word == 'iri':
        supines = [p for p in parses if p.form.pos == Pos.SUPINE and
                   p.form.case == Case.ACC]
        if not supines:
            return parses, False
        kept = keep_affixes(lambda p: p.form.pos == Pos.SUPINE and
                            p.form.case == Case.ACC, lambda p: True)
        for p in reversed(supines):
            kept.append(Parse('SUPINE + iri', Inflection(
                Form(Pos.V, p.form.decl, tense=Tense.FUT,
                     voice=Voice.PASSIVE, mood=Mood.INF), freq=Freq.A),
                Origin.COMPOUND))
        notes[Origin.COMPOUND] = SUPINE_IRI
        return kept, True
    return parses, False


# ---------------------------------------------------------------------------
#  Adverbs from adjectives: longe from longus

def adverbs(parses: list[Parse], notes: dict) -> list[Parse]:
    """For an adjective found as a vocative singular masculine (longe,
    longissime), the adverb made from it."""
    out = []
    for i in range(len(parses) - 1, -1, -1):
        p = parses[i]
        f = p.form
        if f.pos != Pos.ADJ or f.case != Case.VOC or f.number != Number.S \
                or f.gender != Gender.M:
            continue
        if f.comparison == Comparison.POS and f.decl == Decl(1, 1):
            ending, note = 'e', '-ly; -ily;  Converting ADJ to ADV'
        elif f.comparison == Comparison.SUPER:
            ending, note = 'me', '-estly; -estily; most -ly, very -ly  ' \
                'Converting ADJ to ADV'
        else:
            continue
        #  The affixes found on the adjective apply to the adverb too
        j = i
        while j > 0 and parses[j - 1].form.pos == Pos.ADJ:
            j -= 1
        affixes = []
        while j > 0 and parses[j - 1].form.pos in AFFIX_POS:
            j -= 1
            affixes.insert(0, parses[j])
        out += affixes
        out.append(Parse('e', Inflection(Form(Pos.SUFFIX), freq=Freq.B),
                         Origin.COMPOUND))
        out.append(Parse(p.stem, Inflection(
            Form(Pos.ADV, comparison=f.comparison), ending=ending,
            freq=Freq.B), p.origin, p.source))
        notes[Origin.COMPOUND] = note
    return out

