"""Reading and writing the data files.

    dictionary.xml   <dictionary> of <entry>
    inflections.xml  <inflections> of <inflection>
    uniques.xml      <uniques> of <unique>
    addons.xml       <addons> of <prefix>, <suffix> and <tackon>
    sources.xml      <sources> of <source>: the names of the source codes
    gloss.xml        <glosses> of <gloss>: the abbreviations of the analyses
    languages/*.xml  <language>: a language of the meanings (see
                     languages.py)

words.xsd describes them.  The entries, irregular forms and affixes have
an id attribute, a number that stays the same when others are added or
moved, which the translations of their meanings refer to (if it is
missing, their position in the file is used).  Grammatical codes are
written as in the original WORDS files (N, V, NOM, PRES, ...),
declensions and conjugations as two digits ("2 1").  The order of the
elements matters.

The readers return (record, line number) pairs in file order and check the
files as they go.  A problem raises DataError, or, if the caller passes a
list as ERRORS, is appended to it and the element skipped.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterator
from typing import NamedTuple
from xml.parsers import expat
from xml.sax.saxutils import escape, quoteattr, unescape

from interface import tr

from model import (
    Pos, Gender, Case, Number, Comparison, NumeralSort, Tense, Voice, Mood,
    NounKind, PronounKind, VerbKind, Age, Freq, Area, Geo, Source, Decl,
    Codes, Part, Form, Inflection, Entry, Unique, Prefix, Suffix, Tackon,
    unmarked)

SCHEMA = 'words.xsd'
MAX_STEM = 18                   # letters in a stem, form or affix
MAX_ENDING = 7

MAX_UID = 10 ** 9

LETTERS = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')


class DataError(Exception):
    """A problem in a data file, with its location (the message is in the
    language of the interface).  A problem with an attribute also says
    which (FIELD), its VALUE and the PROBLEM (None if it is missing), for
    the editors."""

    def __init__(self, path, line, message, field=None, value=None,
                 problem=None):
        super().__init__(f'{path}:{line}: {message}')
        self.path = path
        self.line = line
        self.message = message
        self.field = field
        self.value = value
        self.problem = problem


# ---------------------------------------------------------------------------
#  Which attributes each part of speech uses

#  Of an entry, and of the <target>/<base> of suffixes and tackons
PART_ATTRS = {
    Pos.N: ('decl', 'gender', 'kind'),
    Pos.PRON: ('decl', 'kind'),
    Pos.PACK: ('decl', 'kind'),
    Pos.ADJ: ('decl', 'comparison'),
    Pos.NUM: ('decl', 'sort', 'value'),
    Pos.ADV: ('comparison',),
    Pos.V: ('conj', 'kind'),
    Pos.PREP: ('case',),
}

#  Of an inflection or a unique form
FORM_ATTRS = {
    Pos.N: ('decl', 'case', 'number', 'gender'),
    Pos.PRON: ('decl', 'case', 'number', 'gender'),
    Pos.PACK: ('decl', 'case', 'number', 'gender'),
    Pos.ADJ: ('decl', 'case', 'number', 'gender', 'comparison'),
    Pos.NUM: ('decl', 'case', 'number', 'gender', 'sort'),
    Pos.ADV: ('comparison',),
    Pos.V: ('conj', 'tense', 'voice', 'mood', 'person', 'number'),
    Pos.VPAR: ('conj', 'case', 'number', 'gender', 'tense', 'voice', 'mood'),
    Pos.SUPINE: ('conj', 'case', 'number', 'gender'),
    Pos.PREP: ('case',),
}

#  The extra "kind" of a unique form
UNIQUE_KIND_ATTRS = {Pos.N: 'kind', Pos.PRON: 'kind', Pos.PACK: 'kind',
                     Pos.NUM: 'value', Pos.V: 'kind', Pos.VPAR: 'kind',
                     Pos.SUPINE: 'kind'}

KIND_ENUM = {Pos.N: NounKind, Pos.PRON: PronounKind, Pos.PACK: PronounKind,
             Pos.V: VerbKind, Pos.VPAR: VerbKind, Pos.SUPINE: VerbKind}

ENUMS = {'gender': Gender, 'case': Case, 'number': Number,
         'comparison': Comparison, 'sort': NumeralSort, 'tense': Tense,
         'voice': Voice, 'mood': Mood}

CODES = (('age', Age), ('area', Area), ('geo', Geo), ('freq', Freq),
         ('source', Source))

DICTIONARY_POS = (Pos.N, Pos.PRON, Pos.PACK, Pos.ADJ, Pos.NUM, Pos.ADV,
                  Pos.V, Pos.PREP, Pos.CONJ, Pos.INTERJ)
TARGET_POS = (Pos.X, Pos.N, Pos.PRON, Pos.PACK, Pos.ADJ, Pos.NUM, Pos.ADV,
              Pos.V)
FORM_POS = tuple(p for p in Pos if p != Pos.X)


# ---------------------------------------------------------------------------
#  Parsing

class _Element:
    __slots__ = ('tag', 'attrs', 'line', 'children', 'text')

    def __init__(self, tag, attrs, line):
        self.tag = tag
        self.attrs = attrs
        self.line = line
        self.children = []
        self.text = []

    @property
    def content(self) -> str:
        return ''.join(self.text)


def _parse(path: str, root_tag: str,
           root: list | None = None) -> Iterator[_Element]:
    """The elements below the root of PATH (with their children), each
    given as soon as it has been read, so that the whole file is never held
    in memory.  The root element itself is appended to ROOT, if given."""
    parser = expat.ParserCreate()
    stack: list[_Element] = []
    done: list[_Element] = []

    def start(tag, attrs):
        el = _Element(tag, attrs, parser.CurrentLineNumber)
        if not stack and tag != root_tag:
            raise DataError(path, el.line, tr(
                'the root element must be <{root}>, not <{tag}>',
                root=root_tag, tag=tag))
        if not stack and root is not None:
            root.append(el)
        if len(stack) > 2:
            raise DataError(path, el.line, tr('<{tag}> is nested too deeply',
                                              tag=tag))
        if len(stack) >= 2:
            stack[-1].children.append(el)
        stack.append(el)

    def end(tag):
        el = stack.pop()
        if len(stack) == 1:
            done.append(el)

    def chars(data):
        if len(stack) > 1:      # the text of an element (not the layout)
            stack[-1].text.append(data)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(1 << 16)
                parser.Parse(chunk, not chunk)
                yield from done
                done.clear()
                if not chunk:
                    break
    except expat.ExpatError as e:
        raise DataError(path, e.lineno, tr('malformed XML: {error}',
                                           error=expat.ErrorString(e.code))
                        ) from None


class _Root(Exception):
    pass


def root_tag(path: str) -> str:
    """The name of the root element of the XML file PATH."""
    return root_element(path)[0]


def root_element(path: str) -> tuple[str, dict[str, str]]:
    """The name and attributes of the root element of the XML file PATH
    (without reading the rest)."""
    parser = expat.ParserCreate()

    def start(tag, attrs):
        raise _Root((tag, attrs))

    parser.StartElementHandler = start
    try:
        with open(path, 'rb') as f:
            parser.ParseFile(f)
    except _Root as e:
        return e.args[0]
    except expat.ExpatError as e:
        raise DataError(path, e.lineno, tr('malformed XML: {error}',
                                           error=expat.ErrorString(e.code))
                        ) from None
    raise DataError(path, 1, tr('the file has no root element'))


#  Many elements have the same grammar or codes: equal attribute values
#  give the same (immutable) record, which saves reading them again.
_SHARED: dict = {}


class _Reader:
    """Reads one element: typed access to its attributes and children."""

    def __init__(self, path: str, el: _Element):
        self.path = path
        self.el = el
        self.used = set()

    def _shared(self, kind, names, make):
        attrs = self.el.attrs
        key = (kind,) + tuple(attrs.get(n) for n in names)
        record = _SHARED.get(key)
        if record is None:
            record = _SHARED[key] = make()
        else:
            self.used.update(n for n in names if n in attrs)
        return record

    def fail(self, message: str, line: int | None = None, **about):
        """Raises the DataError MESSAGE; ABOUT: its field, value and
        problem."""
        raise DataError(self.path, line or self.el.line, message, **about)

    def bad(self, name: str, value: str, problem: str):
        """Raises the DataError: attribute NAME's VALUE has PROBLEM."""
        self.fail(f'{name}="{value}" {problem}', field=name, value=value,
                  problem=problem)

    def raw(self, name, default=None):
        if name not in self.el.attrs:
            if default is None:
                self.fail(tr('<{tag}> needs a {name} attribute',
                             tag=self.el.tag, name=name), field=name)
            return default
        self.used.add(name)
        return self.el.attrs[name]

    def enum(self, name, enum_cls, default=None):
        value = self.raw(name, None if default is None else '')
        if value == '' and default is not None:
            return default
        try:
            return enum_cls[value]
        except KeyError:
            names = ' '.join(m.name for m in enum_cls)
            self.bad(name, value, tr('is not one of: {names}', names=names))

    def integer(self, name, lo, hi):
        value = self.raw(name)
        if not value.isdigit() or not lo <= int(value) <= hi:
            self.bad(name, value, tr('must be a number from {lo} to {hi}',
                                     lo=lo, hi=hi))
        return int(value)

    def decl(self, name) -> Decl:
        value = self.raw(name)
        parts = value.split()
        if len(parts) != 2 or not all(p.isdigit() and len(p) == 1
                                      for p in parts):
            self.bad(name, value, tr('must be two digits, like "2 1"'))
        return Decl(int(parts[0]), int(parts[1]))

    def pos(self, allowed) -> Pos:
        pos = self.enum('pos', Pos)
        if pos not in allowed:
            names = ' '.join(p.name for p in allowed)
            self.bad('pos', pos.name, tr('is not allowed in <{tag}>; use '
                                         'one of: {names}', tag=self.el.tag,
                                         names=names))
        return pos

    def word(self, text: str, what: str, line=None, empty=False) -> str:
        if (text or not empty) and not (text and set(text) <= LETTERS):
            self.fail(tr('the {what} "{text}" may only contain the letters '
                         'a-z and A-Z', what=tr(what), text=text), line)
        if len(text) > MAX_STEM:
            self.fail(tr('the {what} "{text}" is longer than {n} letters',
                         what=tr(what), text=text, n=MAX_STEM), line)
        return text

    def uid(self, n: int) -> int:
        """The id attribute (N, the position, if there is none)."""
        value = self.raw('id', '')
        if not value:
            return n
        if not value.isdigit() or not 0 < int(value) < MAX_UID:
            self.bad('id', value, tr('must be a whole number above 0'))
        return int(value)

    def done(self):
        extra = set(self.el.attrs) - self.used
        if extra:
            names = ', '.join(sorted(extra))
            self.fail(tr('<{tag}> does not take the attributes {names} '
                         'here', tag=self.el.tag, names=names)
                      if len(extra) > 1 else
                      tr('<{tag}> does not take the attribute {names} here',
                         tag=self.el.tag, names=names))

    def children(self, expected):
        """{tag: [child elements]}, checked against EXPECTED, a dict
        {tag: (min, max)}."""
        found = {tag: [] for tag in expected}
        for child in self.el.children:
            if child.tag not in expected:
                self.fail(tr('<{tag}> cannot contain <{child}>',
                             tag=self.el.tag, child=child.tag), child.line)
            found[child.tag].append(child)
        for tag, (lo, hi) in expected.items():
            if not lo <= len(found[tag]) <= hi:
                need = tr('exactly {n}', n=lo) if lo == hi else \
                    tr('{lo} to {hi}', lo=lo, hi=hi)
                self.fail(tr('<{tag}> must contain {need} <{child}> '
                             'element', tag=self.el.tag, need=need,
                             child=tag) if hi == 1 else
                          tr('<{tag}> must contain {need} <{child}> '
                             'elements', tag=self.el.tag, need=need,
                             child=tag))
        return found

    def meaning(self, el: _Element) -> str:
        text = el.content
        if '\n' in text or '\r' in text:
            self.fail(tr('a <meaning> must be on one line'), el.line)
        return text

    # Grammar --------------------------------------------------------------

    def part(self, pos: Pos) -> Part:
        uses = PART_ATTRS.get(pos, ())
        return self._shared(('part', pos), uses, lambda: self._part(pos, uses))

    def _part(self, pos: Pos, uses) -> Part:
        kw = {}
        for name in uses:
            match name:
                case 'decl' | 'conj':
                    kw['decl'] = self.decl(name)
                case 'kind':
                    kw['kind'] = self.enum('kind', KIND_ENUM[pos])
                case 'value':
                    kw['value'] = self.integer('value', 0, 1000)
                case _:
                    kw[name] = self.enum(name, ENUMS[name])
        return Part(pos, **kw)

    def form(self, pos: Pos) -> Form:
        kw = {}
        for name in FORM_ATTRS.get(pos, ()):
            if name in ('decl', 'conj'):
                kw['decl'] = self.decl(name)
            elif name == 'person':
                kw['person'] = self.integer('person', 0, 3)
            else:
                kw[name] = self.enum(name, ENUMS[name])
        return Form(pos, **kw)

    def codes(self) -> Codes:
        def make():
            sources = self.sources()
            return Codes(*(self.enum(name, cls, cls.X)
                           for name, cls in CODES[:-1]),
                         sources[0], sources[1:])
        return self._shared('codes', [name for name, _ in CODES], make)

    def sources(self) -> tuple[Source, ...]:
        """The source attribute: one code or several ("O M"), the main
        one first."""
        value = self.raw('source', '')
        if not value.strip():
            return (Source.X,)
        out = []
        for code in value.split():
            if code not in Source.__members__:
                names = ' '.join(m.name for m in Source)
                self.bad('source', value,
                         tr('is not one of: {names}', names=names))
            if Source[code] in out:
                self.bad('source', value,
                         tr('repeats the source {code}', code=code))
            out.append(Source[code])
        if len(out) > 1 and Source.X in out:
            self.bad('source', value,
                     tr('has X (general or unknown) with other sources'))
        return tuple(out)


