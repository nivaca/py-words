"""Words about words: the principal parts of an entry (amicus, amici), its
grammar in plain English (noun, 2nd declension, masculine), the grammar of
a form (genitive singular), and English example glosses.
"""

from __future__ import annotations

from model import (Pos, Gender, Case, Number, Comparison, NumeralSort,
                    Tense, Voice, Mood, VerbKind, PronounKind, Decl, Part,
                    Form, Entry)

ORDINAL = {1: '1st', 2: '2nd', 3: '3rd', 4: '4th', 5: '5th'}

POS_NAME = {Pos.N: 'noun', Pos.PRON: 'pronoun', Pos.PACK: 'pronoun',
            Pos.ADJ: 'adjective', Pos.NUM: 'numeral', Pos.ADV: 'adverb',
            Pos.V: 'verb', Pos.VPAR: 'participle', Pos.SUPINE: 'supine',
            Pos.PREP: 'preposition', Pos.CONJ: 'conjunction',
            Pos.INTERJ: 'interjection', Pos.TACKON: 'enclitic',
            Pos.PREFIX: 'prefix', Pos.SUFFIX: 'suffix'}
CASE_NAME = {Case.NOM: 'nominative', Case.VOC: 'vocative',
             Case.GEN: 'genitive', Case.LOC: 'locative', Case.DAT: 'dative',
             Case.ABL: 'ablative', Case.ACC: 'accusative'}
NUMBER_NAME = {Number.S: 'singular', Number.P: 'plural'}
GENDER_NAME = {Gender.M: 'masculine', Gender.F: 'feminine',
               Gender.N: 'neuter', Gender.C: 'masculine/feminine'}
COMPARISON_NAME = {Comparison.POS: 'positive', Comparison.COMP: 'comparative',
                   Comparison.SUPER: 'superlative'}
SORT_NAME = {NumeralSort.CARD: 'cardinal', NumeralSort.ORD: 'ordinal',
             NumeralSort.DIST: 'distributive',
             NumeralSort.ADVERB: 'numeral adverb'}
TENSE_NAME = {Tense.PRES: 'present', Tense.IMPF: 'imperfect',
              Tense.FUT: 'future', Tense.PERF: 'perfect',
              Tense.PLUP: 'pluperfect', Tense.FUTP: 'future perfect'}
VOICE_NAME = {Voice.ACTIVE: 'active', Voice.PASSIVE: 'passive'}
MOOD_NAME = {Mood.IND: 'indicative', Mood.SUB: 'subjunctive',
             Mood.IMP: 'imperative', Mood.INF: 'infinitive',
             Mood.PPL: 'participle'}
VERB_KIND_NAME = {VerbKind.TO_BE: 'the verb "to be"',
                  VerbKind.TO_BEING: 'compound of "to be"',
                  VerbKind.GEN: 'takes the genitive',
                  VerbKind.DAT: 'takes the dative',
                  VerbKind.ABL: 'takes the ablative',
                  VerbKind.TRANS: 'transitive',
                  VerbKind.INTRANS: 'intransitive',
                  VerbKind.IMPERS: 'impersonal', VerbKind.DEP: 'deponent',
                  VerbKind.SEMIDEP: 'semi-deponent',
                  VerbKind.PERFDEF: 'perfect with present meaning'}
PRONOUN_KIND_NAME = {PronounKind.PERS: 'personal', PronounKind.REL: 'relative',
                     PronounKind.REFLEX: 'reflexive',
                     PronounKind.DEMONS: 'demonstrative',
                     PronounKind.INTERR: 'interrogative',
                     PronounKind.INDEF: 'indefinite',
                     PronounKind.ADJECT: 'adjectival'}


# ---------------------------------------------------------------------------
#  Principal parts

