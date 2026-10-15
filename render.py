"""The text WORDS shows for its results.

    amicus
      amicus, amici  noun, 2nd declension, masculine  [XXXBO]
        friend, ally, disciple; loved one; patron; ...
        amic-us   nominative singular

Each word is followed by its readings: a dictionary entry (its principal
parts and grammar, its meaning, then the forms the word can be), an
irregular form, an affix or enclitic found on the word, or a note on a
trick that was needed to find it.
"""


from english import Hit
from forms import (principal_parts, describe_part, describe_form, example,
                    deponent, stem_and_ending, POS_NAME)
from model import Pos, Age, Freq, NumeralSort, Entry, Unique, Prefix, \
    Suffix, Tackon
from results import Origin, Parse, Reading, WordResult
from settings import Settings

#  Pearse codes (the do_pearse_codes developer mode): each line starts with
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
    def __init__(self, settings: Settings, meanings_only: bool = False):
        self.s = settings
        self.meanings_only = meanings_only or settings.do_only_meanings
        self.lines: list[str] = []

    def line(self, text: str, indent: int = 0, code: int | None = None):
        if self.s.do_pearse_codes and code is not None:
            text = '%02d %s' % (code, text)
        else:
            text = ' ' * indent + text
        self.lines.append(text.rstrip())

    def text(self) -> str:
        out = '\n'.join(self.lines)
        self.lines = []
        return out + '\n' if out else ''

    # Latin to English ------------------------------------------------------

    def word(self, result: WordResult, show_unknown_list=None) -> str:
        """The text for one analysed word."""
        self.line(result.word)
        if result.unknown:
            self.line('(unknown)', 2, UNKNOWN_CODE)
            if show_unknown_list:
                for entry in show_unknown_list:
                    self.neighbour(entry)
            return self.text()
        if self.s.do_unknowns_only:
            self.lines = []
            return ''
        shown = set()
        for reading in result.readings:
            self.reading(reading, result, shown)
        if result.trimmed:
            self.line('(less likely forms are not shown)', 2)
        return self.text()

    def reading(self, r: Reading, result: WordResult, shown: set):
        src = r.source
        if isinstance(src, (Prefix, Suffix, Tackon)):
            self.affix(src)
        elif r.origin in (Origin.TRICK, Origin.SYNCOPE):
            label = r.forms[0].stem
            self.line('%s: %s' % (TRICK_TITLE[r.origin], label), 2,
                      TRICK_CODE)
            note = result.notes.get(r.origin)
            if note and r.origin not in shown:
                self.line(note, 4, TRICK_CODE)
                shown.add(r.origin)
        elif r.origin == Origin.COMPOUND and r.pos == Pos.SUFFIX:
            self.line('-%s  suffix: adverb from adjective' % r.forms[0].stem,
                      2, AFFIX_CODE)
        elif r.origin == Origin.ROMAN:
            self.line('%s  Roman numeral' % r.forms[0].stem, 2, ENTRY_CODE)
            note = result.notes.get(Origin.ROMAN)
            if note:
                self.line(note.split('  ')[0], 4, MEANING_CODE)
        elif isinstance(src, Unique):
            self.unique(r, src)
        elif isinstance(src, Entry):
            self.entry(r, src, result)

    def affix(self, a):
        if isinstance(a, Prefix):
            title = '%s-  prefix' % a.fix
        elif isinstance(a, Suffix):
            title = '-%s  suffix' % a.fix
        else:
            title = '-%s  enclitic' % a.fix
        self.line(title, 2, AFFIX_CODE)
        if not self.s.do_dictionary_forms:
            return
        self.line(a.meaning.strip(), 4, MEANING_CODE)

    def entry_header(self, entry: Entry) -> str:
        words = []
        if self.s.do_dictionary_forms:
            words.append(principal_parts(entry))
            words.append(describe_part(entry.part))
        if self.s.show_dictionary_codes:
            words.append('[%s]' % entry.codes)
        flags = []
        if self.s.show_age or entry.codes.age != Age.X:
            flags.append(ENTRY_AGE.get(entry.codes.age))
        if self.s.show_frequency or entry.codes.freq >= Freq.D:
            flags.append(ENTRY_FREQ.get(entry.codes.freq))
        words += [f for f in flags if f]
        if self.s.show_dictionary:
            words.append('(%s dictionary)' % entry.dictionary)
        if self.s.show_dictionary_line:
            words.append('(entry %d)' % entry.id)
        return '  '.join(w for w in words if w)

    def entry(self, r: Reading, entry: Entry, result: WordResult):
        header = self.entry_header(entry)
        if header:
            self.line(header, 2, ENTRY_CODE)
        self.line(meaning_of(entry, r.forms[0]), 4, MEANING_CODE)
        if self.meanings_only or r.pos in (Pos.CONJ, Pos.INTERJ):
            return              # (the form says no more than the header)
        for p in r.forms:
            self.form(p, entry, result)

    def unique(self, r: Reading, u: Unique):
        words = [u.word, POS_NAME.get(u.form.pos, '')]
        if self.s.show_dictionary_codes:
            words.append('[%s]' % u.codes)
        self.line('  '.join(w for w in words if w), 2, ENTRY_CODE)
        self.line(u.meaning, 4, MEANING_CODE)
        if not self.meanings_only:
            for p in r.forms:
                self.form(p, None, None)

    def form(self, p: Parse, entry: Entry | None, result):
        if p.origin == Origin.COMPOUND and p.stem.startswith(
                ('PPL+', 'SUPINE')):
            words = p.stem.replace('PPL+', 'participle + ').replace(
                'SUPINE + ', 'supine + ')
            text = columns(words, describe_form(p.form))
        else:
            description = describe_form(p.form, deponent(entry))
            if entry is not None and p.form.pos not in (
                    entry.part.pos, Pos.VPAR, Pos.SUPINE) and not (
                    entry.part.pos == Pos.PACK and p.form.pos == Pos.PRON):
                # made by a suffix: ludus -> ludic-a, an adjective
                description = ', '.join(
                    x for x in (POS_NAME.get(p.form.pos), description) if x)
            text = columns(stem_and_ending(p.stem, p.infl.ending),
                           description)
        extra = []
        if self.s.show_age or p.infl.age != Age.X:
            extra.append(FORM_AGE.get(p.infl.age))
        if self.s.show_frequency or p.infl.freq >= Freq.C:
            extra.append(FORM_FREQ.get(p.infl.freq))
        extra = [e for e in extra if e]
        if extra:
            text += '  (%s)' % ', '.join(extra)
        self.line(text, 4, FORM_CODE)
        if p.origin == Origin.COMPOUND and result is not None:
            note = result.notes.get(Origin.COMPOUND)
            if note:
                self.line(note, 6, MEANING_CODE)
        if self.s.do_examples:
            gloss = example(p.form, entry)
            if gloss:
                self.line(gloss, 6)

    def neighbour(self, entry: Entry):
        self.line('near: ' + self.entry_header(entry), 2, ENTRY_CODE)
        self.line(entry.meaning, 4, MEANING_CODE)

    # English to Latin ------------------------------------------------------

    def english(self, word: str, hits: list[Hit]) -> str:
        self.line(word)
        if not hits:
            self.line('(no match)', 2)
            return self.text()
        shown = hits
        if self.s.trim_output and len(hits) > 6:
            shown = hits[:6]
        for h in shown:
            header = self.entry_header(h.entry)
            self.line(header, 2, ENTRY_CODE)
            self.line(h.entry.meaning, 4, MEANING_CODE)
        if len(shown) < len(hits):
            self.line('(%d more not shown)' % (len(hits) - len(shown)), 2)
        return self.text()


def columns(left: str, right: str, width: int = 14) -> str:
    if not right:
        return left
    if len(left) < width:
        return left.ljust(width) + ' ' + right
    return left + '  ' + right


def meaning_of(entry: Entry, p: Parse) -> str:
    """The meaning of an entry; for a numeral, what this form means."""
    m = entry.meaning.lstrip('|').strip()
    part = entry.part
    if part.pos != Pos.NUM or part.value <= 0:
        return m
    n = part.value
    if p.form.pos != Pos.NUM:
        return 'Number %d' % n
    return {
        NumeralSort.CARD: "%d - (CARD answers 'how many');" % n,
        NumeralSort.ORD: "%dth - (ORD, 'in series'); (a/the) %dth (part) "
                         "(fract w/pars?);" % (n, n),
        NumeralSort.DIST: "%d each/apiece/times/fold/together/at a time - "
                          "'how many each'; by %ds; " % (n, n),
        NumeralSort.ADVERB: "%d times, on %d occasions - (ADVERB answers "
                            "'how often');" % (n, n),
    }.get(p.form.sort, m)