Loaded = list[tuple[object, int]]


def _read(path: str, root: str, errors: list | None,
          convert: Callable[[_Reader, int], object]) -> Loaded:
    out = []
    for el in _parse(path, root):
        try:
            out.append((convert(_Reader(path, el), len(out) + 1), el.line))
        except DataError as e:
            if errors is None:
                raise
            errors.append(e)
    return out


def _expect(r: _Reader, *tags):
    if r.el.tag not in tags:
        names = ', '.join(f'<{t}>' for t in tags)
        r.fail(tr('this file can only contain {names} elements, not <{tag}>',
                  names=names, tag=r.el.tag))


def _entry(r: _Reader, n: int, dictionary: str) -> Entry:
    _expect(r, 'entry')
    uid = r.uid(n)
    pos = r.pos(DICTIONARY_POS)
    part = r.part(pos)
    codes = r.codes()
    r.done()
    found = r.children({'stem': (1, 4), 'meaning': (1, 1)})
    stems = [r.word(s.content, 'stem', s.line, empty=True)
             for s in found['stem']]
    stems += [''] * (4 - len(stems))
    return Entry(n, tuple(stems), part, codes,
                 r.meaning(found['meaning'][0]), dictionary, uid)


def read_dictionary(path: str, errors=None,
                    dictionary='general') -> list[tuple[Entry, int]]:
    return _read(path, 'dictionary', errors,
                 lambda r, n: _entry(r, n, dictionary))


