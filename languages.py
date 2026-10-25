"""The languages of the meanings.

The meanings in the data files are in English.  Each language has a file,
languages/CODE.xml in the data folder (see words.xsd):

    <language code="es" name="Spanish" native="Español">
      <noise>el la los las ...</noise>          words never looked for
      <common pos="PREP">de a en ...</common>   (see reverse.py)
      <numeral sort="CARD">{n} - ...</numeral>  what a numeral's form means
      <meaning entry="12">...</meaning>         the meaning of the entry
      <meaning unique="3">...</meaning>         of dictionary.xml with id
      <meaning addon="40">...</meaning>         12, of an irregular form,
      <meaning builtin="esse">...</meaning>     of an affix, of esse
      <meaning entry="13" source="m">...</meaning>  taken from a dictionary
    </language>

English (en.xml, reference="yes") has no <meaning>s: its meanings are
those of the data files.  Another language gives the meanings it
translates (source="...": the dictionary a meaning was taken from, by its
code in sources.xml, when it was not translated from the English); the
others are shown in English, marked [en], as are the
numerals it does not say.  The search from a language to Latin (~E) looks
in its meanings.

The <text>s translate what the results say besides the meanings: the
grammar in words (noun, 2nd declension), the labels and the notes on
tricks.  A text may be a pattern, with {1}, {2} ... for its parts:

    <text en="Word mod {1}/{2}">Modificador de palabra {1}/{2}</text>

The parts are translated too, if they are texts.  What is not translated
is shown in English.
"""

from __future__ import annotations

import os
import re
from functools import cached_property

import xmldata
from model import Entry, NumeralSort, Unique
from xmldata import DataError, LanguageData

FOLDER = 'languages'
REFERENCE = 'en'                # the language of the data files
#  Lo que el archivo de un idioma no traduce sale en inglés, con esta marca
ENGLISH_MARK = '[en] '          # before a meaning that is not translated

#  The entries built into the program, by their uid
BUILTIN = {-1: 'esse'}

HERE = os.path.dirname(os.path.abspath(__file__))
OWN_FOLDER = os.path.join(HERE, 'data', FOLDER)


def key(thing) -> tuple[str, int | str]:
    """What a language file calls THING (an entry, irregular form or
    affix): ('entry', its uid), ('unique', ...), ('builtin', 'esse') ..."""
    if isinstance(thing, Entry):
        if thing.uid in BUILTIN:
            return 'builtin', BUILTIN[thing.uid]
        return ('special' if thing.dictionary == 'special' else 'entry',
                thing.uid)
    if isinstance(thing, Unique):
        return 'unique', thing.uid
    return 'addon', thing.uid


def files(datadir: str) -> dict[str, str]:
    """The language files: {code: path}, by the names of the files.  The
    program's own English file stands in if the data folder has none."""
    folder = os.path.join(datadir, FOLDER)
    try:
        names = os.listdir(folder)
    except OSError:
        names = []
    found = {os.path.splitext(name)[0]: os.path.join(folder, name)
             for name in names if name.endswith('.xml')}
    if REFERENCE not in found:
        found[REFERENCE] = os.path.join(OWN_FOLDER, REFERENCE + '.xml')
    return dict(sorted(found.items()))


def names(datadir: str) -> dict[str, str]:
    """{code: name} of the languages (read from the start of each file)."""
    out = {}
    for code, path in files(datadir).items():
        try:
            _, attrs = xmldata.root_element(path)
        except (OSError, DataError):
            continue
        out[code] = attrs.get('name') or code
    return out


class Language:
    """A language of the meanings."""

    def __init__(self, data: LanguageData, reference: Language | None = None,
                 sources: dict[str, str] | None = None):
        """REFERENCE: English, for what this language does not say (None
        for English itself).  SOURCES: {source code: name}, to say which
        dictionary a meaning was taken from."""
        self.data = data
        self.reference = reference
        self.sources = sources or {}

    def __repr__(self):
        return f'<Language {self.code}>'

    @property
    def code(self) -> str:
        return self.data.code

    @property
    def name(self) -> str:
        return self.data.name

    @property
    def is_reference(self) -> bool:
        return self.data.reference

    def translated(self, thing) -> str | None:
        """THING's meaning in this language, if it has one."""
        if self.is_reference:
            return thing.meaning
        return self.data.meanings.get(key(thing))

    def meaning(self, thing) -> str:
        """THING's meaning in this language, or in English (marked); a
        meaning taken from a dictionary says which, "(De Miguel)"."""
        text = self.translated(thing)
        if text is None:
            return ENGLISH_MARK + thing.meaning.lstrip('|').strip()
        source = self.data.sources.get(key(thing))
        if source is None or source.name not in self.sources:
            return text
        name = self.sources[source.name].split(',')[0].strip()
        return f'{text} ({name})'

    def text(self, english: str) -> str:
        """ENGLISH, a text of the results, in this language (as it is if
        it is not translated)."""
        texts = self.data.texts
        if not texts:
            return english
        key = ' '.join(english.split())
        found = texts.get(key)
        if found is not None:
            return found
        for pattern, translation in self._patterns:
            m = pattern.fullmatch(key)
            if m:
                return re.sub(r'\{(\d)\}',
                              lambda n: self.text(m.group('p' + n[1])),
                              translation)
        return english

    @cached_property
    def _patterns(self) -> list[tuple[re.Pattern, str]]:
        """The texts with parts ({1} ...), as patterns: the most
        specific (the most fixed text) first."""
        out = []
        for english, translation in self.data.texts.items():
            pieces = re.split(r'\{(\d)\}', english)
            if len(pieces) == 1:
                continue
            regex = ''.join(re.escape(x) if i % 2 == 0 else f'(?P<p{x}>.*?)'
                            for i, x in enumerate(pieces))
            fixed = sum(len(x) for x in pieces[::2])
            out.append((fixed, re.compile(regex), translation))
        out.sort(key=lambda x: -x[0])
        return [(p, t) for _, p, t in out]

    def numeral(self, sort: NumeralSort, n: int) -> str | None:
        """What a form of the numeral N of SORT means (sort X: a form that
        is not a numeral)."""
        text = self.data.numerals.get(sort)
        if text is None:
            if self.reference is None:
                return None
            text = self.reference.numeral(sort, n)
            return None if text is None else ENGLISH_MARK + text
        return text.replace('{n}', str(n))


def read(path: str, reference: Language | None = None) -> Language:
    """The language file PATH (raises DataError)."""
    data = xmldata.read_language(path)
    if data.reference:
        reference = None
    elif reference is None:
        raise DataError(path, 1, 'English is needed for what this '
                        'language does not say')
    return Language(data, reference)
