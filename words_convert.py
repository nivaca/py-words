#!/usr/bin/env python3
"""Convert data files in the original WORDS text format to XML.

    python3 words_convert.py SRC [DEST]

reads DICTLINE.GEN, INFLECTS.LAT, UNIQUES.LAT and ADDONS.LAT (and
DICTLINE.SPE, if there is one) from SRC and writes dictionary.xml,
inflections.xml, uniques.xml and addons.xml (and special.xml) to DEST (by
default SRC).  The comments of INFLECTS.LAT and ADDONS.LAT are kept as XML
comments.  This brings in data from other versions of WORDS.

The original files are read as the original program read them, including
a quirk: in ADDONS.LAT a short line after a comment can pick up the end of
the comment.  A tackon that this makes unusable is written as a comment.
"""

import argparse
import os
import sys
from collections.abc import Iterator

import xmldata
from model import (Pos, Gender, Case, Number, Comparison, NumeralSort,
                    Tense, Voice, Mood, NounKind, PronounKind, VerbKind, Age,
                    Freq, Area, Geo, Source, Decl, Codes, Part, Form,
                    Inflection, Entry, Unique, Prefix, Suffix, Tackon)

#  Columns of DICTLINE.GEN: four stems of 18 letters, then the rest
STEM_STARTS = (0, 19, 38, 57)
STEM_WIDTH = 18
PART_START = 76


class ConvertError(Exception):
    pass


