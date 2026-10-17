"""Reading and writing the data files.

    dictionary.xml   <dictionary> of <entry>
    inflections.xml  <inflections> of <inflection>
    uniques.xml      <uniques> of <unique>
    addons.xml       <addons> of <prefix>, <suffix> and <tackon>
    sources.xml      <sources> of <source>: the names of the source codes
    gloss.xml        <glosses> of <gloss>: the abbreviations of the analyses

words.xsd describes them.  Grammatical codes are written as in the
original WORDS files (N, V, NOM, PRES, ...), declensions and conjugations
as two digits ("2 1").  The order of the elements matters.

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
from xml.sax.saxutils import escape, quoteattr

from model import (
    Pos, Gender, Case, Number, Comparison, NumeralSort, Tense, Voice, Mood,
    NounKind, PronounKind, VerbKind, Age, Freq, Area, Geo, Source, Decl,
    Codes, Part, Form, Inflection, Entry, Unique, Prefix, Suffix, Tackon)

SCHEMA = 'words.xsd'
MAX_STEM = 18                   # letters in a stem, form or affix
MAX_ENDING = 7

LETTERS = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')


class DataError(Exception):
    """A problem in a data file, with its location."""

    def __init__(self, path, line, message):
        super().__init__(f'{path}:{line}: {message}')
        self.path = path
        self.line = line
        self.message = message


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


def _parse(path: str, root_tag: str) -> Iterator[_Element]:
    """The elements below the root of PATH (with their children), each
    given as soon as it has been read, so that the whole file is never held
    in memory."""
    parser = expat.ParserCreate()
    stack: list[_Element] = []
    done: list[_Element] = []

    def start(tag, attrs):
        el = _Element(tag, attrs, parser.CurrentLineNumber)
        if not stack and tag != root_tag:
            raise DataError(path, el.line, f'the root element must be '
                            f'<{root_tag}>, not <{tag}>')
        if len(stack) > 2:
            raise DataError(path, el.line, f'<{tag}> is nested too deeply')
        if len(stack) >= 2:
            stack[-1].children.append(el)
        stack.append(el)

    def end(tag):
        el = stack.pop()
        if len(stack) == 1:
            done.append(el)

    def chars(data):
        if len(stack) == 3:     # the text of a child (the rest is layout)
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
        raise DataError(path, e.lineno, f'malformed XML: '
                        f'{expat.ErrorString(e.code)}') from None


class _Root(Exception):
    pass


def root_tag(path: str) -> str:
    """The name of the root element of the XML file PATH."""
    parser = expat.ParserCreate()

    def start(tag, attrs):
        raise _Root(tag)

    parser.StartElementHandler = start
    try:
        with open(path, 'rb') as f:
            parser.ParseFile(f)
    except _Root as e:
        return e.args[0]
    except expat.ExpatError as e:
        raise DataError(path, e.lineno, f'malformed XML: '
                        f'{expat.ErrorString(e.code)}') from None
    raise DataError(path, 1, 'the file has no root element')


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

    def fail(self, message: str, line: int | None = None):
        raise DataError(self.path, line or self.el.line, message)

    def raw(self, name, default=None):
        if name not in self.el.attrs:
            if default is None:
                self.fail(f'<{self.el.tag}> needs a {name} attribute')
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
            self.fail(f'{name}="{value}" is not one of: {names}')

    def integer(self, name, lo, hi):
        value = self.raw(name)
        if not value.isdigit() or not lo <= int(value) <= hi:
            self.fail(f'{name}="{value}" must be a number from {lo} to {hi}')
        return int(value)

    def decl(self, name) -> Decl:
        value = self.raw(name)
        parts = value.split()
        if len(parts) != 2 or not all(p.isdigit() and len(p) == 1
                                      for p in parts):
            self.fail(f'{name}="{value}" must be two digits, like "2 1"')
        return Decl(int(parts[0]), int(parts[1]))

    def pos(self, allowed) -> Pos:
        pos = self.enum('pos', Pos)
        if pos not in allowed:
            names = ' '.join(p.name for p in allowed)
            self.fail(f'pos="{pos.name}" is not allowed in <{self.el.tag}>; '
                      f'use one of: {names}')
        return pos

    def word(self, text: str, what: str, line=None, empty=False) -> str:
        if (text or not empty) and not (text and set(text) <= LETTERS):
            self.fail(f'the {what} "{text}" may only contain the letters '
                      'a-z and A-Z', line)
        if len(text) > MAX_STEM:
            self.fail(f'the {what} "{text}" is longer than {MAX_STEM} '
                      'letters', line)
        return text

    def done(self):
        extra = set(self.el.attrs) - self.used
        if extra:
            plural = 's' if len(extra) > 1 else ''
            names = ', '.join(sorted(extra))
            self.fail(f'<{self.el.tag}> does not take the attribute{plural} '
                      f'{names} here')

    def children(self, expected):
        """{tag: [child elements]}, checked against EXPECTED, a dict
        {tag: (min, max)}."""
        found = {tag: [] for tag in expected}
        for child in self.el.children:
            if child.tag not in expected:
                self.fail(f'<{self.el.tag}> cannot contain <{child.tag}>',
                          child.line)
            found[child.tag].append(child)
        for tag, (lo, hi) in expected.items():
            if not lo <= len(found[tag]) <= hi:
                need = f'exactly {lo}' if lo == hi else f'{lo} to {hi}'
                plural = '' if hi == 1 else 's'
                self.fail(f'<{self.el.tag}> must contain {need} <{tag}> '
                          f'element{plural}')
        return found

    def meaning(self, el: _Element) -> str:
        text = el.content
        if '\n' in text or '\r' in text:
            self.fail('a <meaning> must be on one line', el.line)
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
        return self._shared('codes', [name for name, _ in CODES],
                            lambda: Codes(*(self.enum(name, cls, cls.X)
                                            for name, cls in CODES)))


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
        r.fail(f'this file can only contain {names} elements, not '
               f'<{r.el.tag}>')


def _entry(r: _Reader, n: int, dictionary: str) -> Entry:
    _expect(r, 'entry')
    pos = r.pos(DICTIONARY_POS)
    part = r.part(pos)
    codes = r.codes()
    r.done()
    found = r.children({'stem': (1, 4), 'meaning': (1, 1)})
    stems = [r.word(s.content, 'stem', s.line, empty=True)
             for s in found['stem']]
    stems += [''] * (4 - len(stems))
    return Entry(n, tuple(stems), part, codes,
                 r.meaning(found['meaning'][0]), dictionary)


def read_dictionary(path: str, errors=None,
                    dictionary='general') -> list[tuple[Entry, int]]:
    return _read(path, 'dictionary', errors,
                 lambda r, n: _entry(r, n, dictionary))


def entry_from_fields(attrs: dict, stems: list[str], meaning: str,
                      id: int = 0, dictionary: str = 'general') -> Entry:
    """An entry from the values of its attributes (as in the XML: pos,
    decl or conj, gender ..., age, area ...), its stems and its meaning,
    checked as the reader checks the file (raises DataError)."""
    el = _Element('entry', {k: v for k, v in attrs.items() if v != ''}, 0)
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


def read_inflections(path: str, errors=None) -> list[tuple[Inflection, int]]:
    def inflection(r: _Reader, n: int) -> Inflection:
        _expect(r, 'inflection')
        if r.el.children:
            r.fail('<inflection> has no content')
        pos = r.pos(FORM_POS)
        form = r.form(pos)
        key = r.integer('key', 0, 9)
        ending = r.raw('ending', '')
        if ending and not set(ending) <= LETTERS:
            r.fail(f'ending="{ending}" may only contain letters')
        if len(ending) > MAX_ENDING:
            r.fail(f'ending="{ending}" is longer than {MAX_ENDING} letters')
        age = r.enum('age', Age, Age.X)
        freq = r.enum('freq', Freq, Freq.X)
        r.done()
        return Inflection(form, key, ending, age, freq)
    return _read(path, 'inflections', errors, inflection)


def read_uniques(path: str, errors=None) -> list[tuple[Unique, int]]:
    def unique(r: _Reader, n: int) -> Unique:
        _expect(r, 'unique')
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
                      r.meaning(found['meaning'][0]).strip())
    return _read(path, 'uniques', errors, unique)


def read_addons(path: str, errors=None):
    """-> list of (Prefix | Suffix | Tackon, line)."""
    def addon(r: _Reader, n: int):
        _expect(r, 'prefix', 'suffix', 'tackon')
        fix = r.word(r.raw('fix'), 'fix')
        tag = r.el.tag
        if tag == 'tackon':
            r.done()
            found = r.children({'base': (1, 1), 'meaning': (1, 1)})
            return Tackon(n, fix, _target(r.path, found['base'][0]),
                          r.meaning(found['meaning'][0]))
        connect = r.raw('connect', '')
        if len(connect) > 1:
            r.fail(f'connect="{connect}" must be a single character')
        if tag == 'prefix':
            root = r.enum('root', Pos)
            target = r.enum('target', Pos)
            r.done()
            found = r.children({'meaning': (1, 1)})
            return Prefix(n, fix, connect, root, target,
                          r.meaning(found['meaning'][0]))
        root = r.enum('root', Pos)
        root_key = r.integer('rootkey', 0, 9)
        target_key = r.integer('targetkey', 0, 9)
        r.done()
        found = r.children({'target': (1, 1), 'meaning': (1, 1)})
        return Suffix(n, fix, connect, root, root_key,
                      _target(r.path, found['target'][0]), target_key,
                      r.meaning(found['meaning'][0]))
    return _read(path, 'addons', errors, addon)


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
            r.fail(f'the source {code} has no name')
        if code in seen:
            r.fail(f'the source {code} is already on line {seen[code]}')
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
            r.fail(f'category="{category}" is not one of: '
                   + ' '.join(GLOSS_CODES))
        code = r.raw('code')
        if code not in GLOSS_CODES[category]:
            r.fail(f'code="{code}" is not one of: '
                   + ' '.join(GLOSS_CODES[category]))
        abbreviation = r.raw('abbreviation')
        if not _ABBREVIATION.fullmatch(abbreviation):
            r.fail(f'abbreviation="{abbreviation}" must be capital letters '
                   'and digits, parts joined by dots (FUT.PRF)')
        meaning = r.raw('meaning').strip()
        leipzig = r.raw('leipzig', 'no')
        if leipzig not in ('yes', 'no'):
            r.fail(f'leipzig="{leipzig}" must be yes or no')
        r.done()
        r.children({})
        key = (category, code)
        if key in seen:
            r.fail(f'{category} {code} is already on line {seen[key]}')
        seen[key] = r.el.line
        return Gloss(category, code, abbreviation, meaning, leipzig == 'yes')
    return _read(path, 'glosses', errors, gloss)


def _target(path: str, el: _Element) -> Part:
    r = _Reader(path, el)
    if el.children or el.content.strip():
        r.fail(f'<{el.tag}> has no content')
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
    return [(name, getattr(codes, name).name) for name, _ in CODES]


def _attrs(pairs) -> str:
    return ''.join(f' {n}={quoteattr(v)}' for n, v in pairs)


HEADERS = {
    'dictionary': 'The WORDS dictionary: one <entry> per dictionary entry. '
                  'See words.xsd.',
    'inflections': 'The inflectional endings used by WORDS. See words.xsd.',
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
    attrs = _attrs(part_attrs(entry.part) + codes_attrs(entry.codes))
    return (f'<entry{attrs}>{body}<meaning>{escape(entry.meaning)}'
            '</meaning></entry>')


WIDTH = 79             # the longest line of entry attributes, indented


def entry_lines(entry: Entry) -> list[str]:
    """ENTRY as lines, indented relative to <entry>: its attributes
    wrapped to WIDTH, then each stem and the meaning on a line of its own."""
    attrs = [_attrs([pair]) for pair in
             part_attrs(entry.part) + codes_attrs(entry.codes)]
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
                                     ('ending', infl.ending),
                                     ('age', infl.age.name),
                                     ('freq', infl.freq.name)]
    return f'<inflection{_attrs(pairs)}/>'


def unique_xml(u: Unique) -> str:
    pairs = form_attrs(u.form)
    if u.form.pos in UNIQUE_KIND_ATTRS:
        pairs.append((UNIQUE_KIND_ATTRS[u.form.pos], _value(u.kind)))
    pairs += codes_attrs(u.codes)
    return (f'<unique{_attrs(pairs)}><form>{escape(u.word)}</form>'
            f'<meaning>{escape(u.meaning)}</meaning></unique>')


def addon_xml(addon) -> str:
    if isinstance(addon, Tackon):
        return (f'<tackon fix={quoteattr(addon.fix)}>'
                f'<base{_attrs(part_attrs(addon.base))}/>'
                f'<meaning>{escape(addon.meaning)}</meaning></tackon>')
    pairs = [('fix', addon.fix)]
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
