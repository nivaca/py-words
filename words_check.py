#!/usr/bin/env python3
"""Check the WORDS data files for mistakes.

    python3 words_check.py [FILE ...]

With no FILE, checks the data files in the data directory: dictionary.xml
(and special.xml, if there is one), inflections.xml, uniques.xml,
addons.xml, sources.xml, gloss.xml and the language files in languages/,
and the files of the languages of the interface (data/interface/ next to
the program).  Each problem is reported as FILE:LINE: error|warning:
message.

Errors are elements WORDS cannot read: malformed XML, unknown or missing
codes, stems with characters other than letters, an id used twice, and so
on.  WORDS stops at the first of them.  Warnings are dictionary entries
that load but probably do not do what was meant, such as a declension
with no endings in inflections.xml, a missing stem, or a source code not
listed in sources.xml, and translations of entries that do not exist.

The exit status is 1 if there are errors (or warnings, with --strict).
"""

from version import check_python
check_python()          # (before the modules that need it)

import argparse
import os
import sys

import interface
import languages, lexicon, xmldata
from interface import tr
from settings import ensure_config
from lexicon import default_datadir
from model import Pos, stems_used

MEANING_SHOWN = 80          # a longer meaning is cut in some places

#  The inflection parts of speech that can serve each dictionary part.
INFLECTED_AS = {Pos.N: (Pos.N,), Pos.PRON: (Pos.PRON,),
                Pos.PACK: (Pos.PRON,), Pos.ADJ: (Pos.ADJ,),
                Pos.NUM: (Pos.NUM,), Pos.V: (Pos.V, Pos.VPAR, Pos.SUPINE)}


def inflection_decls(inflections):
    """{part of speech: set of Decl} for a list of Inflection."""
    decls = {}
    for infl in inflections:
        if infl.form.pos in (Pos.N, Pos.PRON, Pos.PACK, Pos.ADJ, Pos.NUM,
                             Pos.V, Pos.VPAR, Pos.SUPINE):
            decls.setdefault(infl.form.pos, set()).add(infl.form.decl)
    return decls