def entry_from_fields(attrs: dict, stems: list[str], meaning: str,
                      id: int = 0, dictionary: str = 'general',
                      uid: int = 0) -> Entry:
    """An entry from the values of its attributes (as in the XML: pos,
    decl or conj, gender ..., age, area ...), its stems and its meaning,
    checked as the reader checks the file (raises DataError)."""
    el = _Element('entry', {k: v for k, v in attrs.items() if v != ''}, 0)
    if uid:
        el.attrs['id'] = str(uid)
    stems = list(stems)
    while len(stems) > 1 and not stems[-1]:
        stems.pop()
    for text in stems or ['']:
        child = _Element('stem', {}, 0)
        child.text.append(text)
        el.children.append(child)
    child = _Element('meaning', {}, 0)
    child.text.append(meaning)
    el.children.append(child)
    return _entry(_Reader('entry', el), id, dictionary)


_LONG_ENDING = re.compile(r'[a-zA-ZāēīōūȳĀĒĪŌŪȲ]{1,' + str(MAX_ENDING) +
                          '}')


def read_inflections(path: str, errors=None) -> list[tuple[Inflection, int]]:
    def inflection(r: _Reader, n: int) -> Inflection:
        _expect(r, 'inflection')
        if r.el.children:
            r.fail(tr('<{tag}> has no content', tag='inflection'))
        pos = r.pos(FORM_POS)
        form = r.form(pos)
        key = r.integer('key', 0, 9)
        ending = r.raw('ending', '')
        if ending and not set(ending) <= LETTERS:
            r.bad('ending', ending, tr('may only contain letters'))
        if len(ending) > MAX_ENDING:
            r.bad('ending', ending, tr('is longer than {n} letters',
                                       n=MAX_ENDING))
        long = r.raw('long', '')
        if long and (not _LONG_ENDING.fullmatch(long) or
                     unmarked(long) != ending):
            r.bad('long', long, tr('is not the ending with long marks'))
        age = r.enum('age', Age, Age.X)
        freq = r.enum('freq', Freq, Freq.X)
        r.done()
        return Inflection(form, key, ending, age, freq, long)
    return _read(path, 'inflections', errors, inflection)


