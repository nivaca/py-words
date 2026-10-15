How py-words was made
=====================

py-words is a Python version of WORDS, the Latin-English dictionary
program written by Colonel William Whitaker (1936-2010).  It was made by
Nicolas Vaughan in 2026 from the Ada version of WORDS maintained at
[mk270/whitakers-words](https://github.com/mk270/whitakers-words).  This
document describes how it was done, in four stages.

Nicolas Vaughan is Associate Professor of Literature at the School of Arts
and Humanities of the Universidad de los Andes, Bogotá, Colombia.

1. A faithful translation
-------------------------

At first, the program was a line-by-line translation of the Ada program.
Its modules followed the Ada packages closely, and the Ada behaviour was
reproduced exactly, down to its peculiarities:

* fixed-length strings padded with blanks;
* arrays counted from 1, or from whatever bound the Ada code declared;
* exceptions used to steer the program, as Ada's `Constraint_Error` and
  `End_Error` were;
* column-based text output, as with Ada's `Text_IO`;
* the dictionary kept, as in the original, in sorted stem files searched
  by binary search through an index of their first two letters.

The aim was output identical, byte for byte, to that of the Ada program.
The regression tests of the Ada version, whose inputs include 735 lines of
the *Aeneid*, were the measure.  This version was useful as a reference,
but it was Ada written in Python: about 10,300 lines in 26 modules, hard
to read and to change.

2. The data in XML
------------------

WORDS keeps its data in four text files with fixed columns: DICTLINE.GEN
(the dictionary), INFLECTS.LAT (the endings), UNIQUES.LAT (irregular
forms) and ADDONS.LAT (prefixes, suffixes and enclitics).  They were
converted to XML:

| Original      | Now               | Contents                          |
|---------------|-------------------|-----------------------------------|
| DICTLINE.GEN  | `dictionary.xml`  | 39,335 entries                    |
| INFLECTS.LAT  | `inflections.xml` | 1,798 inflectional endings        |
| UNIQUES.LAT   | `uniques.xml`     | 79 irregular forms                |
| ADDONS.LAT    | `addons.xml`      | prefixes, suffixes and enclitics  |

The grammatical codes are written as in the original files (`N`, `V`,
`NOM`, `PRES`, declensions as "2 1" ...), so an entry can be read by
anyone who knows WORDS.  An XML Schema, `words.xsd`, describes the format,
so that an XML editor can check the files while they are edited.  The
converter (`words_convert.py`) turns files in the original format into
XML.  A checker (`words_check.py`) reports mistakes in hand-edited
files, with line numbers.

3. A redesign in idiomatic Python
---------------------------------

With the translation as a reference, the program was rewritten as
ordinary Python, keeping what matters (what WORDS finds for a word) and
replacing the rest:

* the grammatical codes became enumerations, and dictionary entries,
  endings and forms became immutable records (dataclasses) that mirror
  the XML;
* the sorted files and binary searches became dictionaries in memory:
  stems, endings and irregular forms are looked up directly, with u/v and
  i/j treated as the same letter;
* the analysis returns structured results, which are ordered and trimmed
  with ordinary sorting, instead of filling shared arrays;
* settings are passed explicitly, instead of being changed temporarily
  as a way of passing arguments; there is no shared mutable state;
* the output was given a new, more readable layout, and the command line
  became a modern one (`argparse`);
* what users rely on was kept: the settings files WORD.MOD and WORD.MDV
  (in their original format) with the `#` and `!` dialogues, the output
  files WORD.OUT, WORD.UNK and WORD.STA, and the developer modes.

The result is about 6,700 lines, in modules organised by task (see "How
it works" in the README).

Checking the redesign
~~~~~~~~~~~~~~~~~~~~~

The new analyser was compared with the faithful translation on a corpus
of 133,671 words: every stem of the dictionary, forms generated from the
stems and endings, and the inputs of the regression tests.  For each word,
the results of both versions were reduced to comparable records (entry,
stem, ending, grammatical form, and any affix or spelling trick used) and
compared.  99.2% of the words gave the same results.  Every remaining
difference was examined; each one turned out to be either a deliberate
change or a bug of the original that the redesign does not reproduce,
such as stems matched to unrelated entries, results attributed to the
wrong enclitic, ill-formed Roman numerals accepted, or a spelling rule
that could never apply.  These are listed under "Changes from the
original program" in the README.  English-to-Latin lookups were compared
in the same way.

4. Tools and refinements
------------------------

On this base, the following were added:

* a window for the dictionary (`words_gui.py`), using Tk from the
  standard library;
* two dictionary editors, one in a window (`words_edit_gui.py`) and one
  in the terminal (`words_edit.py`), to add, correct and delete entries
  without editing XML by hand.  They explain each code, show the entry as
  WORDS will show it, and can try a word against the edited dictionary
  before it is saved;
* a readable layout for `dictionary.xml`, one element per line, which the
  editors and the converter keep when they save;
* faster start-up: the XML is read as a stream, and what is read is
  cached, so that the program starts in about a quarter of a second;
* a simple layout: the programs in one folder, the data in `data/`, with
  nothing to install beyond Python 3.11 or later;
* current Python: the code was brought up to Python 3.11 (modern type
  annotations, f-strings, `match` statements, data classes with slots),
  and each program says plainly when it is run with an older Python.

Testing
-------

The program has unit tests and regression tests (`tests/`).  The
regression tests run the inputs inherited from the Ada version and compare
the output with reviewed expected files; the editors are tested by driving
them as a user would, in a terminal and in a window.
