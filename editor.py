"""Editing the dictionary: what the terminal and window editors share.

An `Editor` holds the entries of dictionary.xml in the data directory.  It
finds entries (by a Latin form, a stem, or a word of their meanings),
builds new or corrected ones from the values of their fields (checked as
the data files are checked), describes them as WORDS will show them, lets
a word be tried against the edited dictionary, and saves the file (keeping
a backup of the original as dictionary.xml.bak).  `Editing` is what the
two editors do with it: the entry in the form, applying changes, and
asking before they are lost.

The meanings are edited in English and, if a language of the meanings is
chosen (set_language), in that language too: its translations are written
to its file in languages/ when the dictionary is saved (keeping a backup
there too).  Deleting an entry takes its translations out of every
language file.

The labels and descriptions of the tables below are English; they are
translated (interface.tr) where they are shown.
"""

from __future__ import annotations

import os
import re
import shutil
from collections import Counter
from dataclasses import replace

import languages
import xmldata
from languages import Language, REFERENCE
from words_check import Checker, inflection_decls
from forms import principal_parts, describe_part
from interface import tr
from lexicon import Lexicon, DICTIONARY, INFLECTIONS, source_names
from model import (Pos, Gender, Case, Comparison, NumeralSort, NounKind,
                    PronounKind, VerbKind, Age, Area, Geo, Freq, Source,
                    Entry, fold, stems_used)
from session import Session
from settings import Settings

#  The parts of speech of dictionary entries, with their names
POS_CHOICES = [
    ('N', 'noun'), ('V', 'verb'), ('ADJ', 'adjective'), ('ADV', 'adverb'),
    ('PREP', 'preposition'), ('CONJ', 'conjunction'),
    ('INTERJ', 'interjection'), ('PRON', 'pronoun'),
    ('PACK', 'pronoun with an enclitic (quicumque)'), ('NUM', 'numeral')]

STEM_LABELS = {
    Pos.N: ('nominative stem', 'genitive stem'),
    Pos.PRON: ('stem 1', 'stem 2'),
    Pos.PACK: ('stem 1', 'stem 2'),
    Pos.ADJ: ('positive stem', 'oblique stem', 'comparative stem',
              'superlative stem'),
    Pos.NUM: ('cardinal stem', 'ordinal stem', 'distributive stem',
              'numeral adverb stem'),
    Pos.ADV: ('positive', 'comparative', 'superlative'),
    Pos.V: ('present stem', 'infinitive stem', 'perfect stem',
            'participle stem'),
}

FIELD_LABELS = {
    'decl': 'declension', 'conj': 'conjugation', 'gender': 'gender',
    'kind': 'kind', 'comparison': 'degree', 'sort': 'sort',
    'value': 'value', 'case': 'takes the case', 'age': 'age',
    'area': 'area', 'geo': 'region', 'freq': 'frequency',
    'source': 'source'}

CODE_FIELDS = ('age', 'area', 'geo', 'freq', 'source')

