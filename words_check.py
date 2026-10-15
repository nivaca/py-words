#!/usr/bin/env python3
"""Check the WORDS data files for mistakes.

    python3 words_check.py [FILE ...]

With no FILE, checks the data files in the data directory: dictionary.xml
(and special.xml, if there is one), inflections.xml, uniques.xml and
addons.xml.  Each problem is reported as FILE:LINE: error|warning: message.

Errors are elements WORDS cannot read: malformed XML, unknown or missing
codes, stems with characters other than letters, and so on.  WORDS stops
at the first of them.  Warnings are dictionary entries that load but
probably do not do what was meant, such as a declension with no endings in
inflections.xml, or a missing stem.

The exit status is 1 if there are errors (or warnings, with --strict).
"""

import argparse
import os
import sys

import lexicon, xmldata
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
    def __init__(self, decls):
        self.decls = decls
        self.errors = 0
        self.warnings = 0
        self.out = []

    def report(self, path, line, kind, message):
        if kind == 'error':
            self.errors += 1
        else:
            self.warnings += 1
        self.out.append('%s:%s: %s: %s' % (path, line, kind, message))

    def check_file(self, path):
        """Checks PATH according to its root element."""
        errors = []
        try:
            root = xmldata.root_tag(path)
            if root == 'dictionary':
                self.check_dictionary(
                    path, xmldata.read_dictionary(path, errors))
            elif root == 'inflections':
                xmldata.read_inflections(path, errors)
            elif root == 'uniques':
                xmldata.read_uniques(path, errors)
            elif root == 'addons':
                xmldata.read_addons(path, errors)
            else:
                errors.append(xmldata.DataError(
                    path, 1, '<%s> is not a WORDS data file (the root must '
                    'be <dictionary>, <inflections>, <uniques> or <addons>)'
                    % root))
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
                            'duplicate of the entry on line %d' % seen[key])
            else:
                seen[key] = line
            for message in self.entry_warnings(entry):
                self.report(path, line, 'warning', message)

    def entry_warnings(self, entry):
        out = []
        stems, part, meaning = entry.stems, entry.part, entry.meaning
        if meaning.strip() == '':
            out.append('the meaning is empty')
        elif len(meaning) > MEANING_SHOWN:
            out.append('the meaning is %d characters long; it may be cut '
                       'after %d: ...%r' % (len(meaning), MEANING_SHOWN,
                                            meaning[MEANING_SHOWN - 10:
                                                    MEANING_SHOWN]))
        used = stems_used(part.pos)
        for k in range(used, 4):
            if stems[k]:
                out.append('stem %d %r is ignored for %s' % (
                    k + 1, stems[k], part.pos.name))
        if not stems[0]:
            out.append('the first stem is blank')
        for k in range(1, used):
            if not stems[k] and _stem_needed(part, k):
                out.append('stem %d is blank (use zzz if the form does not '
                           'exist)' % (k + 1))
        if all(st in ('', 'zzz') for st in stems[:max(used, 1)]):
            out.append('no usable stem: no form of this word can be found')
        if part.pos in INFLECTED_AS:
            ok = any(part.decl.fits(d)
                     for p in INFLECTED_AS[part.pos]
                     for d in self.decls.get(p, ()))
            if not ok:
                out.append('%s %s has no endings in %s, so no form of this '
                           'word can be found' % (
                               part.pos.name, part.decl,
                               lexicon.INFLECTIONS))
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


def data_files(datadir):
    """The data files in DATADIR."""
    paths = [os.path.join(datadir, n) for n in lexicon.DATA_FILES]
    return [p for p in paths if os.path.isfile(p)]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Check the WORDS data files for mistakes.')
    parser.add_argument('files', nargs='*', metavar='FILE',
                        help='files to check (default: the data files in the '
                             'data directory)')
    parser.add_argument('--inflections', metavar='FILE',
                        help='the inflections.xml to check declensions '
                             'against (default: the one in the data '
                             'directory)')
    parser.add_argument('-q', '--errors-only', action='store_true',
                        help='do not report warnings')
    parser.add_argument('--strict', action='store_true',
                        help='exit with status 1 on warnings too')
    args = parser.parse_args(argv)

    datadir = default_datadir()
    files = args.files or data_files(datadir)
    if not files:
        sys.exit('no data files in %s (set WHITAKERS_WORDS_DATADIR)'
                 % datadir)
    inflections = args.inflections or \
        os.path.join(datadir, lexicon.INFLECTIONS)
    if not os.path.isfile(inflections):
        sys.exit('cannot find %s (use --inflections)' % inflections)
    try:
        decls = inflection_decls(
            i for i, _ in xmldata.read_inflections(inflections, []))
    except xmldata.DataError as e:
        sys.exit(str(e))
    checker = Checker(decls)
    for path in files:
        if not os.path.isfile(path):
            sys.exit('cannot find %s' % path)
        checker.check_file(path)
    for item in checker.out:
        if args.errors_only and ': warning: ' in item:
            continue
        print(item)
    print('%d error%s, %d warning%s' % (
        checker.errors, '' if checker.errors == 1 else 's',
        checker.warnings, '' if checker.warnings == 1 else 's'),
        file=sys.stderr)
    if checker.errors or (args.strict and checker.warnings):
        sys.exit(1)


if __name__ == '__main__':
    main()
