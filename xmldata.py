"""Reading and writing the data files.

    dictionary.xml   <dictionary> of <entry>
    inflections.xml  <inflections> of <inflection>
    uniques.xml      <uniques> of <unique>
    addons.xml       <addons> of <prefix>, <suffix> and <tackon>

words.xsd describes them.  Grammatical codes are written as in the
original WORDS files (N, V, NOM, PRES, ...), declensions and conjugations
as two digits ("2 1").  The order of the elements matters.

The readers return (record, line number) pairs in file order and check the
files as they go.  A problem raises DataError, or, if the caller passes a
list as ERRORS, is appended to it and the element skipped.
"""

from __future__ import annotations

import os
from typing import Callable, Iterator, List, Optional, Tuple
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
        super().__init__('%s:%s: %s' % (path, line, message))
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
    stack: List[_Element] = []
    done: List[_Element] = []

    def start(tag, attrs):
        el = _Element(tag, attrs, parser.CurrentLineNumber)
        if not stack and tag != root_tag:
            raise DataError(path, el.line, 'the root element must be <%s>, '
                            'not <%s>' % (root_tag, tag))
        if len(stack) > 2:
            raise DataError(path, el.line, '<%s> is nested too deeply' % tag)
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
        raise DataError(path, e.lineno, 'malformed XML: %s'
                        % expat.ErrorString(e.code)) from None


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
        raise DataError(path, e.lineno, 'malformed XML: %s'
                        % expat.ErrorString(e.code)) from None
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

    def fail(self, message: str, line: Optional[int] = None):
        raise DataError(self.path, line or self.el.line, message)

    def raw(self, name, default=None):
        if name not in self.el.attrs:
            if default is None:
                self.fail('<%s> needs a %s attribute' % (self.el.tag, name))
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
            self.fail('%s="%s" is not one of: %s' % (
                name, value, ' '.join(m.name for m in enum_cls)))

    def integer(self, name, lo, hi):
        value = self.raw(name)
        if not value.isdigit() or not lo <= int(value) <= hi:
            self.fail('%s="%s" must be a number from %d to %d' % (
                name, value, lo, hi))
        return int(value)

    def decl(self, name) -> Decl:
        value = self.raw(name)
        parts = value.split()
        if len(parts) != 2 or not all(p.isdigit() and len(p) == 1
                                      for p in parts):
            self.fail('%s="%s" must be two digits, like "2 1"' % (
                name, value))
        return Decl(int(parts[0]), int(parts[1]))

    def pos(self, allowed) -> Pos:
        pos = self.enum('pos', Pos)
        if pos not in allowed:
            self.fail('pos="%s" is not allowed in <%s>; use one of: %s' % (
                pos.name, self.el.tag, ' '.join(p.name for p in allowed)))
        return pos

    def word(self, text: str, what: str, line=None, empty=False) -> str:
        if (text or not empty) and not (text and set(text) <= LETTERS):
            self.fail('the %s "%s" may only contain the letters a-z and A-Z'
                      % (what, text), line)
        if len(text) > MAX_STEM:
            self.fail('the %s "%s" is longer than %d letters'
                      % (what, text, MAX_STEM), line)
        return text

    def done(self):
        extra = set(self.el.attrs) - self.used
        if extra:
            self.fail('<%s> does not take the attribute%s %s here' % (
                self.el.tag, 's' if len(extra) > 1 else '',
                ', '.join(sorted(extra))))

    def children(self, expected):
        """{tag: [child elements]}, checked against EXPECTED, a dict
        {tag: (min, max)}."""
        found = {tag: [] for tag in expected}
        for child in self.el.children:
            if child.tag not in expected:
                self.fail('<%s> cannot contain <%s>' % (self.el.tag,
                                                        child.tag),
                          child.line)
            found[child.tag].append(child)
        for tag, (lo, hi) in expected.items():
            if not lo <= len(found[tag]) <= hi:
                need = 'exactly %d' % lo if lo == hi else '%d to %d' % (lo, hi)
                self.fail('<%s> must contain %s <%s> element%s' % (
                    self.el.tag, need, tag, '' if hi == 1 else 's'))
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
            if name in ('decl', 'conj'):
                kw['decl'] = self.decl(name)
            elif name == 'kind':
                kw['kind'] = self.enum('kind', KIND_ENUM[pos])
            elif name == 'value':
                kw['value'] = self.integer('value', 0, 1000)
            else:
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


Loaded = List[Tuple[object, int]]


def _read(path: str, root: str, errors: Optional[list],
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
        names = ', '.join('<%s>' % t for t in tags)
        r.fail('this file can only contain %s elements, not <%s>'
               % (names, r.el.tag))


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
                    dictionary='general') -> List[Tuple[Entry, int]]:
    return _read(path, 'dictionary', errors,
                 lambda r, n: _entry(r, n, dictionary))


