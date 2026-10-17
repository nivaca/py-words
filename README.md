py-words
========

William Whitaker's WORDS, a Latin-English dictionary with inflectional
morphology, in Python: it analyses inflected Latin words (and whole lines
of Latin) into their forms and dictionary entries, and can also look up
English words to find Latin equivalents.

It was written by Nicolas Vaughan (<nivaca@fastmail.com> and <n.vaughan@uniandes.edu.co>) in 2026, first
as a faithful translation of the Ada version maintained at
[mk270/whitakers-words](https://github.com/mk270/whitakers-words), then
redesigned as idiomatic Python with the same analyses, a more
readable output and a modern command line.  It needs only Python 3.11 or
later, with nothing to install.

[Nicolas Vaughan](https://artehum.uniandes.edu.co/profesores/nicolas-vaughan/) is Associate Professor of Literature at the School of Arts
and Humanities of the Universidad de los Andes, Bogotá, Colombia.

Installation
------------

### What is needed

Python 3.11 or later, and nothing else: the program uses only Python's
standard library.  The windows (the dictionary and the editor) need Tk,
which comes with Python on Windows and with the installers from
[python.org](https://www.python.org/downloads/) on macOS.  On Linux, and
with Homebrew's Python on macOS, it may be a separate package:

    $ sudo dnf install python3-tkinter         # Fedora
    $ sudo apt install python3-tk              # Debian, Ubuntu
    $ brew install python-tk                   # macOS with Homebrew

To see which Python you have, run `python3 --version`.  The Python that
comes with macOS may be too old: if so, install a newer one from
python.org or with Homebrew.  With an older Python the program says so and
stops.

The commands below are written with `python3`; on Windows, type `python`.

### Getting the program

Clone the repository:

    $ git clone https://github.com/nivaca/py-words.git

or download it as a zip (on GitHub: "Code", then "Download ZIP") and unpack
it anywhere.  The folder is the whole program: there is nothing to build
or install, and it can be run from where it is:

    $ cd py-words                              # (or the unpacked folder)
    $ python3 words.py amicus                  # a first test
    $ python3 words_gui.py                     # the window

### A menu entry

To start the program from the applications menu, run once

    $ python3 words_install.py

which adds two entries, with the program's icon: the window, and the
command line (in a terminal).  Where they go depends on the system:

* Linux (and other systems with freedesktop menus): the applications
  menu, as `.desktop` files and icons in `~/.local/share`;
* Windows: the Start menu, as shortcuts;
* macOS: `~/Applications`, as two small applications.

No administrator rights are needed.  The entries start the program in its
folder, so run the script again after moving the folder.

### Updating

With git, `git pull` in the folder; otherwise, download the program again
and replace the folder.  If you have edited the dictionary, keep a copy of
`data/dictionary.xml` first (with git, commit it).  The menu entries keep
working as long as the folder stays where it was.

### Uninstalling

    $ python3 words_install.py --uninstall     # remove the menu entries

then delete the folder.  The program also keeps a cache, which can be
deleted too: `~/.cache/py-words` on Linux, `~/Library/Caches/py-words` on
macOS, `%LOCALAPPDATA%\py-words` on Windows; the configuration file, if
one was made (see "Settings and files"); and the history of the searches
(see "Usage").

What is where
-------------

    words.py            the dictionary (command line and interactive)
    meanings.py         the same, showing only dictionary forms and meanings
    words_gui.py        the dictionary in a window
    words_edit.py       edit the dictionary in the terminal
    words_edit_gui.py   edit the dictionary in a window
    words_check.py      check the data files after editing them by hand
    words_convert.py    convert data in the original text format to XML
    words_install.py    add the program to the applications menu
    *.py                the rest of the program, used by the above
    data/               the dictionary and the other data files
    icons/              the program's icons
    tests/              the tests (not needed to use the program)

To use it elsewhere, copy (or zip) the folder; the tests can be left out.
A zip of the program without the tests:

    $ git archive --format=zip --prefix=py-words/ -o py-words.zip HEAD

Usage
-----

    $ python3 words.py rem acu tetigisti
    $ python3 words.py                         # interactive
    $ python3 words_gui.py                     # a window

On Windows, type `python` instead of `python3`; `pythonw words_gui.py`
opens the window without a console.

In the windows, Ctrl and + or − make the text larger or smaller, and Ctrl
and 0 brings back the usual size (Command instead of Ctrl on macOS).
"Font…" chooses the fonts: a fixed-width one for the results, whose
columns must line up, and one for the rest of the window.  The choice is
remembered in the configuration file (see "Settings and files").  To start
the program from the applications menu instead, see "Installation" above.

    words.py                          interactive
    words.py amicus est               look up words (a line of Latin)
    words.py -f in.txt [-o out.txt]   each line of a file ('-': standard input)
    words.py -e friend [--pos N]      English to Latin
    words.py -m ...                   dictionary forms and meanings only
                                      (the same as `meanings.py ...`)
    words.py --no-glosses ...         analyses in words, not abbreviations
    words.py --datadir DIR ...        the data files in DIR
    words.py --config                 create/show the configuration file
    words.py --clear-history          forget the earlier searches
    words.py --help

The data files are looked for with `--datadir`, then
`$WHITAKERS_WORDS_DATADIR`, then the folder in the configuration file, then
the `data` folder next to the program.

In interactive mode a line is looked up unless it starts with one of
these:

    ~E / ~L    English to Latin / Latin to English
    @FILE      look up each line of FILE
    #          change the parameters
    !          change the developer modes
    ?          help

An empty line twice, or Ctrl-D, quits.  A file given with `-f` or `@` can
also switch the language with lines `~E` and `~L`.

The searches are remembered, also between sessions: in interactive mode,
Up and Down bring them back, and in the window the box where words are
typed lists them (Down opens the list, newest first).  The command line
and the window share them.  They are kept, the last 1,000, in
`$XDG_STATE_HOME/py-words/history` on Linux (usually
`~/.local/state/py-words`), `~/Library/Application Support/py-words` on
macOS and `%LOCALAPPDATA%\py-words` on Windows
(`$WHITAKERS_WORDS_HISTORY` names another file; set to nothing, nothing is
kept).  `words.py --clear-history`, or "Clear history" in the window's
Settings, forgets them.

The output
----------

Each word is followed by what it can be:

    laudatus
      laudo, laudare, laudavi, laudatus  verb, 1st conjugation  [XXXAX]
        recommend; praise, approve, extol; call upon, name; deliver eulogy on;
        laudat-us      PRF.PASS.PTCP.NOM.SG.M
        participle + est  3SG.PRF.PASS.IND
          PERF PASSIVE PPL + verb TO_BE => PASSIVE perfect system

For a dictionary entry: its principal parts and grammar (and, with
show_dictionary_codes, its codes of age, area, geography, frequency and
source), its meaning, and the forms the word can be, as stem-ending.  A
prefix, suffix or enclitic found on the word, or a trick needed to find it
(a spelling change, a syncopated perfect, two words written as one ...),
gets a line of its own, followed by what was found with it.  A word that is
not found is marked "(unknown)", and "(less likely forms are not shown)"
says that trim_output left something out.

The analyses of the forms are written in glossing abbreviations, as in
the [Leipzig Glossing Rules](https://www.eva.mpg.de/lingua/resources/glossing-rules.php):
the categories are separated by dots, and person and number are written
together (`2SG.PRF.ACT.IND` is 2nd person singular perfect active
indicative).  The abbreviations are those of the [list of glossing
abbreviations](https://en.wikipedia.org/wiki/List_of_glossing_abbreviations);
those marked * are not among the standard Leipzig ones:

* Case: NOM nominative, GEN genitive, DAT dative, ACC accusative, ABL
  ablative, VOC vocative, LOC locative
* Number: SG singular, PL plural
* Gender: M masculine, F feminine, N neuter, C* common (masculine or
  feminine)
* Person: 1 first person, 2 second person, 3 third person
* Tense: PRS present, IMPF* imperfect, FUT future, PRF perfect, PLUP*
  pluperfect, FUT.PRF* future perfect
* Voice: ACT* active, PASS passive
* Mood: IND indicative, SBJV subjunctive, IMP imperative, INF infinitive,
  PTCP participle
* Other verb forms: SUP* supine
* Degree: POS* positive, CMPR* comparative, SPRL* superlative
* Numerals: CARD* cardinal numeral, ORD* ordinal numeral, DISTR distributive
  numeral, MULT* multiplicative numeral (numeral adverb)

They are kept in `data/gloss.xml`, where they can be changed.  With the
parameter `use_glosses` off ("Use glosses" in the window's Settings;
`--no-glosses` on the command line, for one run), or without that file,
the analyses are written in words ("genitive plural", "2nd person
singular perfect active indicative").

Settings and files
------------------

The parameters (`#`) and developer modes (`!`) are those of the original
program; `?` in their dialogues explains each one.  In the window,
"Settings…" shows them all, with what each one does; a change there
applies at once.  They are kept, with the fonts of the windows and
(optionally) the data folder, in one configuration file, `config.toml`:

| System  | Configuration file                                         |
|---------|------------------------------------------------------------|
| Linux   | `$XDG_CONFIG_HOME/py-words/config.toml` (usually `~/.config/py-words`) |
| macOS   | `~/Library/Application Support/py-words/config.toml`       |
| Windows | `%APPDATA%\py-words\config.toml`                           |

(`$WHITAKERS_WORDS_CONFIG` names another folder.)  The program writes it
when settings are saved in the `#` or `!` dialogue or the fonts change;

    $ python3 words.py --config

creates it with the current settings and shows where it is.  It is plain
text, with a comment for each setting, and can be edited by hand:

    [data]
    folder = ""              # empty: the data folder next to the program

    [parameters]
    trim_output = true
    do_examples = false
    ...

    [developer]
    use_prefixes = true
    start_file_character = "@"
    ...

    [fonts]
    text_size = 13

Any setting can be left out, and then has its usual value.  When the
program rewrites the file it keeps the values, but not comments of your
own.

The settings files of the original program, WORD.MOD (the parameters) and
WORD.MDV (the developer modes), are still read if there are any, in the
current folder or the program folder, but the configuration file comes
first.

On request the program writes, in the current directory, WORD.OUT (the
results), WORD.UNK (the unknown words) and WORD.STA (statistics on the
tricks and affixes used).

The data files
--------------

| File (in `data/`) | Contents                                   |
|-------------------|--------------------------------------------|
| `dictionary.xml`  | the dictionary, one `<entry>` per word     |
| `inflections.xml` | the inflectional endings                   |
| `uniques.xml`     | irregular forms not built from a stem      |
| `addons.xml`      | prefixes, suffixes and enclitics (tackons) |
| `sources.xml`     | the names of the sources (dictionaries ...) |
| `gloss.xml`       | the glossing abbreviations of the analyses |
| `special.xml`     | (optional) a second, special dictionary    |

Each entry names its source with a one-letter code (`source="O"`);
`sources.xml` says what each code stands for, e.g.

    <source code="O" name="Oxford Latin Dictionary"/>
    <source code="U" name="Du Cange"/>

The editors show these names when a source is chosen, and `words_check.py`
warns about entries whose code is not listed.  To add a source, give it an
unused letter there.

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

A change to an entry is put into the dictionary with "Apply changes" (F3
in the terminal); "Save" (F2) also applies the entry shown before writing
the file, and choosing another entry, starting a new one or closing the
editor while the entry shown has changes not applied asks whether to apply
them.  Nothing is written until you save.  The first save in a session
keeps the original file as `dictionary.xml.bak`.

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
| `config.py`   | the configuration file, config.toml                           |
| `history.py`  | the history of the searches                                   |
| `gui_fonts.py`| the fonts of the windows: zoom, the "Font…" dialogue          |
| `gui_settings.py` | the window's "Settings…" dialogue                         |
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
with the expected output.  Some regression tests switch options on with a
`config.toml` of their own: the English examples and dictionary forms of
every kind (`50_forms`), the developer modes (`60_developer_modes`), and
leaving out dictionary forms or known words.  After an intended change to
the output, regenerate the expected files with `UPDATE_GOLDEN=1` and review
them with `git diff`.

Version
-------

- 1.6:
  - The searches are remembered between sessions, and shared by the
    command line (Up and Down in interactive mode) and the window (the
    list of the box where words are typed).  `--clear-history`, or "Clear
    history" in the window's Settings, forgets them.
  - The window's options (Trim output, Examples ...) are only in the
    Settings dialogue, which has them all.
- 1.5:
  - The window has a "Settings…" dialogue with every parameter and
    developer mode of the command line, each with what it does; changes
    apply at once and are kept in the configuration file.
  - The new parameter `use_glosses` (on by usual) chooses between glossing
    abbreviations and words in the analyses: "Use glosses" in the window's
    Settings, the `#` dialogue or `--glosses` / `--no-glosses` on the
    command line.
- 1.4:
  - The analyses of the forms are written in glossing abbreviations, as in
    the Leipzig Glossing Rules: `GEN.PL` (was "genitive plural"),
    `2SG.PRF.ACT.IND` (was "2nd person singular perfect active
    indicative").  The abbreviations are kept in `data/gloss.xml`, which
    `words_check.py` checks; without that file the analyses are in words.
- 1.3:
  - Fixed dictionary forms of numerals with a single stem: *centensimus,
    centensima, centensimum* (was *centensim*), *biseni, bisenae, bisena*,
    *ambo, ambae, ambo*.
  - Fixed English examples of the subjunctive: "let us ~" (was "let us
    may/must/should ~"), and the passive "I may/must/should be ~ed" (was
    "I may/must/should ~").
  - More regression tests: dictionary forms of every kind with the English
    examples, the developer modes, and the options that leave out
    dictionary forms or known words.  Each regression test can set its own
    options, in a `config.toml` of its own.
- 1.2:
  - The two dictionary editors share one implementation of editing an
    entry (applying changes, asking before they are lost, saving), in
    `editor.py`, so that they behave the same.
  - Fixed: after "Apply changes", the window editor listed the entry twice
    (old and new); its button did not say "Add to the dictionary" on a new
    entry; and deleting from the list in the terminal editor did not ask
    about changes not applied to the entry being edited.
- 1.1:
  - The dictionary editors no longer lose changes: "Save" (F2) applies the
    entry being edited before writing the file, and choosing another
    entry, starting a new one or closing the editor while the entry has
    changes not applied asks whether to apply them.
  - The names of the sources (Oxford Latin Dictionary, Du Cange ...) are
    kept in `data/sources.xml`, where they can be changed or added to.
    `words_check.py` checks the file, and warns about entries whose source
    code is not listed there.
- 1.0: first public release.

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

py-words is distributed under the MIT License (see
[LICENCE.txt](LICENCE.txt)): anyone may use, copy, change and
redistribute it, also commercially, provided that the copyright notices
are kept, acknowledging Nicolas Vaughan (<nivaca@fastmail.com>, 2026) for
the Python program and William A. Whitaker (1936-2010) for WORDS and its
dictionary data.  Whitaker's original permission, which allows any use of
his program and data, reads:

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