#  Each part is (stem number, ending): stem None means just the ending.
NOUN_PARTS = {
    (1, 1): ((0, 'a'), (1, 'ae')), (1, 6): ((0, 'e'), (1, 'es')),
    (1, 7): ((0, 'es'), (1, 'ae')), (1, 8): ((0, 'as'), (1, 'ae')),
    (2, 1): ((0, 'us'), (1, 'i')), (2, 2): ((0, 'um'), (1, 'i')),
    (2, 3): ((0, ''), (1, 'i')), (2, 5): ((0, 'us'), (1, '')),
    (2, 6): ((0, 'os'), (1, 'i')), (2, 7): ((0, ''), (1, 'yos/i')),
    (2, 8): ((0, 'on'), (1, 'i')), (2, 9): ((0, 'us'), (1, 'i')),
    (4, 1): ((0, 'us'), (1, 'us')), (4, 2): ((0, 'u'), (1, 'us')),
    (4, 3): ((0, 'us'), (1, 'u')), (4, 4): ((0, ''), (1, 'u')),
    (9, 8): ((0, '.'), (None, 'abb.')),
    (9, 9): ((0, ''), (None, 'undeclined')),
}

PRONOUN_PARTS = {
    (3, 1): ((0, 'ic'), (0, 'aec'), (0, 'oc')),
    (3, 2): ((0, 'ic'), (0, 'aec'), (0, 'uc')),
    (4, 1): ((0, 's'), (1, 'a'), (0, 'd')),
    (4, 2): ((0, 'dem'), (1, 'adem'), (0, 'dem')),
    (6, 1): ((0, 'e'), (0, 'a'), (0, 'ud')),
    (6, 2): ((0, 'e'), (0, 'a'), (0, 'um')),
    (9, 8): ((0, '.'), (None, 'abb.')),
    (9, 9): ((0, ''), (None, 'undeclined')),
}

ADJ_PARTS = {
    (1, 1): ((0, 'us'), (1, 'a'), (1, 'um')),
    (1, 2): ((0, ''), (1, 'a'), (1, 'um')),
    (1, 3): ((0, 'us'), (1, 'a'), (1, 'um (gen -ius)')),
    (1, 4): ((0, ''), (1, 'a'), (1, 'um')),
    (1, 5): ((0, 'us'), (1, 'a'), (1, 'ud')),
    (2, 1): ((None, '-'), (0, 'e'), (None, '-')),
    (2, 2): ((None, '-'), (None, 'a'), (None, '-')),
    (2, 3): ((0, 'es'), (0, 'es'), (0, 'es')),
    (2, 6): ((0, 'os'), (0, 'os'), (None, '-')),
    (2, 7): ((0, 'os'), (None, '-'), (None, '-')),
    (2, 8): ((None, '-'), (None, '-'), (1, 'on')),
    (3, 1): ((0, ''), (None, '(gen.)'), (1, 'is')),
    (3, 2): ((0, 'is'), (1, 'is'), (1, 'e')),
    (3, 3): ((0, ''), (1, 'is'), (1, 'e')),
    (3, 6): ((0, ''), (None, '(gen.)'), (1, 'os')),
    (9, 8): ((0, '.'), (None, 'abb.')),
    (9, 9): ((0, ''), (None, 'undeclined')),
}

ADJ_COMPARED = (2, 'or -or -us'), (3, 'mus -a -um')
ADJ_ALL_DEGREES = {
    (1, 1): ((0, 'us'), (1, 'a -um')),
    (1, 2): ((0, ''), (1, 'a -um')),
    (3, 1): ((0, ''), (1, 'is (gen.)')),
    (3, 2): ((0, 'is'), (1, 'e')),
    (3, 3): ((0, ''), (1, 'is -e')),
}

NUMERAL_PARTS = {
    (1, 1): ((0, 'us -a -um'), (1, 'us -a -um'), (2, 'i -ae -a'), (3, '')),
    (1, 2): ((0, 'o -ae o'), (1, 'us -a -um'), (2, 'i -ae -a'), (3, '')),
    (1, 3): ((0, 'es -es -ia'), (1, 'us -a -um'), (2, 'i -ae -a'), (3, '')),
    (1, 4): ((0, 'i -ae -a'), (1, 'us -a -um'), (2, 'i -ae -a'),
             (3, 'ie (n)s')),
    (2, 0): ((0, ''), (1, 'us -a -um'), (2, 'i -ae -a'), (3, 'ie (n)s')),
}
CARDINAL_PARTS = {
    (1, 1): ('us', 'a', 'um'), (1, 2): ('o', 'ae', 'o'),
    (1, 3): ('es', 'es', 'ia'), (1, 4): ('i', 'ae', 'a'),
}