class Tokens:
    """The whitespace-separated words of a line, read one at a time."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def next(self) -> str:
        text = self.text
        while self.pos < len(text) and text[self.pos] in ' \t':
            self.pos += 1
        start = self.pos
        while self.pos < len(text) and text[self.pos] not in ' \t':
            self.pos += 1
        if start == self.pos:
            raise ConvertError('the line ends too early')
        return text[start:self.pos]

    def rest(self) -> str:
        """The text after the next separating space."""
        return self.text[self.pos + 1:]

    def enum(self, cls):
        word = self.next()
        try:
            return cls[word.upper()]
        except KeyError:
            raise ConvertError('%r is not a %s' % (word, cls.__name__))

    def number(self, lo=0, hi=9) -> int:
        word = self.next()
        if not word.isdigit() or not lo <= int(word) <= hi:
            raise ConvertError('%r is not a number from %d to %d'
                               % (word, lo, hi))
        return int(word)

    def decl(self) -> Decl:
        return Decl(self.number(), self.number())


KIND = {Pos.N: NounKind, Pos.PRON: PronounKind, Pos.PACK: PronounKind,
        Pos.V: VerbKind, Pos.VPAR: VerbKind, Pos.SUPINE: VerbKind}


def read_part(t: Tokens, pos: Pos | None = None) -> Part:
    pos = pos if pos is not None else t.enum(Pos)
    if pos == Pos.N:
        return Part(pos, t.decl(), t.enum(Gender), t.enum(NounKind))
    if pos in (Pos.PRON, Pos.PACK):
        return Part(pos, t.decl(), kind=t.enum(PronounKind))
    if pos == Pos.ADJ:
        return Part(pos, t.decl(), comparison=t.enum(Comparison))
    if pos == Pos.NUM:
        return Part(pos, t.decl(), sort=t.enum(NumeralSort),
                    value=t.number(0, 1000))
    if pos == Pos.ADV:
        return Part(pos, comparison=t.enum(Comparison))
    if pos == Pos.V:
        return Part(pos, t.decl(), kind=t.enum(VerbKind))
    if pos == Pos.PREP:
        return Part(pos, case=t.enum(Case))
    if pos in (Pos.VPAR, Pos.SUPINE):
        raise ConvertError('%s is not a dictionary part of speech'
                           % pos.name)
    return Part(pos)


def read_form(t: Tokens) -> Form:
    pos = t.enum(Pos)
    if pos in (Pos.N, Pos.PRON, Pos.PACK, Pos.SUPINE, Pos.ADJ, Pos.NUM,
               Pos.VPAR):
        decl, case, number, gender = (t.decl(), t.enum(Case),
                                      t.enum(Number), t.enum(Gender))
        if pos == Pos.ADJ:
            return Form(pos, decl, case, number, gender,
                        comparison=t.enum(Comparison))
        if pos == Pos.NUM:
            return Form(pos, decl, case, number, gender,
                        sort=t.enum(NumeralSort))
        if pos == Pos.VPAR:
            return Form(pos, decl, case, number, gender, tense=t.enum(Tense),
                        voice=t.enum(Voice), mood=t.enum(Mood))
        return Form(pos, decl, case, number, gender)
    if pos == Pos.ADV:
        return Form(pos, comparison=t.enum(Comparison))
    if pos == Pos.V:
        decl = t.decl()
        tense, voice, mood = t.enum(Tense), t.enum(Voice), t.enum(Mood)
        return Form(pos, decl, tense=tense, voice=voice, mood=mood,
                    person=t.number(0, 3), number=t.enum(Number))
    if pos == Pos.PREP:
        return Form(pos, case=t.enum(Case))
    return Form(pos)


def read_codes(t: Tokens) -> Codes:
    return Codes(t.enum(Age), t.enum(Area), t.enum(Geo), t.enum(Freq),
                 t.enum(Source))


def read_lines(path: str) -> list[str]:
    """The lines of a file, without line endings (LF or CR LF)."""
    with open(path, encoding='latin-1', newline='') as f:
        return [line.rstrip('\r\n') for line in f]


def _fail(path, number, message, line):
    raise ConvertError('%s:%d: %s\n    %s' % (path, number, message, line))


def _split_comment(line: str) -> tuple[str, str | None]:
    content, sep, comment = line.partition('--')
    return content, (comment if sep else None)


def _comment_line(line: str) -> str:
    indent = line[:len(line) - len(line.lstrip(' \t'))]
    return indent + xmldata.comment(_split_comment(line)[1].rstrip())


def _is_comment(line: str) -> bool:
    return line.lstrip(' \t').startswith('--')


# ---------------------------------------------------------------------------

def convert_dictline(path: str, dictionary='general') -> list[Entry]:
    entries = []
    for number, line in enumerate(read_lines(path), 1):
        if not line.strip():
            continue
        stems = []
        for start in STEM_STARTS:
            field = line[start:start + STEM_WIDTH]
            stem = field.strip()
            if field.rstrip() != stem or ' ' in stem or \
                    line[start + STEM_WIDTH:start + STEM_WIDTH + 1].strip():
                _fail(path, number, 'a stem is out of its columns', line)
            stems.append(stem)
        t = Tokens(line[PART_START:])
        try:
            part = read_part(t)
            codes = read_codes(t)
        except ConvertError as e:
            _fail(path, number, str(e), line)
        entries.append(Entry(len(entries) + 1, tuple(stems), part, codes,
                             t.rest(), dictionary))
    return entries


def convert_inflects(path: str) -> list[str]:
    body = []
    for number, line in enumerate(read_lines(path), 1):
        if not line.replace('\t', ' ').strip():
            body.append('')
            continue
        if _is_comment(line):
            body.append(_comment_line(line))
            continue
        content, note = _split_comment(line)
        t = Tokens(content)
        try:
            form = read_form(t)
            key = t.number()
            size = t.number(0, 7)
            ending = t.next() if size else ''
            if len(ending) != size:
                raise ConvertError('the ending %r is not %d letters long'
                                   % (ending, size))
            infl = Inflection(form, key, ending, t.enum(Age), t.enum(Freq))
        except ConvertError as e:
            _fail(path, number, str(e), line)
        text = xmldata.inflection_xml(infl)
        if note is not None and note.strip():
            text += ' ' + xmldata.comment(note.rstrip())
        body.append(text)
    return body


def convert_uniques(path: str) -> list[Unique]:
    lines = read_lines(path)
    if len(lines) % 3:
        raise ConvertError('%s: the number of lines is not a multiple of 3'
                           % path)
    out = []
    for i in range(0, len(lines), 3):
        word, line, meaning = lines[i:i + 3]
        t = Tokens(line)
        try:
            form = read_form(t)
            if form.pos == Pos.NUM:
                kind = t.number(0, 1000)
            elif form.pos in KIND:
                kind = t.enum(KIND[form.pos])
            else:
                kind = None
            codes = read_codes(t)
        except ConvertError as e:
            _fail(path, i + 2, str(e), line)
        out.append(Unique(len(out) + 1, word.strip(), form, kind, codes,
                          meaning.strip()))
    return out


def convert_addons(path: str) -> list[str]:
    lines = read_lines(path)
    body = []
    #  The header of an entry is read into a buffer that still holds the
    #  comment lines just before it: it ends at the first "--" in the line
    #  laid over them, or, if there is none, at the end of the line.
    stale = ''
    number = 0
    pos = 0
    while pos < len(lines):
        line = lines[pos]
        if not line.strip():
            body.append('')
            pos += 1
            continue
        if _is_comment(line):
            body.append(_comment_line(line))
            stale = line[:250] + stale[len(line):]
            pos += 1
            continue
        if pos + 2 >= len(lines):
            _fail(path, pos + 1, 'the entry is incomplete', line)
        _, note = _split_comment(line)
        header = line[:250] + stale[len(line):]
        header = header[:header.index('--')] if '--' in header else line
        stale = ''
        entry, meaning = lines[pos + 1], lines[pos + 2]
        number += 1
        t = Tokens(header)
        try:
            kind = t.enum(Pos)
            rest = header[t.pos:].split()
            e = Tokens(entry)
            if kind == Pos.TACKON:
                base = e.enum(Pos)
                base = Part(Pos.X) if base == Pos.X else read_part(e, base)
                addon = Tackon(number, rest[0] if rest else '', base,
                               meaning)
                if len(rest) != 1:
                    body.append(xmldata.comment(
                        ' Not used by WORDS: in ADDONS.LAT this tackon was '
                        'read as "%s", with text from the comment before '
                        'it, and never matched. ' % header[t.pos:].strip()))
                    body.append(xmldata.comment(
                        ' ' + xmldata.addon_xml(addon) + ' '))
                    pos += 3
                    continue
            elif kind in (Pos.PREFIX, Pos.SUFFIX):
                fix = rest[0] if rest else ''
                letter = rest[1][0] if len(rest) > 1 else ''
                if kind == Pos.PREFIX:
                    addon = Prefix(number, fix, letter, e.enum(Pos),
                                   e.enum(Pos), meaning)
                else:
                    root, root_key = e.enum(Pos), e.number()
                    target = e.enum(Pos)
                    target = Part(Pos.X) if target == Pos.X else \
                        read_part(e, target)
                    addon = Suffix(number, fix, letter, root, root_key,
                                   target, e.number(), meaning)
            else:
                raise ConvertError('expected PREFIX, SUFFIX or TACKON')
        except ConvertError as err:
            _fail(path, pos + 1, str(err), line + '\n    ' + entry)
        text = xmldata.addon_xml(addon)
        if note is not None and note.strip():
            text += ' ' + xmldata.comment(note.rstrip())
        body.append(text)
        pos += 3
    return body


# ---------------------------------------------------------------------------

write_xml = xmldata.write_file


def convert(src: str, dest: str) -> Iterator[str]:
    """Converts the files; yields the names of those written."""
    def path(name):
        return os.path.join(src, name)
    for name, out in (('DICTLINE.GEN', 'dictionary.xml'),
                      ('DICTLINE.SPE', 'special.xml')):
        if os.path.isfile(path(name)):
            xmldata.write_dictionary(os.path.join(dest, out),
                                     convert_dictline(path(name)))
            yield out
    write_xml(os.path.join(dest, 'inflections.xml'), 'inflections',
              convert_inflects(path('INFLECTS.LAT')))
    yield 'inflections.xml'
    write_xml(os.path.join(dest, 'uniques.xml'), 'uniques',
              [xmldata.unique_xml(u)
               for u in convert_uniques(path('UNIQUES.LAT'))])
    yield 'uniques.xml'
    write_xml(os.path.join(dest, 'addons.xml'), 'addons',
              convert_addons(path('ADDONS.LAT')))
    yield 'addons.xml'


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Convert WORDS data files in the original text format '
                    '(DICTLINE.GEN, INFLECTS.LAT, UNIQUES.LAT, ADDONS.LAT) '
                    'to XML.')
    parser.add_argument('src', help='the folder with the original files')
    parser.add_argument('dest', nargs='?',
                        help='the folder for the XML files (default: SRC)')
    args = parser.parse_args(argv)
    try:
        for name in convert(args.src, args.dest or args.src):
            print('wrote', os.path.join(args.dest or args.src, name))
    except (ConvertError, OSError) as e:
        sys.exit(str(e))


if __name__ == '__main__':
    main()