#  What the codes mean (those of the sources are in sources.xml)
DESCRIPTIONS: dict[str, dict[str, str]] = {
    'gender': {'M': 'masculine', 'F': 'feminine', 'N': 'neuter',
               'C': 'common (masculine or feminine)', 'X': 'unknown'},
    'case': {'NOM': 'nominative', 'GEN': 'genitive', 'DAT': 'dative',
             'ACC': 'accusative', 'ABL': 'ablative', 'VOC': 'vocative',
             'LOC': 'locative', 'X': 'unknown'},
    'comparison': {'X': 'all degrees (positive, comparative, superlative)',
                   'POS': 'positive only', 'COMP': 'comparative only',
                   'SUPER': 'superlative only'},
    'sort': {'X': 'all sorts (cardinal, ordinal ...)', 'CARD': 'cardinal',
             'ORD': 'ordinal', 'DIST': 'distributive',
             'ADVERB': 'numeral adverb'},
    'kind N': {'X': 'unknown', 'S': 'singular only', 'M': 'plural only',
               'A': 'abstract idea', 'G': 'group, collective',
               'N': 'proper name', 'P': 'a person', 'T': 'a thing',
               'L': 'a place', 'W': 'where (a place name)'},
    'kind PRON': {'X': 'unknown', 'PERS': 'personal', 'REL': 'relative',
                  'REFLEX': 'reflexive', 'DEMONS': 'demonstrative',
                  'INTERR': 'interrogative', 'INDEF': 'indefinite',
                  'ADJECT': 'adjectival'},
    'kind V': {'X': 'unknown', 'TRANS': 'transitive',
               'INTRANS': 'intransitive', 'DEP': 'deponent',
               'SEMIDEP': 'semi-deponent', 'IMPERS': 'impersonal',
               'PERFDEF': 'perfect with present meaning',
               'GEN': 'takes the genitive', 'DAT': 'takes the dative',
               'ABL': 'takes the ablative', 'TO_BE': 'the verb "to be"',
               'TO_BEING': 'compound of "to be"'},
    'age': {'X': 'in use throughout', 'A': 'archaic', 'B': 'early (before '
            'the classical period)', 'C': 'classical', 'D': 'late (after '
            '200)', 'E': 'later (after 600)', 'F': 'medieval (after 1000)',
            'G': 'scholarly (Renaissance and after)', 'H': 'modern'},
    'area': {'X': 'general', 'A': 'agriculture, plants, animals, the land',
             'B': 'biology, medicine, the body',
             'D': 'drama, music, the arts', 'E': 'the Church, the Bible',
             'G': 'grammar, rhetoric, logic, literature, school',
             'L': 'law, government, money, titles', 'P': 'poetry',
             'S': 'science, philosophy, mathematics, measures',
             'T': 'technical, architecture, surveying',
             'W': 'war, the army, the navy', 'Y': 'mythology'},
    'geo': {'X': 'everywhere', 'A': 'Africa', 'B': 'Britain', 'C': 'China',
            'D': 'Scandinavia', 'E': 'Egypt', 'F': 'France, Gaul',
            'G': 'Germany', 'H': 'Greece', 'I': 'Italy, Rome',
            'J': 'India', 'K': 'the Balkans', 'N': 'the Netherlands',
            'P': 'Persia', 'Q': 'the Near East', 'R': 'Russia',
            'S': 'Spain', 'U': 'Eastern Europe'},
    'freq': {'X': 'unknown', 'A': 'very frequent', 'B': 'frequent',
             'C': 'common', 'D': 'lesser', 'E': 'uncommon',
             'F': 'very rare', 'I': 'only in inscriptions',
             'M': 'only in graffiti', 'N': 'only in Pliny'},
}

ENUMS = {'gender': Gender, 'case': Case, 'comparison': Comparison,
         'sort': NumeralSort, 'age': Age, 'area': Area, 'geo': Geo,
         'freq': Freq, 'source': Source}
KINDS = {Pos.N: NounKind, Pos.PRON: PronounKind, Pos.PACK: PronounKind,
         Pos.V: VerbKind}


class Fields:
    """The editable values of an entry, as text."""

    def __init__(self, pos='N', attrs=None, stems=('', '', '', ''),
                 meaning='', translation=None):
        self.pos = pos
        self.attrs: dict[str, str] = dict(attrs or {})
        self.stems = list(stems) + [''] * (4 - len(stems))
        self.meaning = meaning
        #  the meaning in the editor's language ('': none; None: the editor
        #  is in English)
        self.translation: str | None = translation

    @classmethod
    def of(cls, entry: Entry, translation: str | None = None) -> Fields:
        attrs = dict(xmldata.part_attrs(entry.part) +
                     xmldata.codes_attrs(entry.codes))
        pos = attrs.pop('pos')
        return cls(pos, attrs, entry.stems, entry.meaning, translation)

    def names(self) -> list[str]:
        """The attributes this part of speech uses, then the codes."""
        return list(xmldata.PART_ATTRS.get(Pos[self.pos], ())) + \
            list(CODE_FIELDS)

    def stem_labels(self) -> tuple[str, ...]:
        """The labels of the stems of this part of speech (in English:
        the editors translate them)."""
        pos = Pos[self.pos]
        return STEM_LABELS.get(pos, ('word',))[:max(stems_used(pos), 1)]

    def set_pos(self, pos: str):
        """Changes the part of speech, keeping the values that still
        apply."""
        self.pos = pos
        keep = set(self.names())
        self.attrs = {k: v for k, v in self.attrs.items() if k in keep}

    def snapshot(self) -> tuple:
        """The values that make the entry, to tell whether a form was
        changed."""
        return (self.pos, tuple(self.attrs.get(n, '') for n in self.names()),
                tuple(self.stems[:len(self.stem_labels())]), self.meaning,
                self.translation)

    def entry(self, id: int = 0) -> Entry:
        """The entry (raises xmldata.DataError if a value is wrong)."""
        attrs = {'pos': self.pos}
        attrs.update({k: v for k, v in self.attrs.items()
                      if k in self.names()})
        n = len(self.stem_labels())
        try:
            return xmldata.entry_from_fields(attrs, self.stems[:n],
                                             self.meaning.strip(), id)
        except xmldata.DataError as e:
            raise xmldata.DataError(e.path, e.line, plain_message(e)) \
                from None