DEPONENT_PRESENT = {1: ('or', 'ari'), 2: ('eor', 'eri')}
INFINITIVE = {1: 'are', 2: 'ere', (3, 2): 're', (3, 4): 'ire', 3: 'ere',
              (5, 1): 'esse', (6, 1): 're', (6, 2): 'le', (7, 3): 'se',
              (8, 1): 'are', (8, 2): 'ere', (8, 3): 'ere', (8, 4): 'ire',
              8: 'ere'}


def _make(stems, parts) -> list[str]:
    out = []
    for stem, ending in parts:
        if stem is None:
            out.append(ending)
        elif stems[stem] == 'zzz':
            out.append('-')
        else:
            out.append(stems[stem] + ending)
    return out


def _verb_parts(stems, part: Part) -> list[str]:
    which, var = part.decl
    kind = part.kind
    st = stems
    if kind == VerbKind.DEP:
        if which in DEPONENT_PRESENT:
            pres, inf = DEPONENT_PRESENT[which]
        elif which == 3:
            pres, inf = 'or', 'iri' if var == 4 else 'i'
        else:
            return []
        return _make(st, ((0, pres), (1, inf), (3, 'us sum')))
    if kind == VerbKind.PERFDEF:
        return _make(st, ((2, 'i'), (2, 'isse'), (3, 'us')))
    if kind == VerbKind.IMPERS and st[0] == 'zzz' and st[1] == 'zzz':
        return _make(st, ((2, 'it'), (2, 'isse'), (3, 'us est')))
    if (which, var) == (9, 8):
        return _make(st, ((0, '.'), (None, 'abb.')))
    if (which, var) == (9, 9):
        return _make(st, ((0, ''), (None, 'undeclined')))
    # First principal part
    if kind == VerbKind.IMPERS:
        if which == 3 and var != 2:
            first = 't' if st[0].endswith('i') else 'it'
        else:
            first = {1: 'at', 2: 'et', 3: 't', 5: 'est', 7: 't'}.get(which)
    else:
        first = {2: 'eo', 5: 'um'}.get(which, 'o')
        if (which, var) == (7, 2):
            first = 'am'
    parts = [(0, first)] if first is not None else []
    # Infinitive
    if (which, var) == (3, 3):
        parts.append((1, 'ieri' if st[1] == 'f' else 'eri'))
    elif (which, var) == (5, 2):
        parts.append((0, 'e'))
    elif (which, var) in INFINITIVE:
        parts.append((1, INFINITIVE[which, var]))
    elif which in INFINITIVE and which not in (5, 6, 7):
        parts.append((1, INFINITIVE[which]))
    # Perfect and participle
    if kind == VerbKind.IMPERS:
        parts += [(2, 'it'), (3, 'us est')]
    elif kind == VerbKind.SEMIDEP:
        parts.append((3, 'us sum'))
    elif (which, var) == (5, 1):
        parts += [(2, 'i'), (3, 'urus')]
    elif which == 8:
        parts += [(None, 'additional'), (None, 'forms')]
    else:
        parts += [(2, 'i'), (3, 'us')]
    out = _make(st, parts)
    if (which, var) == (6, 1) and len(out) >= 3:
        out[2] += '(ii)'
    return out


