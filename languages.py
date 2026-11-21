"""Los idiomas de los significados.

Los significados de los archivos de datos están en inglés.  Cada idioma
tiene un archivo, languages/CODE.xml en la carpeta de datos (véase
words.xsd):

    <language code="es" name="Spanish" native="Español">
      <noise>el la los las ...</noise>          palabras que nunca se buscan
      <common pos="PREP">de a en ...</common>   (véase reverse.py)
      <numeral sort="CARD">{n} - ...</numeral>  el significado de un numeral
      <meaning entry="12">...</meaning>         el significado de la entrada
      <meaning unique="3">...</meaning>         de dictionary.xml con id 12,
      <meaning addon="40">...</meaning>         de una forma irregular, de
      <meaning builtin="esse">...</meaning>     un afijo, de esse
      <meaning entry="13" source="m">...</meaning>  tomado de un diccionario
    </language>

Las entradas del diccionario especial se nombran con special="..." en
lugar de entry="...".  El inglés (en.xml, reference="yes") tiene los
significados de los archivos de datos, salvo los que dan sus <meaning>,
tomados de un diccionario (source="S").  Otro idioma da los significados
que traduce (source="...": el diccionario del que se tomó un significado,
por su código en sources.xml, cuando no se tradujo del inglés); los demás
se muestran en inglés, marcados [en], igual que los numerales que el
archivo no dice.  La búsqueda desde un idioma hacia el latín (~E) busca en
sus significados.

Los <text> traducen lo que dicen los resultados aparte de los
significados: la gramática en palabras (noun, 2nd declension), las
etiquetas y las notas sobre los trucos.  Un texto puede ser un patrón, con
{1}, {2} ... en lugar de sus partes:

    <text en="Word mod {1}/{2}">Modificador de palabra {1}/{2}</text>

Las partes también se traducen, si son textos.  Lo que no se traduce se
muestra en inglés.
"""

from __future__ import annotations

import os
import re
from functools import cached_property

import xmldata
from model import Entry, NumeralSort, Unique
from xmldata import DataError, LanguageData

FOLDER = 'languages'
REFERENCE = 'en'                # el idioma de los archivos de datos
#  Lo que el archivo de un idioma no traduce sale en inglés, con esta marca
ENGLISH_MARK = '[en] '          # before a meaning that is not translated

#  Las entradas que trae el propio programa, por su uid
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
        """THING's meaning in this language, if it has one.  English has
        the meanings of the data files, unless its file gives another,
        taken from a dictionary (source="S": Lewis and Short)."""
        text = self.data.meanings.get(key(thing))
        if self.is_reference:
            return thing.meaning if text is None else text
        return text

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
