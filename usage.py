"""El uso de las palabras: las lecturas de una palabra, de la más usual a
la menos, según los textos latinos lematizados por el LASLA (Université
de Liège) que contó Collatinus (data/frequencies.xml).

Como en Collatinus, una lectura vale lo que aparece su entrada, por la
parte que su clase de forma (su etiqueta: n31, el acusativo singular de un
sustantivo) tiene entre las de su categoría.  Las formas de una entrada
suman las de sus etiquetas distintas.  Una entrada que el LASLA no cuenta
vale la mediana de las entradas contadas de su frecuencia (los códigos A a
F del diccionario).  Las formas irregulares de uniques.xml van primero,
como antes.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median

from model import Pos, Case, Mood, Tense, Freq, Form, Entry
from results import Parse

#  La letra de Collatinus de cada categoría (véase NOTES_Tagger.md de
#  Collatinus)
POS_LETTER = {Pos.N: 'n', Pos.ADJ: 'a', Pos.PRON: 'p', Pos.PACK: 'p',
              Pos.NUM: 'm', Pos.VPAR: 'w', Pos.V: 'v', Pos.SUPINE: 'v',
              Pos.ADV: 'd', Pos.PREP: 'r', Pos.CONJ: 'c',
              Pos.INTERJ: 'i'}
#  The cases in the French order that Collatinus uses (7, the locative)
CASE_DIGIT = {Case.NOM: '1', Case.VOC: '2', Case.ACC: '3', Case.GEN: '4',
              Case.DAT: '5', Case.ABL: '6', Case.LOC: '7'}
MOOD_DIGIT = {Mood.IND: '1', Mood.SUB: '2', Mood.IMP: '3', Mood.INF: '4'}
#  Las categorías que se declinan o conjugan (las demás valen entera su
#  entrada)
INFLECTED = 'napmwv'
#  The weights of Collatinus (LemCore::fraction): its tags have no
#  gender, person or voice, so a form of an adjective, pronoun or
#  participle is one of three genders, and a verb's of several persons
WEIGHT = {'a': 1 / 3, 'p': 1 / 3, 'w': 1 / 3, 'n': 1.0, 'm': 1.0}
PRESENT_WEIGHT, OTHER_TENSE_WEIGHT = 1 / 2, 1 / 4


def tag(form: Form) -> str | None:
    """The tag of Collatinus for FORM (n31, v11, d  ...), or None."""
    letter = POS_LETTER.get(form.pos)
    if letter is None:
        return None
    if form.pos == Pos.SUPINE:
        return 'v3 '        # (Collatinus junta los supinos con v3)
    if form.pos == Pos.V:
        mood = MOOD_DIGIT.get(form.mood)
        if mood is None:
            return None
        return 'v' + mood + ('1' if form.tense == Tense.PRES else ' ')
    if letter in 'napmw' and form.case in CASE_DIGIT:
        return letter + CASE_DIGIT[form.case] + \
            ('2' if form.number.name == 'P' else '1')
    return letter + '  '


class Usage:
    """How usual each reading of a word is, from the counts of a
    lexicon."""

    def __init__(self, uses: dict[int, int], tag_counts: dict[str, int],
                 entries: list[Entry]):
        self.uses = uses
        self.tags = tag_counts
        self.totals: dict[str, int] = defaultdict(int)
        for t, n in tag_counts.items():
            self.totals[t[0]] += n
        by_freq = defaultdict(list)
        for e in entries:
            n = uses.get(e.uid)
            if n:
                by_freq[e.codes.freq or Freq.D].append(n)
        #  lo que vale una entrada sin recuento, por su frecuencia
        self.usual = {f: median(ns) for f, ns in by_freq.items()}

    def __bool__(self) -> bool:
        return bool(self.uses)

    def share(self, t: str) -> float:
        """The part of tag T among those of its part of speech (1 for the
        words that are not inflected)."""
        if t[0] not in INFLECTED or t[1] == ' ':
            return 1.0
        total = self.totals.get(t[0])
        if not total:
            return 1.0
        if t[0] == 'v':
            weight = PRESENT_WEIGHT if t[2] == '1' else OTHER_TENSE_WEIGHT
        else:
            weight = WEIGHT.get(t[0], 1.0)
        return weight * max(self.tags.get(t, 0), 1) / total

    def entry_uses(self, e: Entry) -> float:
        n = self.uses.get(e.uid) if e.dictionary == 'general' else None
        if n:
            return n
        return self.usual.get(e.codes.freq or Freq.D, 1)

    def scores(self, parses: tuple[Parse, ...]) -> dict[int, float]:
        """{entry id: how usual its forms among PARSES are}."""
        tags: dict[int, set] = defaultdict(set)
        entries = {}
        for p in parses:
            e = p.entry
            if e is None:
                continue
            entries[p.id] = e
            t = tag(p.form)
            if t is not None:
                tags[p.id].add(t)
        return {i: self.entry_uses(e) *
                (sum(self.share(t) for t in tags[i]) if tags[i] else 1.0)
                for i, e in entries.items()}
