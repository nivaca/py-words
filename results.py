"""What analysis finds for a word, and how the findings are ordered,
trimmed and grouped for display.

The analyzer produces a flat list of `Parse`s.  Some are *markers*: a
prefix, suffix or enclitic found on the word, or a note that a trick (a
spelling change, a syncopated form ...) was needed.  A marker applies to
the parses that follow it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import IntEnum

from model import (Pos, Case, Number, Gender, Tense, Voice, Mood, Age,
                    Freq, Decl, VerbKind, Form, Inflection, Entry, Unique,
                    Prefix, Suffix, Tackon, NO_INFLECTION)
from settings import Settings


class Origin(IntEnum):
    """Where a parse comes from."""
    NONE = 0
    ADDON = 1           # a prefix, suffix or tackon (marker)
    TRICK = 2           # a spelling change, two words ... (marker)
    SYNCOPE = 3         # a syncopated form (marker)
    ROMAN = 5           # a Roman numeral
    COMPOUND = 6        # a compound with esse, or an adverb made from an ADJ
    GENERAL = 7         # the general dictionary
    SPECIAL = 8         # the special dictionary
    UNIQUE = 10         # an irregular form


MARKER_ORIGINS = (Origin.ADDON, Origin.TRICK, Origin.SYNCOPE)
TRICK_ORIGINS = (Origin.TRICK, Origin.SYNCOPE, Origin.COMPOUND)
AFFIX_POS = (Pos.TACKON, Pos.PREFIX, Pos.SUFFIX)

Source = Entry | Unique | Prefix | Suffix | Tackon | None


@dataclass(frozen=True, slots=True)
class Parse:
    stem: str                       # or, for a trick marker, its label
    infl: Inflection
    origin: Origin
    source: Source = None

    @property
    def form(self) -> Form:
        return self.infl.form

    @property
    def id(self) -> int:
        return self.source.id if self.source is not None else 0

    @property
    def entry(self) -> Entry | None:
        return self.source if isinstance(self.source, Entry) else None

    @property
    def is_marker(self) -> bool:
        return self.origin in MARKER_ORIGINS or self.form.pos in AFFIX_POS

    @property
    def meaning(self) -> str:
        if isinstance(self.source, (Entry, Unique)):
            return self.source.meaning
        return ''


def from_dictionary(origin: Origin) -> bool:
    return origin in (Origin.GENERAL, Origin.SPECIAL)


def marker(addon: Prefix | Suffix | Tackon) -> Parse:
    pos = {Prefix: Pos.PREFIX, Suffix: Pos.SUFFIX,
           Tackon: Pos.TACKON}[type(addon)]
    return Parse(addon.fix, Inflection(Form(pos)), Origin.ADDON, addon)


def trick_marker(label: str, origin: Origin = Origin.TRICK) -> Parse:
    return Parse(label, NO_INFLECTION, origin)


@dataclass(slots=True)
class Reading:
    """Forms of one word: a dictionary entry, an irregular form, an affix
    or a trick, with the stems and endings that make them."""
    origin: Origin
    source: Source
    forms: list[Parse] = field(default_factory=list)

    @property
    def pos(self) -> Pos:
        return self.forms[0].form.pos


@dataclass(slots=True)
class WordResult:
    word: str
    readings: list[Reading] = field(default_factory=list)
    #  The explanations of tricks, by origin (several tricks of the same
    #  kind share the last explanation, as in the original program)
    notes: dict[Origin, str] = field(default_factory=dict)
    trimmed: bool = False

    @property
    def unknown(self) -> bool:
        return not self.readings


# ---------------------------------------------------------------------------
#  Ordering and trimming (List_Sweep)

_DIC_STEMS = ('dic', 'duc', 'fac', 'fer')


def allowed(p: Parse, settings: Settings) -> bool:
    """Whether a parse from the dictionary is a possible word, or (with
    for_word_list_check) a dictionary form."""
    if not from_dictionary(p.origin):
        return True
    f = p.form
    check = settings.for_word_list_check
    ok = True
    if f.pos == Pos.N and check:
        nominative = f.case in (Case.NOM, Case.X)
        if nominative and f.number in (Number.S, Number.X):
            ok = True
        elif nominative and f.number == Number.P:
            ok = 'pl.' in p.source.meaning
        else:
            ok = False
    elif f.pos == Pos.ADJ and check:
        ok = f.case in (Case.NOM, Case.X) and \
            f.number in (Number.S, Number.X) and \
            f.gender in (Gender.M, Gender.C, Gender.X)
    elif f.pos == Pos.V:
        kind = p.source.part.kind if p.source.part.pos == Pos.V else None
        if f.decl == Decl(3, 1) and f.tvm == (Tense.PRES, Voice.ACTIVE,
                                               Mood.IMP) \
                and f.person == 2 and f.number == Number.S \
                and not p.infl.ending:
            # dic, duc, fac, fer: the only short imperatives
            ok = p.stem[-3:] in _DIC_STEMS
        if f.mood == Mood.IMP and not (
                (f.tense == Tense.PRES and f.person == 2) or
                (f.tense == Tense.FUT and f.person in (2, 3))):
            ok = False
        if kind == VerbKind.IMPERS and f.person != 3:
            ok = False
        if kind == VerbKind.DEP:
            if f.voice == Voice.ACTIVE and f.mood == Mood.INF and \
                    f.tense == Tense.FUT:
                ok = True
            elif f.voice == Voice.ACTIVE and \
                    Mood.IND <= f.mood <= Mood.INF:
                ok = False
        if kind == VerbKind.SEMIDEP and Mood.IND <= f.mood <= Mood.IMP and (
                (f.voice == Voice.PASSIVE and
                 Tense.PRES <= f.tense <= Tense.FUT) or
                (f.voice == Voice.ACTIVE and
                 Tense.PERF <= f.tense <= Tense.FUTP)):
            ok = False
        if check:
            if f.person == 1 and f.number == Number.S:
                ok = f.tvm == (Tense.PRES, Voice.ACTIVE, Mood.IND) and (
                    kind is None or kind <= VerbKind.INTRANS or
                    kind in (VerbKind.DEP, VerbKind.SEMIDEP,
                             VerbKind.PERFDEF))
            elif kind == VerbKind.IMPERS:
                ok = f.person == 3 and f.number == Number.S and \
                    f.tvm == (Tense.PRES, Voice.ACTIVE, Mood.IND)
            else:
                ok = False
    if check and f.pos in (Pos.VPAR, Pos.SUPINE):
        ok = False
    return ok


def _is_qu_pronoun(f: Form) -> bool:
    return f.pos == Pos.PRON and f.decl.which == 1


def _order(p: Parse) -> tuple:
    """Dictionary parses come entry by entry; within an entry, by form.
    The qu- pronouns (qui, quis ...) are ordered by the kind of their entry
    (relative, interrogative ...)."""
    f = p.form
    if _is_qu_pronoun(f) and p.entry is not None:
        form_key = (Pos.PRON, (int(p.entry.part.kind or 0),))
    else:
        form_key = f.order()
    return (-p.origin, p.id, form_key, p.meaning, len(p.infl.ending),
            f.order())


def _sort_and_trim(block: list[Parse], settings: Settings, all_caps: bool,
                   followed_by_period: bool) -> (list[Parse], bool):
    block = sorted(block, key=_order)
    if not settings.trim_output:
        return block, False
    entries = [p for p in block if from_dictionary(p.origin)]

    def not_only(test_infl, test_entry):
        return any(test_infl(p.infl) and test_entry(p.entry.codes)
                   for p in entries)
    not_only_archaic = not_only(
        lambda i: i.age == Age.X or i.age > Age.A,
        lambda c: c.age == Age.X or c.age > Age.A)
    not_only_medieval = not_only(
        lambda i: i.age == Age.X or i.age < Age.F,
        lambda c: c.age == Age.X or c.age < Age.F)
    not_only_uncommon = not_only(
        lambda i: i.freq == Freq.X or i.freq < Freq.C,
        lambda c: c.freq == Freq.X or c.freq < Freq.D)
    has_abbreviation = any(p.form.pos == Pos.N and p.form.decl == Decl(9, 8)
                           for p in entries)
    abbreviation = Form(Pos.N, Decl(9, 8), gender=Gender.M)

    def keep(p: Parse) -> bool:
        if not allowed(p, settings):
            return False
        if not_only_archaic and settings.omit_archaic and \
                p.infl.age == Age.A:
            return False
        if not_only_medieval and settings.omit_medieval and \
                p.infl.age >= Age.F:
            return False
        if not_only_uncommon and settings.omit_uncommon and \
                p.infl.freq >= Freq.C:
            return False
        if has_abbreviation and all_caps and followed_by_period:
            # "M." is an abbreviation, not the Roman numeral
            return p.form.pos == Pos.N and (
                p.form == abbreviation or len(p.stem) != 1 or
                p.stem[0] not in 'ACDLM')
        return True
    kept = [p for p in block if keep(p)]
    return kept, len(kept) < len(block)


def sweep(parses: list[Parse], settings: Settings, all_caps=False,
          followed_by_period=False) -> (list[Parse], bool):
    """Orders the parses and removes unlikely and repeated ones.  Returns
    them and whether any were trimmed."""
    out: list[Parse] = []
    block: list[Parse] = []
    markers: list[Parse] = []       # the markers before BLOCK
    trimmed = False

    def flush():
        nonlocal trimmed
        kept, cut = _sort_and_trim(block, settings, all_caps,
                                   followed_by_period)
        if kept or not block:
            out.extend(markers)     # (markers of a block that was all
        out.extend(kept)            # trimmed go with it)
        trimmed = trimmed or cut
        block.clear()
        markers.clear()
    for p in parses:
        if p.is_marker:
            if block:
                flush()
            markers.append(p)
        else:
            block.append(p)
    flush()

    unique: list[Parse] = []
    for p in out:
        prev = unique[-1] if unique else None
        if prev is not None and p.origin not in TRICK_ORIGINS and (
                p == prev or (p.form == prev.form and p.id == prev.id)):
            continue
        unique.append(p)
    return [_for_display(p) for p in unique], trimmed


def _for_display(p: Parse) -> Parse:
    """The qu- pronouns are shown as PRON 1 0; verbs of conjugation 3 4
    (audio-like 3rd) as 4 1."""
    f = p.form
    if _is_qu_pronoun(f) and f.decl.var != 0:
        f = replace(f, decl=Decl(1, 0))
    elif f.pos == Pos.V and f.decl == Decl(3, 4):
        f = replace(f, decl=Decl(4, 1))
    else:
        return p
    return replace(p, infl=replace(p.infl, form=f))


# ---------------------------------------------------------------------------
#  Grouping (Cycle_Over_Pa)

NOMINAL = (Pos.N, Pos.PRON, Pos.PACK, Pos.ADJ, Pos.NUM)
VERBAL = (Pos.V, Pos.VPAR, Pos.SUPINE)


def group(parses: list[Parse]) -> list[Reading]:
    """Gathers consecutive parses of the same entry and part of speech into
    readings.  A compound with esse joins the reading of its participle."""
    readings: list[Reading] = []
    current: Reading | None = None
    for p in parses:
        pos = p.form.pos
        same = current is not None and current.pos == pos and \
            current.origin != Origin.UNIQUE and p.origin != Origin.UNIQUE
        if same and pos in NOMINAL and p.origin != Origin.ROMAN and \
                p.id == current.forms[0].id:
            current.forms.append(p)
            continue
        if same and pos in VERBAL and p.id == current.forms[0].id:
            current.forms.append(p)
            continue
        if p.origin == Origin.COMPOUND and pos in VERBAL and \
                current is not None and current.pos in VERBAL:
            current.forms.append(p)
            continue
        current = Reading(p.origin, p.source, [p])
        readings.append(current)
    return readings