def read_uniques(path: str, errors=None) -> list[tuple[Unique, int]]:
    def unique(r: _Reader, n: int) -> Unique:
        _expect(r, 'unique')
        uid = r.uid(n)
        pos = r.pos(FORM_POS)
        form = r.form(pos)
        if pos == Pos.NUM:
            kind = r.integer('value', 0, 1000)
        elif pos in KIND_ENUM:
            kind = r.enum('kind', KIND_ENUM[pos])
        else:
            kind = None
        codes = r.codes()
        r.done()
        found = r.children({'form': (1, 1), 'meaning': (1, 1)})
        word = r.word(found['form'][0].content.strip(), 'form')
        return Unique(n, word, form, kind, codes,
                      r.meaning(found['meaning'][0]).strip(), uid)
    return _read(path, 'uniques', errors, unique)


def read_addons(path: str, errors=None):
    """-> list of (Prefix | Suffix | Tackon, line)."""
    def addon(r: _Reader, n: int):
        _expect(r, 'prefix', 'suffix', 'tackon')
        uid = r.uid(n)
        fix = r.word(r.raw('fix'), 'fix')
        tag = r.el.tag
        if tag == 'tackon':
            r.done()
            found = r.children({'base': (1, 1), 'meaning': (1, 1)})
            return Tackon(n, fix, _target(r.path, found['base'][0]),
                          r.meaning(found['meaning'][0]), uid)
        connect = r.raw('connect', '')
        if len(connect) > 1:
            r.bad('connect', connect, tr('must be a single character'))
        if tag == 'prefix':
            root = r.enum('root', Pos)
            target = r.enum('target', Pos)
            r.done()
            found = r.children({'meaning': (1, 1)})
            return Prefix(n, fix, connect, root, target,
                          r.meaning(found['meaning'][0]), uid)
        root = r.enum('root', Pos)
        root_key = r.integer('rootkey', 0, 9)
        target_key = r.integer('targetkey', 0, 9)
        r.done()
        found = r.children({'target': (1, 1), 'meaning': (1, 1)})
        return Suffix(n, fix, connect, root, root_key,
                      _target(r.path, found['target'][0]), target_key,
                      r.meaning(found['meaning'][0]), uid)
    return _read(path, 'addons', errors, addon)