def plain_message(error: xmldata.DataError | str) -> str:
    """A message about a field in the editors' words (declension, not
    decl), in the language of the interface.  ERROR: the DataError, or
    the English message of one."""
    def label(name):
        return tr(FIELD_LABELS.get(name, name))
    field = value = problem = None
    if isinstance(error, xmldata.DataError):
        field, value, problem = error.field, error.value, error.problem
        message = error.message
    else:
        message = error
        m = re.match(r'<\w+> needs a (\w+) attribute', message)
        if m:
            field = m.group(1)
        m = re.match(r'(\w+)="(.*?)" (.*)', message)
        if m:
            field, value, problem = m.group(1), m.group(2), tr(m.group(3))
    if field is not None and problem is None:
        return tr('the {field} is missing', field=label(field))
    if field is not None:
        return tr('the {field} "{value}" {problem}', field=label(field),
                  value=value, problem=problem)
    return message


class Editor:
    def __init__(self, datadir: str, language: str = REFERENCE):
        """LANGUAGE: the language of the meanings edited besides English
        (one that is not there is taken to be English)."""
        self.datadir = datadir
        self.path = os.path.join(datadir, DICTIONARY)
        self.base = Lexicon.load(datadir)
        self.entries: list[Entry] = self.base.entries[:-1]     # (not esse)
        #  the descriptions of the codes; the sources come from sources.xml
        self.descriptions = dict(DESCRIPTIONS)
        self.descriptions['source'] = source_names(datadir)
        self.checker = Checker(inflection_decls(
            i for i, _ in xmldata.read_inflections(
                os.path.join(datadir, INFLECTIONS))),
            set(self.descriptions['source']) or None)
        self.dirty = False
        self._backed_up = False
        self._trial: Lexicon | None = None
        self._decl_examples: dict[tuple[str, str], str] = {}
        #  the languages of the meanings: {code: name}
        self.language_names = languages.names(datadir)
        self.language = REFERENCE
        #  the meanings of the entries in the languages chosen, by code and
        #  uid, as edited; the uids whose meaning changed, by code; the
        #  uids of the entries deleted
        self._translations: dict[str, dict[int, str]] = {}
        self._retranslated: dict[str, set[int]] = {}
        self._deleted: set[int] = set()
        self._languages_backed_up: set[str] = set()
        if language in self.language_names:
            self.set_language(language)

    # The language of the meanings --------------------------------------------

    def set_language(self, code: str):
        """Edits the meanings in CODE besides English (REFERENCE: in English
        only).  Raises LookupError if there is no such language,
        xmldata.DataError if its file is wrong."""
        if code != REFERENCE and code not in self._translations:
            path = languages.files(self.datadir).get(code)
            if path is None:
                raise LookupError(tr('there is no language {code}',
                                     code=code))
            data = xmldata.read_language(path)
            self._translations[code] = {
                which: text for (kind, which), text in data.meanings.items()
                if kind == 'entry'}
        self.language = code
        self._trial = None

    @property
    def translating(self) -> bool:
        """Whether the meanings are edited in a language besides
        English."""
        return self.language != REFERENCE

    @property
    def language_name(self) -> str:
        return self.language_names.get(self.language, self.language)

    def translation(self, entry: Entry | None) -> str | None:
        """ENTRY's meaning in the language chosen ('' if it has none; None
        if the language is English)."""
        if not self.translating:
            return None
        if entry is None:
            return ''
        return self._translations[self.language].get(entry.uid, '')

    def fields(self, entry: Entry) -> Fields:
        """The values of ENTRY, with its meaning in the language chosen."""
        return Fields.of(entry, self.translation(entry))

    def set_translation(self, entry: Entry, text: str):
        """Sets ENTRY's meaning in the language chosen ('': none, and the
        English one is shown)."""
        table = self._translations[self.language]
        text = text.strip()
        if text == table.get(entry.uid, ''):
            return
        if text:
            table[entry.uid] = text
        else:
            table.pop(entry.uid, None)
        self._retranslated.setdefault(self.language, set()).add(entry.uid)
        self._changed()

    # Choices ---------------------------------------------------------------

    def options(self, name: str, pos: str) -> list[tuple[str, str]]:
        """The (value, description) choices for a field, or [] for free
        text (value).  The descriptions are in the language of the
        interface (but the names of the sources are as they are)."""
        if name in ('decl', 'conj'):
            return self._declensions(pos)
        if name == 'kind':
            descriptions = self.descriptions['kind ' + (
                'PRON' if pos == 'PACK' else pos)]
            return [(k.name, tr(descriptions.get(k.name, '')))
                    for k in KINDS[Pos[pos]]]
        if name in ENUMS:
            descriptions = self.descriptions.get(name, {})
            show = (lambda d: d) if name == 'source' else tr
            return [(m.name, show(descriptions.get(m.name, '')))
                    for m in ENUMS[name]]
        return []

    def _declensions(self, pos: str) -> list[tuple[str, str]]:
        """The declensions (or conjugations) entries of this part of speech
        have, each with an example."""
        counts = Counter(str(e.part.decl) for e in self.entries
                         if e.part.pos.name == pos)
        out = []
        for decl, _ in sorted(counts.items()):
            key = (pos, decl)
            if key not in self._decl_examples:
                examples = [e for e in self.entries
                            if e.part.pos.name == pos and
                            str(e.part.decl) == decl]
                best = min(examples, key=lambda e: (e.codes.freq or 9,
                                                    e.id))
                self._decl_examples[key] = principal_parts(best) or \
                    best.stems[0]
            out.append((decl, tr('like {word}',
                                 word=self._decl_examples[key])))
        return out

    # Finding ---------------------------------------------------------------

    def search(self, query: str, limit: int = 200) -> list[Entry]:
        """Entries for QUERY: those it is a form of, those with a stem
        that begins with it, then those whose meaning (in English or in the
        language chosen) has it."""
        query = query.strip()
        if not query:
            return []
        trial = self.trial()
        by_id = {i + 1: e for i, e in enumerate(self.entries)}
        found: list[Entry] = []
        seen = set()

        def add(entry):
            if entry is not None and id(entry) not in seen:
                seen.add(id(entry))
                found.append(entry)
        word = query.split()[0]
        if word.isalpha():
            az = Session(trial, Settings()).analyzer
            result, _ = az.analyze_word(word)
            for reading in result.readings:
                for p in reading.forms:
                    if p.entry is not None and \
                            p.entry.dictionary == 'general':
                        add(by_id.get(p.entry.id))
            key = fold(word)
            exact = [e for e in self.entries
                     if any(fold(s) == key for s in e.stems)]
            prefix = [e for e in self.entries
                      if any(fold(s).startswith(key) for s in e.stems if s)]
            for e in exact + prefix:
                add(e)
            for code in dict.fromkeys((self.language, REFERENCE)):
                for hit in trial.reverse(code).search(word):
                    add(by_id.get(hit.entry.id))
        text = query.lower()
        for e in self.entries:
            if len(found) >= limit:
                break
            if text in e.meaning.lower() or \
                    text in (self.translation(e) or '').lower():
                add(e)
        return found[:limit]

    # Changing --------------------------------------------------------------

    def add(self, entry: Entry, after: Entry | None = None) -> Entry:
        """Adds ENTRY after AFTER, or where its first stem goes in the
        alphabetical order of the dictionary.  It gets a new id (which no
        entry has had, as far as this file tells)."""
        #  Nunca reutilizar un id: las traducciones (languages/*.xml)
        #  apuntan a él, y una entrada nueva heredaría las de otra.
        entry = replace(entry, uid=max(
            [e.uid for e in self.entries] + list(self._deleted),
            default=0) + 1)
        if after is not None and any(e is after for e in self.entries):
            i = self._index(after) + 1
        else:
            key = fold(entry.stems[0])
            i = next((k for k, e in enumerate(self.entries)
                      if fold(e.stems[0]) > key), len(self.entries))
        self.entries.insert(i, entry)
        self._changed()
        return entry

    def replace(self, old: Entry, new: Entry) -> Entry:
        """Puts NEW in the place of OLD (it keeps OLD's id, which the
        translations of its meaning refer to)."""
        new = replace(new, uid=old.uid)
        self.entries[self._index(old)] = new
        self._changed()
        return new

    def delete(self, entry: Entry):
        """Takes ENTRY out (and, when saved, its translations)."""
        del self.entries[self._index(entry)]
        self._deleted.add(entry.uid)
        for table in self._translations.values():
            table.pop(entry.uid, None)
        self._changed()

    def _index(self, entry: Entry) -> int:
        for i, e in enumerate(self.entries):
            if e is entry:
                return i
        raise ValueError(tr('the entry is not in the dictionary'))

    def _changed(self):
        self.dirty = True
        self._trial = None

    def numbered(self) -> list[Entry]:
        """The entries, numbered by their position (as when read)."""
        return [e if e.id == i else replace(e, id=i)
                for i, e in enumerate(self.entries, 1)]

    def save(self):
        """Writes dictionary.xml, and the language files whose meanings
        changed (the first time, keeping the originals as .bak files)."""
        if not self._backed_up and os.path.exists(self.path):
            shutil.copy2(self.path, self.path + '.bak')
            self._backed_up = True
        # (the entries themselves are kept: the editors hold on to them)
        xmldata.write_dictionary(self.path, self.numbered())
        self._save_languages()
        self.dirty = False
        self._trial = None

    def _save_languages(self):
        """Writes the meanings changed, and takes out those of the entries
        deleted, in the language files."""
        names = {e.uid: self.name(e) for e in self.entries}
        for code, path in languages.files(self.datadir).items():
            if code == REFERENCE or \
                    os.path.dirname(path) != os.path.join(
                        self.datadir, languages.FOLDER):
                continue
            changes = {('entry', uid): None for uid in self._deleted}
            for uid in self._retranslated.get(code, ()):
                if uid in names:
                    changes['entry', uid] = \
                        self._translations[code].get(uid) or None
            if not changes:
                continue
            if code not in self._languages_backed_up:
                shutil.copy2(path, path + '.bak')
                self._languages_backed_up.add(code)
            xmldata.update_language(path, changes, {
                key: names[key[1]] for key in changes if key[1] in names})
        self._retranslated = {}
        self._deleted = set()

    # Describing and trying out ----------------------------------------------

    def describe(self, entry: Entry) -> str:
        """How WORDS shows the entry: its principal parts and grammar (in
        the language chosen)."""
        tr = self.base.language(self.language).text
        parts = principal_parts(entry, tr) or entry.stems[0]
        return f'{parts}  {describe_part(entry.part, tr)}'

    @staticmethod
    def name(entry: Entry) -> str:
        """The entry's dictionary form: "amicus, amici"."""
        return principal_parts(entry) or entry.stems[0]

    def warnings(self, entry: Entry,
                 translation: str | None = None) -> list[str]:
        """What is odd about ENTRY (and its meaning TRANSLATION in the
        language chosen, if given)."""
        out = self.checker.entry_warnings(entry)
        if translation is not None and not translation.strip():
            out.append(tr('there is no meaning in {language}: the English '
                          'one is shown', language=tr(self.language_name)))
        return out

    def trial(self) -> Lexicon:
        """The lexicon with the dictionary (and the meanings in the
        language chosen) as edited."""
        if self._trial is None:
            self._trial = self.base.with_entries(self.numbered())
            if self.translating:
                lang = self.base.language(self.language)
                meanings = {k: v for k, v in lang.data.meanings.items()
                            if k[0] != 'entry'}
                meanings.update(
                    (('entry', uid), text) for uid, text in
                    self._translations[self.language].items())
                self._trial._languages[self.language] = Language(
                    lang.data._replace(meanings=meanings), lang.reference)
        return self._trial

    def try_word(self, word: str) -> str:
        """What WORDS says about WORD with the dictionary as edited (in the
        language chosen)."""
        settings = Settings()
        settings.language = self.language
        return Session(self.trial(), settings).lookup_latin(word)

    def summary(self, entry: Entry, width: int = 70) -> str:
        """A one-line description, for lists (with the meaning in the
        language chosen, if it has one)."""
        parts = principal_parts(entry) or entry.stems[0]
        meaning = self.translation(entry) or entry.meaning
        text = f'{parts}  {entry.part.pos.name}  {meaning.strip()}'
        return text if len(text) <= width else text[:width - 1] + '…'


