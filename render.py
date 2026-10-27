"""The text WORDS shows for its results.

    amicus
      amicus, amici  noun, 2nd declension, masculine  [XXXBO]
        friend, ally, disciple; loved one; patron; ...
        amic-us   nominative singular

Each word is followed by its readings: a dictionary entry (its principal
parts and grammar, its meaning, then the forms the word can be), an
irregular form, an affix or enclitic found on the word, or a note on a
trick that was needed to find it.  The meanings are in the language given
(see languages.py), and so is the rest, if the language translates it
(Language.text).
"""

from __future__ import annotations

from forms import (principal_parts, describe_part, describe_form,
                   gloss_form,
                    deponent, stem_and_ending, POS_NAME)
from languages import Language
from model import Pos, Age, Freq, NumeralSort, Entry, Form, Unique, \
    Prefix, Suffix, Tackon, fold, marked_like
from results import Origin, Parse, Reading, WordResult
from reverse import Hit
from settings import Settings

#  Pearse codes (the pearse_codes developer mode): each line starts with
#  a number saying what it is.
UNKNOWN_CODE, FORM_CODE, ENTRY_CODE, MEANING_CODE, UNKNOWN_FILE_CODE, \
    AFFIX_CODE, TRICK_CODE = range(7)

ENTRY_AGE = {Age.A: 'archaic', Age.B: 'early', Age.C: 'classical',
             Age.D: 'late', Age.E: 'later', Age.F: 'medieval',
             Age.G: 'neo-Latin', Age.H: 'modern'}
ENTRY_FREQ = {Freq.A: 'very frequent', Freq.B: 'frequent', Freq.C: 'common',
              Freq.D: 'lesser', Freq.E: 'uncommon', Freq.F: 'very rare',
              Freq.I: 'inscriptions', Freq.M: 'graffiti', Freq.N: 'Pliny'}
FORM_AGE = {Age.X: 'always', Age.A: 'archaic', Age.B: 'early',
            Age.C: 'classical', Age.D: 'late', Age.E: 'later',
            Age.F: 'medieval', Age.G: 'scholarly', Age.H: 'modern'}
FORM_FREQ = {Freq.A: 'most frequent', Freq.B: 'sometimes',
             Freq.C: 'uncommon', Freq.D: 'infrequent', Freq.E: 'rare',
             Freq.F: 'very rare', Freq.I: 'inscriptions'}

TRICK_TITLE = {Origin.TRICK: 'spelling', Origin.SYNCOPE: 'syncope'}


