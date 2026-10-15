py-words
========

William Whitaker's WORDS, a Latin-English dictionary with inflectional
morphology, in Python: it analyses inflected Latin words (and whole lines
of Latin) into their forms and dictionary entries, and can also look up
English words to find Latin equivalents.

It was written by Nicolas Vaughan (<nivaca@fastmail.com>) in 2026, first
as a faithful translation of the Ada version maintained at
[mk270/whitakers-words](https://github.com/mk270/whitakers-words), then
(version 2) redesigned as idiomatic Python with the same analyses, a more
readable output and a modern command line.  It needs only Python 3.8 or
later, with nothing to install.

What is where
-------------

    words.py            the dictionary (command line and interactive)
    meanings.py         the same, showing only dictionary forms and meanings
    words_gui.py        the dictionary in a window
    words_edit.py       edit the dictionary in the terminal
    words_edit_gui.py   edit the dictionary in a window
    words_check.py      check the data files after editing them by hand
    words_convert.py    convert data in the original text format to XML
    *.py                the rest of the program, used by the above
    data/               the dictionary and the other data files
    tests/              the tests (not needed to use the program)

To use it elsewhere, copy (or zip) the folder; the tests can be left out.
A zip of the program without the tests:

    $ git archive --format=zip --prefix=py-words/ -o py-words.zip HEAD

Usage
-----

    $ python3 words.py rem acu tetigisti
    $ python3 words.py                         # interactive
    $ python3 words_gui.py                     # a window

On Windows, `pythonw words_gui.py` opens the window without a console.

    words.py                          interactive
    words.py amicus est               look up words (a line of Latin)
    words.py -f in.txt [-o out.txt]   each line of a file ('-': standard input)
    words.py -e friend [--pos N]      English to Latin
    words.py -m ...                   dictionary forms and meanings only
                                      (the same as `meanings.py ...`)
    words.py --datadir DIR ...        the data files in DIR
    words.py --help

The data files are looked for with `--datadir`, then
`$WHITAKERS_WORDS_DATADIR`, then the `data` folder next to the program.

In interactive mode a line is looked up unless it starts with one of
these:

    ~E / ~L    English to Latin / Latin to English
    @FILE      look up each line of FILE
    #          change the parameters
    !          change the developer modes
    ?          help

An empty line twice, or Ctrl-D, quits.  A file given with `-f` or `@` can
also switch the language with lines `~E` and `~L`.

The output
----------

Each word is followed by what it can be:

    laudatus
      laudo, laudare, laudavi, laudatus  verb, 1st conjugation  [XXXAX]
        recommend; praise, approve, extol; call upon, name; deliver eulogy on;
        laudat-us      perfect passive participle, nominative singular masculine
        participle + est  3rd person singular perfect passive indicative
          PERF PASSIVE PPL + verb TO_BE => PASSIVE perfect system

For a dictionary entry: its principal parts and grammar (and, with
show_dictionary_codes, its codes of age, area, geography, frequency and
source), its meaning, and the forms the word can be, as stem-ending.  A
prefix, suffix or enclitic found on the word, or a trick needed to find it
(a spelling change, a syncopated perfect, two words written as one ...),
gets a line of its own, followed by what was found with it.  A word that is
not found is marked "(unknown)", and "(less likely forms are not shown)"
says that trim_output left something out.

Settings and files
------------------

The parameters (`#`) and developer modes (`!`) are those of the original
program; `?` in their dialogues explains each one.  They can be saved in
WORD.MOD and WORD.MDV, which are read at start-up from the current
directory or the program folder, in the original format (names the program
no longer uses are ignored).  On request the program writes, in the current
directory, WORD.OUT (the results), WORD.UNK (the unknown words) and WORD.STA
(statistics on the tricks and affixes used).

The data files
--------------

| File (in `data/`) | Contents                                   |
|-------------------|--------------------------------------------|
| `dictionary.xml`  | the dictionary, one `<entry>` per word     |
| `inflections.xml` | the inflectional endings                   |
| `uniques.xml`     | irregular forms not built from a stem      |
| `addons.xml`      | prefixes, suffixes and enclitics (tackons) |
| `special.xml`     | (optional) a second, special dictionary    |

`words.xsd` describes their format, so an XML editor can check them as you
type.  The grammatical codes are those of the original files; an entry
of `dictionary.xml` looks like this:

    <entry pos="N" decl="2 1" gender="M" kind="P" age="X" area="X" geo="X"
      freq="B" source="O">
      <stem>amic</stem>
      <stem>amic</stem>
      <meaning>friend, ally, disciple; loved one; patron; counselor/courtier (to a prince);</meaning>
    </entry>

The order of the elements matters.  The editors and the converter write
the dictionary in this layout (each `<meaning>` must stay on one line).

Reading the files takes about half a second, so what is read is cached
(in `~/.cache/py-words` on Linux, `~/Library/Caches/py-words` on macOS,
`%LOCALAPPDATA%\py-words` on Windows) and used while the files are
unchanged; a later start takes about a quarter of a second.  The cache
holds at most four data folders.  `$WHITAKERS_WORDS_CACHE` names another
folder for it; set to nothing, it switches the cache off.  Deleting the
cache is always safe.

Editing the dictionary
----------------------

Two editors add, correct and delete entries of `data/dictionary.xml`:

    $ python3 words_edit_gui.py      # a window
    $ python3 words_edit.py          # in the terminal

The window is also opened by "Edit dictionary..." in the main window; the
terminal editor is a full-screen program (F-keys or Ctrl keys, shown at
the bottom; on Windows it needs the windows-curses package).  In both:

* find an entry by a Latin form ("amicorum"), a stem or an English word;
* correct it, add a new one (from scratch, or "like this" one), or delete
  it.  The fields depend on the part of speech, and the codes are chosen
  from lists that explain them;
* the preview shows the entry as WORDS will (amicus, amici  noun, 2nd
  declension, masculine) and any problem; "try a word" shows what WORDS
  makes of a word with the dictionary as edited.

Nothing is written until you save.  The first save in a session keeps the
original file as `dictionary.xml.bak`.

The files can also be edited by hand: copy the entry of a similar word in
`data/dictionary.xml` and edit it, then run

    $ python3 words_check.py

which reports, with line numbers, what WORDS cannot read (malformed XML,
unknown codes, stems with characters other than letters) and entries that
probably do not do what was meant (a declension with no endings, a missing
stem, a long meaning, a duplicate).  WORDS itself stops with the file and
line of the first error.

Data in the original text format (DICTLINE.GEN, INFLECTS.LAT, UNIQUES.LAT,
ADDONS.LAT) is converted with

    $ python3 words_convert.py SRC [DEST]

How it works
------------

| Module        | Role                                                          |
|---------------|---------------------------------------------------------------|
| `model.py`    | the grammatical codes and the records (Entry, Form, Inflection ...) |
| `xmldata.py`  | reading and writing the data files                            |
| `lexicon.py`  | the data, indexed: stems, endings, irregular forms, affixes   |
| `analyzer.py` | analysis of a word: stems + endings, qu- pronouns, affixes, enclitics, compound tenses |
| `tricks.py`   | other spellings, syncope, Roman numerals, two words as one    |
| `results.py`  | the results: ordering, trimming and grouping                   |
| `english.py`  | the English index, for English-to-Latin lookups               |
| `forms.py`    | principal parts, grammar in words, example glosses            |
| `render.py`   | the text of the results                                       |
| `settings.py` | the parameters and developer modes, and their files           |
| `session.py`  | a session: language, output files                             |
| `editor.py`   | editing the dictionary: what the two editors share            |
| `words.py`    | the command line, interactive mode and setting dialogues      |
| `words_*.py`, `meanings.py` | the other programs (see above)                  |

A word is analysed by splitting it into every possible stem and ending,
looking the stems up in the dictionary and keeping the combinations whose
grammar agrees (the declension, gender, stem number ...).  Failing that,
the program tries prefixes and suffixes, enclitics (-que, -ne ...) and,
for unknown words, the tricks.  Everything is looked up with u/v and i/j
treated as the same letter.

Changes from the original program
---------------------------------

The analyses are those of the original program; on a corpus of 134,000
generated words more than 99% come out the same.  The differences are
deliberate:

* the output layout and the command line are new;
* bugs that only the original's Ada structure explains are fixed: stems
  matched to unrelated dictionary entries of the same length, results
  attributed to the wrong enclitic, duplicated results, an affix shown
  without the results it belonged to, ill-formed Roman numerals (CCD)
  read as numbers, a spelling rule (assimilated prefixes such as ad- in
  appono) that could never apply, the voice of the active periphrastic,
  irregular forms without a part of speech, crashes on some lines;
* the enclitic -cumque on adjectives, which the original read wrongly
  from ADDONS.LAT and so never used, is used;
* there are no fixed limits on the number of results;
* the English index is built from the meanings by a simpler reading, with
  the same ranking; most lookups give the same results;
* the developer modes that did nothing are gone (NO_MEANINGS, DO_I_FOR_J,
  DO_U_FOR_V, NO_SCREEN_ACTIVITY, UPDATE_LOCAL_DICTIONARY,
  UPDATE_MEANINGS, MINIMIZE_OUTPUT, IGNORE_UNKNOWN_CAPS), as is the local
  dictionary DICT.LOC, which the original never managed to load.

Testing
-------

    $ python3 -m unittest discover -s tests

runs the unit tests and the regression tests in `tests/regression`, which
compare the output for some inputs (among them 735 lines of the Aeneid)
with the expected output.  After an intended change to the output,
regenerate the expected files with `UPDATE_GOLDEN=1` and review them with
`git diff`.

The Ada version
---------------

The Ada sources, their build files and the data in its original text
format are not in this repository; they are upstream at
[mk270/whitakers-words](https://github.com/mk270/whitakers-words), whose
[website](http://mk270.github.io/whitakers-words/operational.html)
documents the original program.  `words_convert.py` turns data files in
the original format into XML.

Background
----------

WORDS was written by Colonel William Whitaker (USAF, Retired), who died in
2010.  The Ada version this port is based on is a cleaned-up version of his
programme, maintained as an exercise in digital preservation.  Its lexicon
does not record vowel length.

Licensing
---------

The Python code is copyright (c) 2026 Nicolas Vaughan
(<nivaca@fastmail.com>) and distributed under the BSD 3-Clause licence;
see [LICENCE.txt](LICENCE.txt).  The dictionary data in `data/` and the
original WORDS program it is based on remain under William Whitaker's
terms:

WORDS, a Latin dictionary, by Colonel William Whitaker (USAF, Retired)

Copyright William A. Whitaker (1936-2010)

This is a free program, which means it is proper to copy it and pass
it on to your friends. Consider it a developmental item for which
there is no charge. However, just for form, it is Copyrighted
(c). Permission is hereby freely given for any and all use of program
and data. You can sell it as your own, but at least tell me.

This version is distributed without obligation, but the developer
would appreciate comments and suggestions.

All parts of the WORDS system, source code and data files, are made freely
available to anyone who wishes to use them, for whatever purpose.