class Checker:
    def __init__(self, decls, sources: set[str] | None = None,
                 ids: dict[str, set[int]] | None = None):
        """DECLS: see inflection_decls; SOURCES: the source codes in
        sources.xml (None: not checked); IDS: the ids of the entries,
        irregular forms and affixes, by what a language file calls them
        (entry, special, unique, addon; None: not checked)."""
        self.decls = decls
        self.sources = sources
        self.ids = ids
        self.errors = 0
        self.warnings = 0
        self.out = []
        self.kinds = []                 # (of the lines of out)

    def report(self, path, line, kind, message):
        """KIND: 'error' or 'warning'."""
        if kind == 'error':
            self.errors += 1
        else:
            self.warnings += 1
        self.out.append(f'{path}:{line}: {tr(kind)}: {message}')
        self.kinds.append(kind)

    def check_file(self, path):
        """Checks PATH according to its root element."""
        errors = []
        try:
            root = xmldata.root_tag(path)
            if root == 'dictionary':
                items = xmldata.read_dictionary(path, errors)
                self.check_dictionary(path, items)
                self.check_ids(path, items)
            elif root == 'inflections':
                xmldata.read_inflections(path, errors)
            elif root == 'uniques':
                self.check_ids(path, xmldata.read_uniques(path, errors))
            elif root == 'addons':
                self.check_ids(path, xmldata.read_addons(path, errors))
            elif root == 'sources':
                xmldata.read_sources(path, errors)
            elif root == 'glosses':
                xmldata.read_glosses(path, errors)
            elif root == 'language':
                self.check_language(path, errors)
            elif root == 'interface':
                try:
                    interface.read(path)
                except interface.InterfaceError as e:
                    errors.append(xmldata.DataError(path, 1, str(e).split(
                        ': ', 1)[-1]))
            else:
                errors.append(xmldata.DataError(
                    path, 1, tr('<{root}> is not a WORDS data file (the '
                                'root must be <dictionary>, <inflections>, '
                                '<uniques>, <addons>, <sources>, <glosses>, '
                                '<language> or <interface>)', root=root)))
        except xmldata.DataError as e:
            errors.append(e)            # the file could not be parsed
        for e in errors:
            self.report(e.path, e.line, 'error', e.message)

    def check_dictionary(self, path, items):
        seen = {}
        for entry, line in items:
            key = (entry.stems, entry.part, entry.codes, entry.meaning)
            if key in seen:
                self.report(path, line, 'warning',
                            tr('duplicate of the entry on line {line}',
                               line=seen[key]))
            else:
                seen[key] = line
            for message in self.entry_warnings(entry):
                self.report(path, line, 'warning', message)

    def check_ids(self, path, items):
        """Each id once in a file (the translations refer to them)."""
        seen = {}
        for record, line in items:
            if record.uid in seen:
                self.report(path, line, 'error',
                            tr('the id {id} is already used on line {line}',
                               id=record.uid, line=seen[record.uid]))
            else:
                seen[record.uid] = line

    def check_language(self, path, errors):
        data = xmldata.read_language(path, errors)
        name = os.path.splitext(os.path.basename(path))[0]
        if name != data.code:
            self.report(path, 1, 'warning',
                        tr('the language {code} should be in {code}.xml, '
                           'not {name}.xml', code=data.code, name=name))
        if data.reference and data.meanings:
            self.report(path, 1, 'warning',
                        tr('the meanings of English are those of the data '
                           'files: these are not used'))
        if self.ids is None:
            return
        lines = _meaning_lines(path)
        for (kind, which) in data.meanings:
            if kind in self.ids and which not in self.ids[kind]:
                self.report(path, lines.get((kind, str(which)), 1),
                            'warning',
                            tr('there is no {kind} with the id {id}: this '
                               'meaning is not used', kind=kind, id=which))

    def entry_warnings(self, entry):
        out = []
        stems, part, meaning = entry.stems, entry.part, entry.meaning
        if meaning.strip() == '':
            out.append(tr('the meaning is empty'))
        elif len(meaning) > MEANING_SHOWN:
            cut = meaning[MEANING_SHOWN - 10:MEANING_SHOWN]
            out.append(tr('the meaning is {n} characters long; it may be '
                          'cut after {shown}: ...{cut}', n=len(meaning),
                          shown=MEANING_SHOWN, cut=repr(cut)))
        used = stems_used(part.pos)
        for k in range(used, 4):
            if stems[k]:
                out.append(tr('stem {k} {stem} is ignored for {pos}',
                              k=k + 1, stem=repr(stems[k]),
                              pos=part.pos.name))
        if not stems[0]:
            out.append(tr('the first stem is blank'))
        for k in range(1, used):
            if not stems[k] and _stem_needed(part, k):
                out.append(tr('stem {k} is blank (use zzz if the form does '
                              'not exist)', k=k + 1))
        if all(st in ('', 'zzz') for st in stems[:max(used, 1)]):
            out.append(tr('no usable stem: no form of this word can be '
                          'found'))
        for source in entry.codes.sources:
            if self.sources is not None and source.name not in self.sources:
                out.append(tr('the source code {code} is not listed in '
                              '{file}', code=source.name,
                              file=lexicon.SOURCES))
        if part.pos in INFLECTED_AS:
            ok = any(part.decl.fits(d)
                     for p in INFLECTED_AS[part.pos]
                     for d in self.decls.get(p, ()))
            if not ok:
                out.append(tr('{pos} {decl} has no endings in {file}, so no '
                              'form of this word can be found',
                              pos=part.pos.name, decl=part.decl,
                              file=lexicon.INFLECTIONS))
        return out


def _stem_needed(part, k):
    """Whether stem K+1 (0-based K) must be filled in for this entry."""
    p = part.pos
    if p in (Pos.N, Pos.PRON, Pos.PACK):
        return part.decl.which != 9          # 9: abbreviation or undeclined
    if p == Pos.V:
        return part.decl.which != 9 and k == 1
    if p == Pos.ADJ:
        return part.comparison.name in ('X', 'POS') and k == 1 and \
            part.decl.which != 9
    return False