def entry_from_fields(attrs: dict, stems: List[str], meaning: str,
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


def read_inflections(path: str, errors=None) -> List[Tuple[Inflection, int]]:
    def inflection(r: _Reader, n: int) -> Inflection:
        _expect(r, 'inflection')
        if r.el.children:
            r.fail('<inflection> has no content')
        pos = r.pos(FORM_POS)
        form = r.form(pos)
        key = r.integer('key', 0, 9)
        ending = r.raw('ending', '')
        if ending and not set(ending) <= LETTERS:
            r.fail('ending="%s" may only contain letters' % ending)
        if len(ending) > MAX_ENDING:
            r.fail('ending="%s" is longer than %d letters'
                   % (ending, MAX_ENDING))
        age = r.enum('age', Age, Age.X)
        freq = r.enum('freq', Freq, Freq.X)
        r.done()
        return Inflection(form, key, ending, age, freq)
    return _read(path, 'inflections', errors, inflection)


def read_uniques(path: str, errors=None) -> List[Tuple[Unique, int]]:
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
            r.fail('connect="%s" must be a single character' % connect)
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


def _target(path: str, el: _Element) -> Part:
    r = _Reader(path, el)
    if el.children or el.content.strip():
        r.fail('<%s> has no content' % el.tag)
    part = r.part(r.pos(TARGET_POS))
    r.done()
    return part


# ---------------------------------------------------------------------------
#  Writing

def _value(v) -> str:
    return v.name if hasattr(v, 'name') else str(v)


def part_attrs(part: Part) -> List[Tuple[str, str]]:
    pairs = [('pos', part.pos.name)]
    for name in PART_ATTRS.get(part.pos, ()):
        attr = 'decl' if name == 'conj' else name
        pairs.append((name, _value(getattr(part, attr))))
    return pairs


def form_attrs(form: Form) -> List[Tuple[str, str]]:
    pairs = [('pos', form.pos.name)]
    for name in FORM_ATTRS.get(form.pos, ()):
        attr = 'decl' if name == 'conj' else name
        pairs.append((name, _value(getattr(form, attr))))
    return pairs


def codes_attrs(codes: Codes) -> List[Tuple[str, str]]:
    return [(name, getattr(codes, name).name) for name, _ in CODES]


def _attrs(pairs) -> str:
    return ''.join(' %s=%s' % (n, quoteattr(v)) for n, v in pairs)


HEADERS = {
    'dictionary': 'The WORDS dictionary: one <entry> per dictionary entry. '
                  'See words.xsd.',
    'inflections': 'The inflectional endings used by WORDS. See words.xsd.',
    'uniques': 'Irregular forms that are not built from a stem and an '
               'ending. See words.xsd.',
    'addons': 'Prefixes, suffixes and enclitics (tackons). See words.xsd.',
}


def write_file(path: str, root: str, body: List[str], wrap=False):
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
        f.write('</%s>\n' % root)
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
    return '<!--%s-->' % text


def root_open(tag: str) -> str:
    return ('<%s xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:noNamespaceSchemaLocation="%s">' % (tag, SCHEMA))


def entry_xml(entry: Entry) -> str:
    stems = list(entry.stems)
    while len(stems) > 1 and stems[-1] == '':
        stems.pop()
    body = ''.join('<stem>%s</stem>' % escape(s) if s else '<stem/>'
                   for s in stems)
    return '<entry%s>%s<meaning>%s</meaning></entry>' % (
        _attrs(part_attrs(entry.part) + codes_attrs(entry.codes)), body,
        escape(entry.meaning))


WIDTH = 79             # the longest line of entry attributes, indented


def entry_lines(entry: Entry) -> List[str]:
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
    lines += ['  <stem>%s</stem>' % escape(s) if s else '  <stem/>'
              for s in stems]
    lines += ['  <meaning>%s</meaning>' % escape(entry.meaning), '</entry>']
    return lines


def inflection_xml(infl: Inflection) -> str:
    pairs = form_attrs(infl.form) + [('key', str(infl.key)),
                                     ('ending', infl.ending),
                                     ('age', infl.age.name),
                                     ('freq', infl.freq.name)]
    return '<inflection%s/>' % _attrs(pairs)


def unique_xml(u: Unique) -> str:
    pairs = form_attrs(u.form)
    if u.form.pos in UNIQUE_KIND_ATTRS:
        pairs.append((UNIQUE_KIND_ATTRS[u.form.pos], _value(u.kind)))
    pairs += codes_attrs(u.codes)
    return '<unique%s><form>%s</form><meaning>%s</meaning></unique>' % (
        _attrs(pairs), escape(u.word), escape(u.meaning))


def addon_xml(addon) -> str:
    if isinstance(addon, Tackon):
        return '<tackon fix=%s><base%s/><meaning>%s</meaning></tackon>' % (
            quoteattr(addon.fix), _attrs(part_attrs(addon.base)),
            escape(addon.meaning))
    pairs = [('fix', addon.fix)]
    if addon.connect:
        pairs.append(('connect', addon.connect))
    if isinstance(addon, Prefix):
        pairs += [('root', addon.root.name), ('target', addon.target.name)]
        return '<prefix%s><meaning>%s</meaning></prefix>' % (
            _attrs(pairs), escape(addon.meaning))
    pairs += [('root', addon.root.name), ('rootkey', str(addon.root_key)),
              ('targetkey', str(addon.target_key))]
    return '<suffix%s><target%s/><meaning>%s</meaning></suffix>' % (
        _attrs(pairs), _attrs(part_attrs(addon.target)),
        escape(addon.meaning))