#  A stem with its long vowels marked (data/quantities.xml), or '-'
_LONG_STEM = re.compile(r'-|[a-zA-ZāēīōūȳĀĒĪŌŪȲ]{1,' + str(MAX_STEM) + '}')


def read_quantities(path: str, errors=None) -> list[tuple[tuple[int, tuple[
        str, ...]], int]]:
    """The long vowels of the stems of entries: a list of ((entry id,
    stems), line), each stem with its long vowels marked (amīc), or '-'
    where they are not known."""
    seen = {}

    def stems(r: _Reader, n: int) -> tuple[int, tuple[str, ...]]:
        _expect(r, 'stems')
        value = r.raw('entry')
        if not value.isdigit() or not 0 < int(value) < MAX_UID:
            r.bad('entry', value, tr('must be a whole number above 0'))
        uid = int(value)
        r.done()
        r.children({})
        marked = tuple(r.el.content.split())
        if not 0 < len(marked) <= 4:
            r.fail(tr('<stems> must have from one to four stems'))
        for m in marked:
            if not _LONG_STEM.fullmatch(m):
                r.fail(tr('the stem "{text}" may only contain letters, '
                          'with long marks on vowels (ā), or be -', text=m))
        if uid in seen:
            r.fail(tr('{what} is already on line {line}',
                      what=f'entry="{uid}"', line=seen[uid]))
        seen[uid] = r.el.line
        return uid, marked
    return _read(path, 'quantities', errors, stems)


def read_sources(path: str, errors=None) -> list[tuple[tuple[str, str],
                                                        int]]:
    """The sources that the source codes of the entries stand for: a list
    of ((code, name), line)."""
    seen = {}

    def source(r: _Reader, n: int) -> tuple[str, str]:
        _expect(r, 'source')
        code = r.enum('code', Source).name
        name = r.raw('name').strip()
        r.done()
        r.children({})
        if not name:
            r.fail(tr('the source {code} has no name', code=code))
        if code in seen:
            r.fail(tr('the source {code} is already on line {line}',
                      code=code, line=seen[code]))
        seen[code] = r.el.line
        return code, name
    return _read(path, 'sources', errors, source)


#  The categories of gloss.xml, and the codes each one glosses
GLOSS_CODES = {
    'case': [m.name for m in Case if m != Case.X],
    'number': [m.name for m in Number if m != Number.X],
    'gender': [m.name for m in Gender if m != Gender.X],
    'person': ['1', '2', '3'],
    'tense': [m.name for m in Tense if m != Tense.X],
    'voice': [m.name for m in Voice if m != Voice.X],
    'mood': [m.name for m in Mood if m != Mood.X],
    'form': ['SUPINE'],
    'comparison': [m.name for m in Comparison if m != Comparison.X],
    'sort': [m.name for m in NumeralSort if m != NumeralSort.X],
}
_ABBREVIATION = re.compile(r'[A-Z0-9]+(\.[A-Z0-9]+)*')


class Gloss(NamedTuple):
    category: str
    code: str
    abbreviation: str
    meaning: str
    leipzig: bool          # one of the standard Leipzig abbreviations


def read_glosses(path: str, errors=None) -> list[tuple[Gloss, int]]:
    """The abbreviations used in the analyses: a list of (Gloss, line)."""
    seen = {}

    def gloss(r: _Reader, n: int) -> Gloss:
        _expect(r, 'gloss')
        category = r.raw('category')
        if category not in GLOSS_CODES:
            r.bad('category', category, tr('is not one of: {names}',
                                           names=' '.join(GLOSS_CODES)))
        code = r.raw('code')
        if code not in GLOSS_CODES[category]:
            r.bad('code', code, tr('is not one of: {names}',
                                   names=' '.join(GLOSS_CODES[category])))
        abbreviation = r.raw('abbreviation')
        if not _ABBREVIATION.fullmatch(abbreviation):
            r.bad('abbreviation', abbreviation,
                  tr('must be capital letters and digits, parts joined by '
                     'dots (FUT.PRF)'))
        meaning = r.raw('meaning').strip()
        leipzig = r.raw('leipzig', 'no')
        if leipzig not in ('yes', 'no'):
            r.bad('leipzig', leipzig, tr('must be yes or no'))
        r.done()
        r.children({})
        key = (category, code)
        if key in seen:
            r.fail(tr('{what} is already on line {line}',
                      what=f'{category} {code}', line=seen[key]))
        seen[key] = r.el.line
        return Gloss(category, code, abbreviation, meaning, leipzig == 'yes')
    return _read(path, 'glosses', errors, gloss)


#  What a <meaning> of a language file can translate: the attribute that
#  names it (entry="12": the entry of dictionary.xml whose id is 12)
TRANSLATED = ('entry', 'special', 'unique', 'addon', 'builtin')
BUILTIN = ('esse',)                     # the entries built into the program
_LANGUAGE_CODE = re.compile(r'[a-z]{2,3}(-[A-Za-z0-9]{1,8})*')