def principal_parts(entry: Entry) -> str:
    """The dictionary form of ENTRY: "amicus, amici", "amo, amare, amavi,
    amatus" ... ('' for the most irregular pronouns)."""
    st = entry.stems
    p = entry.part
    which, var = p.decl
    if p.pos == Pos.PREP:
        return st[0]
    special = (p.pos == Pos.N and which == 9) or \
        (p.pos == Pos.ADJ and (which == 9 or p.comparison in (
            Comparison.COMP, Comparison.SUPER))) or \
        (p.pos == Pos.V and p.decl in ((9, 8), (9, 9))) or \
        (p.pos == Pos.NUM and p.sort != NumeralSort.X)  # (one stem)
    if st[1:] == ('', '', '') and not special:
        return st[0]
    parts: list[str] = []
    if p.pos == Pos.N:
        if (which, var) == (2, 4):
            ending = 'um' if p.gender == Gender.N else 'us'
            parts = _make(st, ((0, ending), (1, '(i)')))
        elif which == 3:
            parts = _make(st, ((0, ''), (1, 'os/is' if var in (7, 9)
                                         else 'is')))
        elif which == 5:
            parts = _make(st, ((0, 'es'), (1, 'ei')))
        elif (which, var) in NOUN_PARTS:
            parts = _make(st, NOUN_PARTS[which, var])
    elif p.pos == Pos.PRON:
        if (which, var) not in PRONOUN_PARTS:
            return ''           # qui, ego ...: too irregular for a summary
        parts = _make(st, PRONOUN_PARTS[which, var])
    elif p.pos == Pos.ADJ:
        if p.comparison == Comparison.COMP:
            parts = _make(st, ((0, 'or'), (0, 'or'), (0, 'us')))
        elif p.comparison == Comparison.SUPER:
            parts = _make(st, ((0, 'mus'), (0, 'ma'), (0, 'mum')))
        elif p.comparison == Comparison.POS:
            parts = _make(st, ADJ_PARTS.get((which, var), ()))
        elif which == 9:
            parts = _make(st, ((0, ''), (None, 'undeclined')) +
                          ADJ_COMPARED)
        elif (which, var) in ADJ_ALL_DEGREES:
            parts = _make(st, ADJ_ALL_DEGREES[which, var] + ADJ_COMPARED)
    elif p.pos == Pos.ADV and p.comparison == Comparison.X:
        parts = _make(st, ((0, ''), (1, ''), (2, '')))
    elif p.pos == Pos.V:
        parts = _verb_parts(st, p)
    elif p.pos == Pos.NUM:
        match p.sort:
            case NumeralSort.X:
                key = (which, var) if which == 1 else (2, 0)
                parts = _make(st, NUMERAL_PARTS.get(key, ()))
            case NumeralSort.CARD:
                if which == 2:
                    parts = [st[0]]
                elif (which, var) in CARDINAL_PARTS:
                    parts = [st[0] + e for e in CARDINAL_PARTS[which, var]]
            case NumeralSort.ORD:
                parts = _make(st, ((0, 'us'), (0, 'a'), (0, 'um')))
            case NumeralSort.DIST:
                parts = _make(st, ((0, 'i'), (0, 'ae'), (0, 'a')))
            case _:
                parts = [st[0]]
    else:
        parts = [st[0]]
    return ', '.join(x for x in parts if x) or st[0]


# ---------------------------------------------------------------------------
#  Grammar in words

def _declension(decl: Decl, conjugation=False) -> str | None:
    which, var = decl
    if which == 9:
        return {8: 'abbreviation', 9: 'undeclined'}.get(var)
    if conjugation:
        if (which, var) == (3, 4):
            return '4th conjugation'
        if which in (1, 2, 3, 4):
            return ORDINAL[which] + ' conjugation'
        return 'irregular'
    if which in ORDINAL:
        return ORDINAL[which] + ' declension'
    return None


def describe_part(part: Part) -> str:
    """The grammar of a dictionary entry: "noun, 2nd declension,
    masculine"."""
    p = part.pos
    words = [POS_NAME.get(p, p.name)]
    match p:
        case Pos.N:
            words += [_declension(part.decl), GENDER_NAME.get(part.gender)]
        case Pos.PRON | Pos.PACK:
            words += [PRONOUN_KIND_NAME.get(part.kind)]
        case Pos.ADJ:
            d = _declension(part.decl)
            if part.decl.which == 1:
                d = '1st/2nd declension'
            words += [d, COMPARISON_NAME.get(part.comparison)
                      if part.comparison != Comparison.POS else None]
        case Pos.NUM:
            words += [SORT_NAME.get(part.sort),
                      str(part.value) if part.value else None]
        case Pos.ADV:
            words += [COMPARISON_NAME.get(part.comparison)
                      if part.comparison != Comparison.POS else None]
        case Pos.V:
            words += [_declension(part.decl, conjugation=True),
                      VERB_KIND_NAME.get(part.kind)]
        case Pos.PREP:
            words += ['with the ' + CASE_NAME[part.case]
                      if part.case in CASE_NAME else None]
    return ', '.join(w for w in words if w)