class Renderer:
    def __init__(self, settings: Settings, meanings_only: bool = False,
                 glosses: dict[tuple[str, str], str] | None = None,
                 language: Language | None = None,
                 long_stems: dict[int, tuple[str, ...]] | None = None):
        """GLOSSES: the abbreviations for the analyses (from gloss.xml);
        without them the analyses are in words.  LANGUAGE: that of the
        meanings (None: those of the data files, in English).  LONG_STEMS:
        the stems with their long vowels marked (Lexicon.long_stems)."""
        self.s = settings
        self.long_stems = long_stems or {}
        self.meanings_only = meanings_only or settings.show_only_meanings
        self.glosses = glosses or {}
        self.language = language
        self.lines: list[str] = []

    def t(self, english: str) -> str:
        """A text of the results, in the language of the meanings."""
        if self.language is None:
            return english
        return self.language.text(english)

    def meaning(self, thing) -> str:
        """The meaning of an entry, irregular form or affix."""
        if self.language is None:
            return thing.meaning
        return self.language.meaning(thing)

    def shown_meaning(self, entry: Entry) -> str:
        """The meaning of an entry as the results show it: without the
        bars of WORDS that mark the further senses of a word (|...)."""
        return self.meaning(entry).lstrip('|').strip()

    def meaning_of(self, entry: Entry, p: Parse) -> str:
        """The meaning of an entry; for a numeral, what this form
        means."""
        m = self.shown_meaning(entry)
        part = entry.part
        if part.pos != Pos.NUM or part.value <= 0 or self.language is None:
            return m
        if p.form.pos != Pos.NUM:
            sort = NumeralSort.X            # (an adverb, say)
        elif p.form.sort == NumeralSort.X:
            return m
        else:
            sort = p.form.sort
        return self.language.numeral(sort, part.value) or m

    def describe(self, form: Form, deponent: bool = False) -> str:
        """The analysis of a form: "GEN.PL" (with use_glosses, if there
        are glosses), or "genitive plural"."""
        if self.glosses and self.s.use_glosses:
            return gloss_form(form, self.glosses, deponent)
        return describe_form(form, deponent, self.t)

    def line(self, text: str, indent: int = 0, code: int | None = None):
        if self.s.pearse_codes and code is not None:
            text = f'{code:02d} {text}'
        else:
            text = ' ' * indent + text
        self.lines.append(text.rstrip())

    def text(self) -> str:
        out = '\n'.join(self.lines)
        self.lines = []
        return out + '\n' if out else ''

    # Latin to the language of the meanings ---------------------------------

    def word(self, result: WordResult, show_unknown_list=None,
             near: list[str] = ()) -> str:
        """The text for one analysed word (and, if it is unknown, the
        NEAR spellings whose results follow)."""
        self.line(result.word)
        if result.unknown:
            self.line(self.t('(unknown)'), 2, UNKNOWN_CODE)
            if show_unknown_list:
                for entry in show_unknown_list:
                    self.neighbour(entry)
            if near:
                self.line(self.t(f'(near spellings: {", ".join(near)})'), 2)
            return self.text()
        shown = set()
        for reading in result.readings:
            self.reading(reading, result, shown)
        if result.trimmed:
            self.line(self.t('(less likely forms are not shown)'), 2)
        return self.text()

    def reading(self, r: Reading, result: WordResult, shown: set):
        src = r.source
        if isinstance(src, (Prefix, Suffix, Tackon)):
            self.affix(src)
        elif r.origin in (Origin.TRICK, Origin.SYNCOPE):
            label = r.forms[0].stem
            self.line(f'{self.t(TRICK_TITLE[r.origin])}: {self.t(label)}',
                      2, TRICK_CODE)
            note = result.notes.get(r.origin)
            if note and r.origin not in shown:
                self.line(self.t(note), 4, TRICK_CODE)
                shown.add(r.origin)
        elif r.origin == Origin.COMPOUND and r.pos == Pos.SUFFIX:
            self.line(f'-{r.forms[0].stem}  '
                      + self.t('suffix: adverb from adjective'),
                      2, AFFIX_CODE)
        elif r.origin == Origin.ROMAN:
            self.line(f'{r.forms[0].stem}  ' + self.t('Roman numeral'), 2,
                      ENTRY_CODE)
            note = result.notes.get(Origin.ROMAN)
            if note:
                self.line(note.split('  ')[0], 4, MEANING_CODE)
        elif isinstance(src, Unique):
            self.unique(r, src)
        elif isinstance(src, Entry):
            self.entry(r, src, result)

    def affix(self, a):
        if isinstance(a, Prefix):
            title = f'{a.fix}-  ' + self.t('prefix')
        elif isinstance(a, Suffix):
            title = f'-{a.fix}  ' + self.t('suffix')
        else:
            title = f'-{a.fix}  ' + self.t('enclitic')
        self.line(title, 2, AFFIX_CODE)
        if not self.s.show_dictionary_forms:
            return
        self.line(self.meaning(a).strip(), 4, MEANING_CODE)

    def entry_header(self, entry: Entry) -> str:
        words = []
        if self.s.show_dictionary_forms:
            words.append(principal_parts(entry, self.t))
            words.append(describe_part(entry.part, self.t))
        if self.s.show_codes:
            words.append(f'[{entry.codes}]')
        flags = []
        if self.s.explain_codes or entry.codes.age != Age.X:
            flags.append(ENTRY_AGE.get(entry.codes.age))
        if self.s.explain_codes or entry.codes.freq >= Freq.D:
            flags.append(ENTRY_FREQ.get(entry.codes.freq))
        words += [self.t(f) for f in flags if f]
        if self.s.show_entry_source:
            words.append(self.t(f'({entry.dictionary} dictionary)'))
            words.append(self.t(f'(entry {entry.id})'))
        return '  '.join(w for w in words if w)

    def entry(self, r: Reading, entry: Entry, result: WordResult):
        header = self.entry_header(entry)
        if header:
            self.line(header, 2, ENTRY_CODE)
        self.line(self.meaning_of(entry, r.forms[0]), 4, MEANING_CODE)
        if self.meanings_only or r.pos in (Pos.CONJ, Pos.INTERJ):
            return              # (the form says no more than the header)
        for p in r.forms:
            self.form(p, entry, result)

    def unique(self, r: Reading, u: Unique):
        words = [u.word, self.t(POS_NAME.get(u.form.pos, ''))]
        if self.s.show_codes:
            words.append(f'[{u.codes}]')
        self.line('  '.join(w for w in words if w), 2, ENTRY_CODE)
        self.line(self.meaning(u), 4, MEANING_CODE)
        if not self.meanings_only:
            for p in r.forms:
                self.form(p, None, None)

    def form(self, p: Parse, entry: Entry | None, result):
        if p.origin == Origin.COMPOUND and p.stem.startswith(
                ('PPL+', 'SUPINE')):
            words = p.stem.replace(
                'PPL+', self.t('participle') + ' + ').replace(
                'SUPINE + ', self.t('supine') + ' + ')
            text = columns(words, self.describe(p.form))
        else:
            description = self.describe(p.form, deponent(entry))
            if entry is not None and p.form.pos not in (
                    entry.part.pos, Pos.VPAR, Pos.SUPINE) and not (
                    entry.part.pos == Pos.PACK and p.form.pos == Pos.PRON):
                # made by a suffix: ludus -> ludic-a, an adjective
                pos = POS_NAME.get(p.form.pos)
                description = ', '.join(
                    x for x in (pos and self.t(pos), description) if x)
            text = columns(stem_and_ending(self.marked(p.stem, entry),
                                           self.long_ending(p)), description)
        extra = []
        if self.s.explain_codes or p.infl.age != Age.X:
            extra.append(FORM_AGE.get(p.infl.age))
        if self.s.explain_codes or p.infl.freq >= Freq.C:
            extra.append(FORM_FREQ.get(p.infl.freq))
        extra = [self.t(e) for e in extra if e]
        if extra:
            text += f"  ({', '.join(extra)})"
        self.line(text, 4, FORM_CODE)
        if p.origin == Origin.COMPOUND and result is not None:
            note = result.notes.get(Origin.COMPOUND)
            if note:
                self.line(self.t(note), 6, MEANING_CODE)

    def marked(self, stem: str, entry: Entry | None) -> str:
        """STEM with its long vowels marked, if it is one of ENTRY's stems
        and show_long_vowels is on (amic -> amīc)."""
        marked = self.long_stems.get(entry.uid) \
            if entry is not None and self.s.show_long_vowels and \
            entry.dictionary == 'general' else None
        if not marked:
            return stem
        for m, s in zip(marked, entry.stems):
            if m != '-' and fold(s) == fold(stem):
                return marked_like(stem, m)
        return stem

    def long_ending(self, p: Parse) -> str:
        """P's ending with its long vowels marked, if show_long_vowels is
        on (abat -> ābat)."""
        if self.s.show_long_vowels and p.infl.long:
            return marked_like(p.infl.ending, p.infl.long)
        return p.infl.ending

    def neighbour(self, entry: Entry):
        self.line(self.t('near:') + ' ' + self.entry_header(entry), 2,
                  ENTRY_CODE)
        self.line(self.shown_meaning(entry), 4, MEANING_CODE)

    # From the language of the meanings to Latin ----------------------------

    def reverse(self, word: str, hits: list[Hit],
                near: list[str] = ()) -> str:
        """The text for the entries found for WORD (and, if there are
        none, the NEAR words whose entries follow)."""
        self.line(word)
        if not hits:
            self.line(self.t('(no match)'), 2)
            if near:
                self.line(self.t(f'(near words: {", ".join(near)})'), 2)
            return self.text()
        shown = hits
        if self.s.trim_output and len(hits) > 6:
            shown = hits[:6]
        for h in shown:
            header = self.entry_header(h.entry)
            self.line(header, 2, ENTRY_CODE)
            self.line(self.shown_meaning(h.entry), 4, MEANING_CODE)
        if len(shown) < len(hits):
            self.line(self.t(f'({len(hits) - len(shown)} more not shown)'),
                      2)
        return self.text()


def columns(left: str, right: str, width: int = 14) -> str:
    if not right:
        return left
    if len(left) < width:
        return left.ljust(width) + ' ' + right
    return left + '  ' + right