class LanguageData(NamedTuple):
    """What a language file says (see languages.py)."""
    code: str
    name: str                   # in English ("Spanish")
    native: str                 # in the language itself ("Español")
    reference: bool             # its meanings are those of the data files
    noise: frozenset[str]
    common: tuple[tuple[frozenset[str], tuple[Pos, ...] | None], ...]
    numerals: dict[NumeralSort, str]
    meanings: dict[tuple[str, int | str], str]
    #  the texts of the results it translates, by their English (with its
    #  spaces made single)
    texts: dict[str, str] = {}
    #  the dictionary a meaning was taken from (source="m"), by its key,
    #  for the meanings that were not translated from the English
    sources: dict[tuple[str, int | str], Source] = {}


_PLACEHOLDER = re.compile(r'\{\d\}')


def read_language(path: str, errors=None) -> LanguageData:
    """A language file: the language's name, the words its reverse search
    leaves out, its sentences for numerals, the meanings in it and the
    texts of the results it translates."""
    root: list[_Element] = []
    noise: set[str] = set()
    common = []
    numerals = {}
    meanings = {}
    texts = {}
    sources = {}
    seen = {}

    def item(r: _Reader, n: int):
        _expect(r, 'noise', 'common', 'numeral', 'meaning', 'text')
        tag = r.el.tag
        text = r.el.content if tag in ('noise', 'common') else \
            r.meaning(r.el)
        if tag == 'noise':
            r.done()
            noise.update(text.split())
            return
        if tag == 'common':
            value = r.raw('pos', '')
            try:
                pos = tuple(Pos[p] for p in value.split()) if value \
                    else None
            except KeyError:
                r.bad('pos', value, tr('must be parts of speech (N V ...)'))
            r.done()
            common.append((frozenset(text.split()), pos))
            return
        if tag == 'numeral':
            sort = r.enum('sort', NumeralSort)
            r.done()
            key = ('numeral', sort.name)
        elif tag == 'text':
            english = ' '.join(r.raw('en').split())
            r.done()
            if not english:
                r.fail(tr('en="" is empty'))
            if sorted(_PLACEHOLDER.findall(english)) != \
                    sorted(_PLACEHOLDER.findall(text)):
                r.fail(tr('the text must have the {1}, {2} ... of en="..."'))
            key = ('text', english)
        else:
            named = [a for a in TRANSLATED if a in r.el.attrs]
            if len(named) != 1:
                r.fail(tr('a <meaning> needs one of the attributes {names}',
                          names=', '.join(TRANSLATED)))
            kind = named[0]
            if kind == 'builtin':
                which = r.raw(kind)
                if which not in BUILTIN:
                    r.bad('builtin', which, tr('is not one of: {names}',
                                               names=' '.join(BUILTIN)))
            else:
                value = r.raw(kind)
                if not value.isdigit() or not 0 < int(value) < MAX_UID:
                    r.bad(kind, value, tr('must be the id of one'))
                which = int(value)
            source = r.enum('source', Source) \
                if 'source' in r.el.attrs else None
            r.done()
            key = (kind, which)
            if source is not None:
                sources[key] = source
        if key in seen:
            r.fail(tr('{what} is already on line {line}',
                      what=f'{key[0]} {key[1]}', line=seen[key]))
        seen[key] = r.el.line
        if not text.strip():
            r.fail(tr('the text is empty'))
        if tag == 'numeral':
            numerals[sort] = text           # (as it is: spaces matter)
        elif tag == 'text':
            texts[key[1]] = text.strip()
        else:
            meanings[key] = text.strip()

    for el in _parse(path, 'language', root):
        try:
            item(_Reader(path, el), 0)
        except DataError as e:
            if errors is None:
                raise
            errors.append(e)
    if not root:
        raise DataError(path, 1, tr('the file has no root element'))
    r = _Reader(path, root[0])
    r.used.update(('xmlns:xsi', 'xsi:noNamespaceSchemaLocation'))
    code = r.raw('code')
    if not _LANGUAGE_CODE.fullmatch(code):
        r.bad('code', code, tr('must be a language code, like en or es'))
    name = r.raw('name').strip()
    native = r.raw('native', name).strip()
    reference = r.raw('reference', 'no')
    if reference not in ('yes', 'no'):
        r.bad('reference', reference, tr('must be yes or no'))
    r.done()
    if not name:
        r.fail(tr('the language has no name'))
    return LanguageData(code, name, native, reference == 'yes',
                        frozenset(noise), tuple(common), numerals, meanings,
                        texts, sources)


def language_xml(kind: str, which, text: str, source: str = '') -> str:
    """A <meaning> of a language file (SOURCE: the code of the dictionary
    it was taken from, if any)."""
    pairs = [(kind, str(which))] + ([('source', source)] if source else [])
    return f'<meaning{_attrs(pairs)}>{escape(text)}</meaning>'


_MEANING_LINE = re.compile(r'(\s*)<meaning (\w+)="([^"]*)"'
                           r'(?: source="([^"]*)")?>(.*?)</meaning>')