def describe_form(form: Form, deponent: bool = False) -> str:
    """The grammar of an inflected form: "genitive singular", "3rd person
    singular perfect active indicative" ...  The voice of a deponent verb
    is not shown, as it is active in meaning."""
    p = form.pos
    voice = None if deponent else VOICE_NAME.get(form.voice)
    words: list[str | None] = []
    match p:
        case Pos.N | Pos.PRON | Pos.PACK | Pos.ADJ | Pos.NUM:
            words = [CASE_NAME.get(form.case), NUMBER_NAME.get(form.number),
                     GENDER_NAME.get(form.gender) if p != Pos.N else None]
            if p == Pos.ADJ and form.comparison not in (Comparison.POS,
                                                         Comparison.X):
                words.append(COMPARISON_NAME[form.comparison])
            if p == Pos.NUM:
                words.append(SORT_NAME.get(form.sort))
        case Pos.ADV:
            words = [COMPARISON_NAME.get(form.comparison)]
        case Pos.V if form.mood == Mood.INF:
            words = [TENSE_NAME.get(form.tense), voice, 'infinitive']
        case Pos.V:
            person = f'{ORDINAL[form.person]} person' \
                if form.person in (1, 2, 3) else None
            words = [person, NUMBER_NAME.get(form.number),
                     TENSE_NAME.get(form.tense), voice,
                     MOOD_NAME.get(form.mood)]
        case Pos.VPAR:
            words = [TENSE_NAME.get(form.tense), voice, 'participle,',
                     CASE_NAME.get(form.case), NUMBER_NAME.get(form.number),
                     GENDER_NAME.get(form.gender)]
        case Pos.SUPINE:
            words = ['supine,', CASE_NAME.get(form.case)]
        case Pos.PREP:
            words = ['with the ' + CASE_NAME[form.case]
                     if form.case in CASE_NAME else None]
    text = ' '.join(w for w in words if w)
    return text.rstrip(',')


# ---------------------------------------------------------------------------
#  Example glosses (the do_examples parameter)

def example(form: Form, entry: Entry | None) -> str | None:
    """How a form is put into English, with ~ for the word: "~'s; of ~"."""
    p = form.pos
    if p == Pos.N:
        return {Case.GEN: "~'s; of ~",
                Case.ABL: 'from _ (separ); because of ~ (cause); than ~ '
                          '(compar); of ~ (circumstance)',
                Case.DAT: 'for _ (purpose, reference); to ~ (w/adjectives); '
                          'to ~ (double dative)',
                Case.LOC: 'at ~ (place where)'}.get(form.case)
    if p == Pos.ADJ:
        return {Comparison.COMP: '~er; more/too _',
                Comparison.SUPER: '~est; most/very'}.get(form.comparison)
    if p == Pos.ADV:
        return {Comparison.COMP: 'more/too ~(ly)',
                Comparison.SUPER: 'most/very ~(ly)'}.get(form.comparison)
    if p == Pos.V:
        kind = entry.part.kind if entry is not None and \
            entry.part.pos == Pos.V else None
        return _verb_example(form, kind)
    if p == Pos.VPAR:
        if form.tense == Tense.PERF:
            return '~ed  PERF PASSIVE PPL often used as ADJ or N ' \
                '(amatus => belov.ed)'
        if form.tense == Tense.PRES:
            return '~ing  PRES ACTIVE PPL often used as ADJ or N ' \
                '(lov.ing, curl.y)'
        if form.tense == Tense.FUT:
            if form.voice == Voice.ACTIVE:
                return 'about/going/intending/destined to ~  FUT ACTIVE PPL ' \
                    'often used as ADJ or N'
            how = {Case.GEN: 'of ~ing', Case.DAT: 'to/for ~ing',
                   Case.ABL: 'by/in ~ing',
                   Case.ACC: 'for ~ing/to ~'}.get(form.case, '~ing')
            return 'to (/must) be ~ed  FUT PASSIVE PPL, often used as ' \
                f'gerund or gerundive ({how})'
    if p == Pos.SUPINE:
        return {Case.ACC: 'to ~  expresses purpose of verb of motion; may '
                          'take a direct object',
                Case.ABL: 'to ~  after ADJ indicating aspect/respect in '
                          'which something is/is done'}.get(form.case)
    return None