def _meaning_lines(path) -> dict[tuple[str, str], int]:
    """The lines of the <meaning>s of a language file, by (kind, id)."""
    out = {}
    with open(path, encoding='utf-8', errors='replace') as f:
        for number, line in enumerate(f, 1):
            for kind in xmldata.TRANSLATED:
                start = line.find(f'<meaning {kind}="')
                if start >= 0:
                    rest = line[start + len(kind) + 11:]
                    out.setdefault((kind, rest.split('"')[0]), number)
    return out


def data_ids(datadir) -> dict[str, set[int]]:
    """The ids of the entries, irregular forms and affixes in DATADIR (see
    Checker)."""
    readers = (('entry', lexicon.DICTIONARY, xmldata.read_dictionary),
               ('special', lexicon.SPECIAL, xmldata.read_dictionary),
               ('unique', lexicon.UNIQUES, xmldata.read_uniques),
               ('addon', lexicon.ADDONS, xmldata.read_addons))
    ids = {}
    for kind, name, read in readers:
        path = os.path.join(datadir, name)
        ids[kind] = {r.uid for r, _ in read(path, [])} \
            if os.path.isfile(path) else set()
    return ids


def data_files(datadir, own: bool = True):
    """The data files in DATADIR, and its language files (and, with OWN,
    the program's files of the languages of the interface)."""
    paths = [os.path.join(datadir, n) for n in lexicon.DATA_FILES]
    folder = os.path.join(datadir, languages.FOLDER)
    if os.path.isdir(folder):
        paths += sorted(os.path.join(folder, n) for n in os.listdir(folder)
                        if n.endswith('.xml'))
    if own:
        paths += interface.files().values()
    return [p for p in paths if os.path.isfile(p)]


def main(argv=None):
    ensure_config()                 # (made at the first start)
    interface.use_configured()
    interface.translate_argparse()
    parser = argparse.ArgumentParser(
        description=tr('Check the WORDS data files for mistakes.'))
    parser.add_argument('files', nargs='*', metavar=tr('FILE'),
                        help=tr('files to check (default: the data files in '
                                'the data directory)'))
    parser.add_argument('--inflections', metavar=tr('FILE'),
                        help=tr('the inflections.xml to check declensions '
                                'against (default: the one in the data '
                                'directory)'))
    parser.add_argument('-q', '--errors-only', action='store_true',
                        help=tr('do not report warnings'))
    parser.add_argument('--strict', action='store_true',
                        help=tr('exit with status 1 on warnings too'))
    args = parser.parse_args(argv)

    datadir = default_datadir()
    files = args.files or data_files(datadir)
    if not files:
        sys.exit(tr('no data files in {folder} (set '
                    'WHITAKERS_WORDS_DATADIR)', folder=datadir))
    inflections = args.inflections or \
        os.path.join(datadir, lexicon.INFLECTIONS)
    if not os.path.isfile(inflections):
        sys.exit(tr('cannot find {path} (use --inflections)',
                    path=inflections))
    try:
        decls = inflection_decls(
            i for i, _ in xmldata.read_inflections(inflections, []))
    except xmldata.DataError as e:
        sys.exit(str(e))
    try:
        sources = set(lexicon.source_names(datadir)) or None
    except xmldata.DataError:
        sources = None                  # (reported when it is checked)
    try:
        ids = data_ids(datadir)
    except xmldata.DataError:
        ids = None                      # (reported when it is checked)
    checker = Checker(decls, sources, ids)
    for path in files:
        if not os.path.isfile(path):
            sys.exit(tr('cannot find {path}', path=path))
        checker.check_file(path)
    for item, kind in zip(checker.out, checker.kinds, strict=True):
        if args.errors_only and kind == 'warning':
            continue
        print(item)
    errors, warnings = checker.errors, checker.warnings
    print((tr('1 error') if errors == 1 else
           tr('{n} errors', n=errors)) + ', ' +
          (tr('1 warning') if warnings == 1 else
           tr('{n} warnings', n=warnings)), file=sys.stderr)
    if checker.errors or (args.strict and checker.warnings):
        sys.exit(1)


if __name__ == '__main__':
    main()