def update_language(path: str, changes: dict[tuple[str, int], str | None],
                    notes: dict[tuple[str, int], str] | None = None) -> bool:
    """Changes the <meaning>s of the language file PATH: CHANGES gives the
    new text of each (kind, id), or None to take it out.  A meaning that
    is not there yet goes among the others of its kind, in the order of the
    ids.  NOTES: the comment after a meaning changed or added (its entry's
    dictionary form; without one, a meaning changed keeps its comment).
    The rest of the file stays as it is; a meaning whose text changes
    loses its source="..." (it is no longer the dictionary's).  Returns
    whether the file was changed."""
    with open(path, encoding='utf-8') as f:
        lines = f.read().split('\n')
    notes = notes or {}

    def where():
        """{(kind, id): line number}, from the lines as they are now."""
        out = {}
        for i, line in enumerate(lines):
            m = _MEANING_LINE.match(line)
            if m and m.group(3).isdigit():
                out[m.group(2), int(m.group(3))] = i
        return out

    def line_of(indent, key, text, rest='', source=''):
        """The line of a meaning; REST: what followed it (kept if there is
        no note)."""
        out = indent + language_xml(key[0], key[1], text, source)
        return out + (' ' + comment(' ' + notes[key] + ' ')
                      if key in notes else rest)

    changed = False
    for key, text in sorted(changes.items()):
        places = where()
        i = places.get(key)
        if i is not None:
            if text is None:
                del lines[i]
            else:
                m = _MEANING_LINE.match(lines[i])
                same = text == unescape(m.group(5))
                new = line_of(m.group(1), key, text, lines[i][m.end():],
                              (m.group(4) or '') if same else '')
                if new == lines[i]:
                    continue
                lines[i] = new
            changed = True
            continue
        if text is None:
            continue
        same = sorted((k[1], n) for k, n in places.items()
                      if k[0] == key[0])
        after = [n for uid, n in same if uid > key[1]]
        if after:
            at, indent = after[0], _MEANING_LINE.match(
                lines[after[0]]).group(1)
        elif same:
            at = same[-1][1] + 1
            indent = _MEANING_LINE.match(lines[same[-1][1]]).group(1)
        else:
            at = next(i for i in range(len(lines) - 1, -1, -1)
                      if lines[i].strip().startswith('</language>'))
            indent = '  '
        lines.insert(at, line_of(indent, key, text))
        changed = True
    if changed:
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(lines))
        os.replace(tmp, path)
    return changed


def _target(path: str, el: _Element) -> Part:
    r = _Reader(path, el)
    if el.children or el.content.strip():
        r.fail(tr('<{tag}> has no content', tag=el.tag))
    part = r.part(r.pos(TARGET_POS))
    r.done()
    return part


# ---------------------------------------------------------------------------
#  Writing

def _value(v) -> str:
    return v.name if hasattr(v, 'name') else str(v)


def part_attrs(part: Part) -> list[tuple[str, str]]:
    pairs = [('pos', part.pos.name)]
    for name in PART_ATTRS.get(part.pos, ()):
        attr = 'decl' if name == 'conj' else name
        pairs.append((name, _value(getattr(part, attr))))
    return pairs


def form_attrs(form: Form) -> list[tuple[str, str]]:
    pairs = [('pos', form.pos.name)]
    for name in FORM_ATTRS.get(form.pos, ()):
        attr = 'decl' if name == 'conj' else name
        pairs.append((name, _value(getattr(form, attr))))
    return pairs


def codes_attrs(codes: Codes) -> list[tuple[str, str]]:
    return [(name, getattr(codes, name).name) for name, _ in CODES[:-1]] + \
        [('source', ' '.join(s.name for s in codes.sources))]


def _attrs(pairs) -> str:
    return ''.join(f' {n}={quoteattr(v)}' for n, v in pairs)


HEADERS = {
    'dictionary': 'The WORDS dictionary: one <entry> per dictionary entry. '
                  'See words.xsd. The entries with source code S that were '
                  'added in October 2026 come from Lewis and Short, A Latin '
                  'Dictionary (Oxford, 1879): text provided under a CC '
                  'BY-SA license by Perseus Digital Library, '
                  'http://www.perseus.tufts.edu, with funding from The '
                  'National Endowment for the Humanities. Data accessed '
                  'from https://github.com/PerseusDL/lexica/ on '
                  '2026-10-23. The entries with source code m come from R. '
                  'de Miguel and the Marqués de Morante, Nuevo diccionario '
                  'latino-español etimológico (Leipzig, 1867).',
    'inflections': 'The inflectional endings used by WORDS. The long '
                   'vowels of the endings (long) were taken from the '
                   'models of Collatinus 11, by Yves Ouvrard and Philippe '
                   'Verkerk (GNU GPL, version 2 or later). See words.xsd.',
    'uniques': 'Irregular forms that are not built from a stem and an '
               'ending. See words.xsd.',
    'addons': 'Prefixes, suffixes and enclitics (tackons). See words.xsd.',
    'sources': 'The sources named by the source codes of the entries. See '
               'words.xsd.',
    'glosses': 'The glossing abbreviations of the analyses (Leipzig '
               'Glossing Rules; see https://en.wikipedia.org/wiki/'
               'List_of_glossing_abbreviations). See words.xsd.',
}