def _verb_example(f: Form, kind) -> str:
    person, number, tense, mood = f.person, f.number, f.tense, f.mood
    voice = f.voice
    if kind == VerbKind.DEP or (kind == VerbKind.SEMIDEP and
                                Tense.PERF <= tense <= Tense.FUTP):
        voice = Voice.ACTIVE
    singular = number == Number.S

    if kind == VerbKind.IMPERS:
        they = 'it '
    elif mood == Mood.INF:
        they = 'to '
    elif mood == Mood.IMP and tense == Tense.PRES and number == Number.P:
        they = '(you) '
    elif mood == Mood.SUB and tense == Tense.PRES and person == 1 and \
            number == Number.P:
        they = 'let us '
    elif number in (Number.S, Number.P):
        they = {1: ('I ', 'we '), 2: ('you ', 'you '),
                3: ('he/it ', 'they ')}.get(person, ('', ''))[
                    0 if singular else 1]
    else:
        they = ''
    #  (the subjunctive "let us" needs no "may/must/should")
    sub = 'may/must/should ' if mood == Mood.SUB and they != 'let us ' \
        else ''
    shall = ''
    if tense in (Tense.FUT, Tense.FUTP):
        if mood in (Mood.IND, Mood.SUB):
            shall = {1: 'shall ', 2: 'will ', 3: 'will '}.get(person, '')
        elif mood == Mood.IMP:
            shall = {1: 'will ', 2: '(shall) ', 3: '(shall) '}.get(person, '')
        elif mood == Mood.INF and tense == Tense.FUT:
            shall = 'be about to be '
    have = ''
    if tense == Tense.PERF:
        have = 'has ' if person == 3 and singular else 'have '
    elif tense == Tense.PLUP:
        have = {Mood.IND: 'had ', Mood.SUB: 'have '}.get(mood, '')
    elif tense == Tense.FUTP:
        have = 'have '
    been = ''
    if voice == Voice.PASSIVE:
        if mood == Mood.IND:
            if tense == Tense.PRES:
                been = 'am/am being ' if person == 1 and singular else \
                    'is/is being ' if person == 3 and singular else \
                    'are/are being '
            elif tense == Tense.IMPF:
                been = 'was/was being ' if person in (1, 3) and singular \
                    else 'were/were being '
            elif tense == Tense.FUT:
                been = 'be '
            elif tense == Tense.PERF:
                been = 'been/was ' if person in (1, 3) and singular \
                    else 'been/were '
            elif tense in (Tense.PLUP, Tense.FUTP):
                been = 'been '
        elif mood == Mood.INF:
            been = {Tense.PRES: 'be ', Tense.PERF: 'been '}.get(tense, '')
        elif mood == Mood.IMP:
            been = 'be '
        elif mood == Mood.SUB:
            been = 'been ' if tense in (Tense.PERF, Tense.PLUP) else 'be '
    ed = ''
    if mood == Mood.IMP:
        ed = {Voice.ACTIVE: '!', Voice.PASSIVE: 'ed!'}.get(voice, '')
    elif mood == Mood.INF:
        ed = 'ed' if voice == Voice.PASSIVE else ''
    elif mood == Mood.IND:
        if voice == Voice.ACTIVE:
            if tense == Tense.PRES:
                ed = 's' if person == 3 and singular else ''
            elif tense == Tense.IMPF:
                ed = 'ed/was ~ing' if person in (1, 3) and singular \
                    else 'ed/were ~ing'
            elif tense in (Tense.PERF, Tense.PLUP, Tense.FUTP):
                ed = 'ed'
        elif voice == Voice.PASSIVE:
            ed = 'ed'
    elif mood == Mood.SUB and (voice == Voice.PASSIVE or
                               tense in (Tense.PERF, Tense.PLUP)):
        ed = 'ed'
    return they + sub + shall + have + been + '~' + ed


def deponent(entry: Entry | None) -> bool:
    return entry is not None and entry.part.pos == Pos.V and \
        entry.part.kind == VerbKind.DEP


def stem_and_ending(stem: str, ending: str) -> str:
    return stem + '-' + ending if ending else stem