class Editing:
    """What the two editors (words_edit_gui.py and words_edit.py) share:
    the entries found, the entry in the form (None for a new one), and
    whether the form has changes that were not applied.

    The editors pass the form's values as Fields and do the asking.  A
    change counts once it is applied; saving applies the form first, and
    leaving the entry (for another one, a new one, or to close) asks what
    to do with changes not applied."""

    def __init__(self, editor: Editor):
        self.editor = editor
        self.results: list[Entry] = []
        self.current: Entry | None = None
        self._shown: tuple | None = None    # the form as it was shown

    def find(self, query: str) -> list[Entry]:
        self.results = self.editor.search(query)
        return self.results

    def start(self, entry: Entry | None, fields: Fields) -> None:
        """The form now shows ENTRY (None: a new entry) as FIELDS."""
        self.current = entry
        self._shown = fields.snapshot()

    def pending(self, fields: Fields) -> bool:
        """Whether the form (FIELDS) has changes that were not applied."""
        return fields.snapshot() != self._shown

    def label(self) -> str:
        """The entry in the form, for questions: '“amicus, amici”' or
        'the new entry'."""
        if self.current is None:
            return tr('the new entry')
        return f'“{self.editor.name(self.current)}”'

    def apply(self, fields: Fields) -> tuple[Entry, str]:
        """Puts FIELDS into the dictionary, as a change to the entry in the
        form or as a new entry.  Returns the entry and 'Added' or
        'Changed' (in English: the editors translate it); raises
        xmldata.DataError if a value is wrong."""
        entry = fields.entry()
        old = self.current
        if old is None:
            entry = self.editor.add(entry)
            done = 'Added'
        else:
            entry = self.editor.replace(old, entry)
            done = 'Changed'
        if fields.translation is not None and self.editor.translating:
            self.editor.set_translation(entry, fields.translation)
        self.results = [entry] + [e for e in self.results
                                  if e is not old and e is not entry]
        self.start(entry, fields)
        return entry, done

    def leave(self, fields: Fields, ask) -> bool:
        """Before the form shows something else: whether it may.  If it
        has changes, ASK(label) decides: True applies them, False leaves
        them out, None stays.  Raises xmldata.DataError if they are to be
        applied but cannot be."""
        if not self.pending(fields):
            return True
        answer = ask(self.label())
        if answer is None:
            return False
        if answer:
            self.apply(fields)
        return True

    def delete(self) -> Entry:
        """Takes the entry in the form out of the dictionary."""
        entry = self.current
        if entry is None:
            raise ValueError(tr('there is no entry to delete'))
        self.editor.delete(entry)
        self.results = [e for e in self.results if e is not entry]
        self.current = None
        return entry

    def save(self, fields: Fields) -> tuple[Entry, str] | None:
        """Applies the form, if it has changes, and writes the dictionary.
        Returns what apply returned, if the form was applied.  Raises
        xmldata.DataError (and nothing is written) if the form has an
        error, OSError if the file cannot be written."""
        applied = self.apply(fields) if self.pending(fields) else None
        self.editor.save()
        return applied