def write_file(path: str, root: str, body: list[str], wrap=False):
    """Writes a data file: the XML declaration, a comment, the root element
    with BODY (lines) inside.  The file is replaced only when complete.
    With WRAP, the root element's attributes go on two lines."""
    tmp = path + '.tmp'
    opening = root_open(root)
    if wrap:
        opening = opening.replace(' xsi:no', '\n  xsi:no')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(comment(' ' + HEADERS[root] + ' ') + '\n')
        f.write(opening + '\n')
        for line in body:
            f.write(('  ' + line if line else '') + '\n')
        f.write(f'</{root}>\n')
    os.replace(tmp, path)


def write_dictionary(path: str, entries) -> None:
    """Writes the entries in the readable layout of entry_lines."""
    write_file(path, 'dictionary',
               [line for e in entries for line in entry_lines(e)], wrap=True)


def comment(text: str) -> str:
    """An XML comment holding TEXT ('--' cannot occur inside one)."""
    while '--' in text:
        text = text.replace('--', '- -')
    if text.endswith('-'):
        text += ' '
    return f'<!--{text}-->'


def root_open(tag: str) -> str:
    return (f'<{tag} xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xsi:noNamespaceSchemaLocation="{SCHEMA}">')


def entry_xml(entry: Entry) -> str:
    stems = list(entry.stems)
    while len(stems) > 1 and stems[-1] == '':
        stems.pop()
    body = ''.join(f'<stem>{escape(s)}</stem>' if s else '<stem/>'
                   for s in stems)
    attrs = _attrs(_uid(entry) + part_attrs(entry.part) +
                   codes_attrs(entry.codes))
    return (f'<entry{attrs}>{body}<meaning>{escape(entry.meaning)}'
            '</meaning></entry>')


WIDTH = 79             # the longest line of entry attributes, indented


def entry_lines(entry: Entry) -> list[str]:
    """ENTRY as lines, indented relative to <entry>: its attributes
    wrapped to WIDTH, then each stem and the meaning on a line of its own."""
    attrs = [_attrs([pair]) for pair in
             _uid(entry) + part_attrs(entry.part) + codes_attrs(entry.codes)]
    lines, line = [], '<entry'
    for i, a in enumerate(attrs):
        end = 1 if i == len(attrs) - 1 else 0          # the closing '>'
        if 2 + len(line) + len(a) + end > WIDTH and line != '<entry':
            lines.append(line)
            line = ' ' + a
        else:
            line += a
    lines.append(line + '>')
    stems = list(entry.stems)
    while len(stems) > 1 and stems[-1] == '':
        stems.pop()
    lines += [f'  <stem>{escape(s)}</stem>' if s else '  <stem/>'
              for s in stems]
    lines += [f'  <meaning>{escape(entry.meaning)}</meaning>', '</entry>']
    return lines


def inflection_xml(infl: Inflection) -> str:
    pairs = form_attrs(infl.form) + [('key', str(infl.key)),
                                     ('ending', infl.ending)] + \
        ([('long', infl.long)] if infl.long else []) + [
                                     ('age', infl.age.name),
                                     ('freq', infl.freq.name)]
    return f'<inflection{_attrs(pairs)}/>'


def _uid(record) -> list[tuple[str, str]]:
    """The id attribute of RECORD (its position, if it has no id)."""
    return [('id', str(record.uid or record.id))]


def unique_xml(u: Unique) -> str:
    pairs = _uid(u) + form_attrs(u.form)
    if u.form.pos in UNIQUE_KIND_ATTRS:
        pairs.append((UNIQUE_KIND_ATTRS[u.form.pos], _value(u.kind)))
    pairs += codes_attrs(u.codes)
    return (f'<unique{_attrs(pairs)}><form>{escape(u.word)}</form>'
            f'<meaning>{escape(u.meaning)}</meaning></unique>')


def addon_xml(addon) -> str:
    if isinstance(addon, Tackon):
        return (f'<tackon{_attrs(_uid(addon))} fix={quoteattr(addon.fix)}>'
                f'<base{_attrs(part_attrs(addon.base))}/>'
                f'<meaning>{escape(addon.meaning)}</meaning></tackon>')
    pairs = _uid(addon) + [('fix', addon.fix)]
    if addon.connect:
        pairs.append(('connect', addon.connect))
    if isinstance(addon, Prefix):
        pairs += [('root', addon.root.name), ('target', addon.target.name)]
        return (f'<prefix{_attrs(pairs)}><meaning>{escape(addon.meaning)}'
                '</meaning></prefix>')
    pairs += [('root', addon.root.name), ('rootkey', str(addon.root_key)),
              ('targetkey', str(addon.target_key))]
    return (f'<suffix{_attrs(pairs)}>'
            f'<target{_attrs(part_attrs(addon.target))}/>'
            f'<meaning>{escape(addon.meaning)}</meaning></suffix>')
