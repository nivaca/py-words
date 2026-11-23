# Changelog

All notable changes to py-words. The releases, with the zip, the
AppImage, the installers (from 3.29), the signed .deb and the signed RPM,
are on
[Codeberg](https://codeberg.org/nivaca/py-words/releases) and
[GitHub](https://github.com/nivaca/py-words/releases); the RPM for
Fedora is also on Copr, in `nivaca/py-words`. The repository starts at
2.13 (2026-10-22); the versions before it are summed up at the end,
without dates, from the list "Version" of the README.

## 3.30 — 2026-11-22

- **Every release signed**: besides the RPM and the .deb, each file
  published (the zip, the AppImage, the installers) comes with its
  OpenPGP signature (`.asc`), with `SHA256SUMS` and its signature, and
  with the public key; the tag of the version is signed too.
  `tools/release.py` always makes the signed RPM now (`--no-rpm` leaves it
  out) and checks each signature with the published key before anything
  is published (`tools/sign_release.py`); `--installers` signs those of
  Windows and macOS. The workflows on GitHub no longer replace the signed
  AppImage and installer for Linux. The README says how to check a
  download.

## 3.29 — 2026-11-22

- **Installers for Windows, macOS and Linux**, each with its own Python
  3.13 (from python-build-standalone, of a fixed version, checked by its
  SHA-256), so that nothing else is needed (`tools/bundle-installer.py`,
  `packaging/installer/`):
  - Windows (`py-words-v.3.29-windows-x64-setup.exe`, Inno Setup): for
    the user without administrator rights, or for everyone; English or
    Spanish; the four programs in the Start menu, a desktop shortcut and
    the `py-words` command in the PATH if wanted; an uninstaller that
    asks whether to remove the settings too.
  - macOS (`-macos-arm64.pkg`, `-macos-x86_64.pkg`): `py-words.app`, the
    three Terminal programs and the command in `/usr/local/bin`, the last
    two optional; `sudo py-words uninstall [--purge]` removes it.
  - Linux (`-linux-x86_64.run`): a shell script with the program inside,
    for the user (`~/.local`) or, with `sudo`, for everyone (`/opt`,
    `/usr/local`); the four menu entries, the icons, the command and an
    uninstaller; it checks itself before installing.
  - All of them give the `py-words` command of the AppImage and the
    packages, plus `py-words uninstall`, and keep the dictionary
    read-only, so that an update cannot overwrite edits.
- `.github/workflows/installers.yml` makes the installers on GitHub,
  each on its own system, installs each one, tries it (Tk, curses, HTTPS,
  a search) and removes it, and adds them to the release of each tag.
- `tools/release.py` makes the installer for Linux (`--no-installer`
  does not), and `--installers` copies those for Windows and macOS from
  the release on GitHub to that on Codeberg.
- Tests of the installers (`tests/test_installer.py`); the manuals, the
  READMEs and the lists of licences describe them.

## 3.28 — 2026-11-21

- **The language of the interface in the main window** of each program,
  as on the author's web page: its code (EN, ES or LA), which opens the
  list of the languages (each in itself, the current one marked).  In the
  window it is at the bottom right, beside the moon, with its name in the
  status line under the mouse; on the web page it is a round button just
  before the moon, that works without JavaScript and goes back to the
  search, not to the settings.  `words_tui.py` shows the code at the right
  of its top line; F6 changes it, as before.
- Tests for the button of the window and for that of the web page.

## 3.27 — 2026-11-21

- **A .deb package for Debian, Ubuntu and their derivatives**
  (`packaging/build-deb.py`), attached to the releases with a detached
  OpenPGP signature (`.deb.asc`) made with the RPM's key.  It installs
  the same as the RPM (the program in `/usr/share/py-words`, the
  `py-words` command, the four menu entries, the icons and the
  documentation) and depends on `python3 (>= 3.13)` and `python3-tk`.
  It is assembled with Python's standard library alone (an ar archive
  with two tar.xz), so it is built on Fedora, without dpkg; like the RPM,
  the newest one is also copied into `dist/`.
- `tools/release.py` makes, signs and attaches the .deb (`--no-deb`
  leaves it out).
- `tests/test_build_deb.py` builds the package in a temporary folder,
  checks its format and contents, and runs the program it installs.

## 3.26 — 2026-11-21

- A user manual in PDF, in English, Spanish and Medieval Latin
  (`docs/MANUAL_en.pdf`, `docs/MANUAL_es.pdf`, `docs/MANUAL_la.pdf`, with
  their LaTeX sources, built with `latexmk`): installing, the four
  programs, reading the results, Logeion, the settings, the editors and
  the keys, with tables of the codes, the abbreviations, the options and
  the keys, and an index.  The RPM installs them.
- The interface can also be in Medieval Latin (`data/interface/la.xml`;
  "Latina" in "Language of the interface", `--interface la`): the menus,
  buttons, messages and help.  The meanings stay in English or Spanish.
- `README_la.md`: the README in Medieval Latin, with Latin screenshots
  (`tools/screenshots.py` now takes them too).

## 3.25 — 2026-11-21

- `docs/LICENCES.md` and `docs/LICENCIAS_es.md` list the open-source
  software py-words uses, with the licence of each one: what it runs on
  (Python, Tcl/Tk, ncurses), the code and data it took in (WORDS,
  Collatinus, py-logeion), what the AppImage and the RPM carry or need,
  and the tools used to make, test and publish it.  The READMEs and the
  descriptions point to them, and the RPM installs them.
- `docs/DESCRIPCIÓN_es.md` no longer says that the program never needs
  the internet: Logeion does.

## 3.24 — 2026-11-20

- On a hi-res display scaled to 200%, the text of the windows follows
  the scaling even when fontconfig fixes a DPI. A rule of 96 in the
  user's own fontconfig settings left the text at half its size with
  the Tk 9 of the RPM; the windows now start fontconfig with the usual
  configuration plus one rule that sets the DPI of the desktop.
- `packaging/build-rpm.sh` copies the newest RPM into `dist/` too, in
  place of the older ones there.
- `docs/DESCRIPCIÓN_es.md` keeps to six sections (Análisis, Diseño,
  Implementación, Validación, Plataforma and Ambiente), each of at most
  4000 characters, in the third person.

## 3.23 — 2026-11-18

- When Logeion is the source, its dictionary is the DMLBS (the
  Dictionary of Medieval Latin from British Sources) until another one is
  chosen, in all the programs; before, it was all of them. A dictionary
  already chosen is kept, and "All dictionaries" is still in the list.
- On the web page, "Search in" offers py-words or Logeion.

## 3.22 — 2026-11-18

- **The web page can also show the entries of Logeion**, as the window,
  the terminal and the command line already could. "Search in" (Local or
  Logeion) and a list of Logeion's dictionaries are beside "Meanings
  in". Each word is analysed here first, and its analysis comes before
  Logeion's entries for its lemmas; the links to other words of Logeion
  look them up on the page.
- Meanwhile the other direction, the language of the meanings and the
  fuzzy search are greyed out, since Logeion searches in Latin only.
- On a public server the choice is each visitor's, kept in their
  cookies, and Logeion is asked only for the first twelve words of a
  search.
- The contact email is now nicolasvaughan@proton.me.

## 3.21 — 2026-11-17

- The documentation no longer describes the version that ran in the
  browser (Pyodide), which is gone: the README's "Online" and the
  descriptions in `docs/` speak only of the server,
  <https://nivaca.pythonanywhere.com/>. The program does not change.

## 3.20 — 2026-11-14

- Python 3.13 or later is needed (it was 3.11): the check in
  `version.py`, the RPM, the tests on GitHub and the documents. The
  AppImage carries its own Python 3.13, and every supported Fedora has a
  newer one.

## 3.19 — 2026-11-14

- The documentation and the comments of the code are written more
  plainly, in English and in Spanish; no code changed. Facts that were
  out of date are corrected: there is no site any more, the version in
  the browser is described in the past, and the 366 tests run with
  `tools/test.py`.

## 3.18 — 2026-11-13

- With Logeion, each word shows first its analysis, as py-words gives it
  but without its meanings (*dixi*: *dico, dicere, dixi, dictus*;
  *dix-ī 1SG.PRF.ACT.IND*), and then Logeion's entries. Entries that are
  alike come once, with all their forms, and a form's own page is shown
  only if Lewis and Short has it (*arma*, not *dixi*).
- The source, Logeion's dictionary and the direction last chosen are
  kept for the next start of every program (`[logeion]` and `[search]`
  in the configuration file); `--local`, `--logeion`, `--dictionary`
  and `-e` change them for one run.
- In interactive mode, `~G` changes between Local and Logeion and `~D`
  chooses Logeion's dictionary; they work in files too.
- In a terminal, results longer than the screen open in the pager
  (`less`, or `$PAGER`), and the results of the command line and of
  `words_tui.py` are in colour (`colours.py`; `NO_COLOR` turns it off).
- The site at `nicolasvaughan.org/py-words/` is gone, with its code
  (`pages/`); the dictionary online is at nivaca.pythonanywhere.com. The
  workflow on GitHub only runs the tests.
- `tools/test.py` runs each class of tests in a process of its own, in
  about a minute and a half instead of nine. The terminal tests wait for
  the answers of the programs instead of fixed times.

## 3.17 — 2026-11-13

- **Logeion as a second source.** The window ("Search in": Local or
  Logeion), `words_tui.py` (F8) and the command line (`--logeion`) can
  show, instead of this dictionary's entries, those of Logeion
  (logeion.uchicago.edu) for the lemmas of the words. py-words analyses
  the words first, since Logeion does not analyse inflected forms. A
  list beside "Search in" (F5 in the terminal, `--dictionary` on the
  command line) shows only one of its dictionaries (Lewis & Short,
  Gaffiot, Georges, Du Cange ...) or all of them. It needs the internet.
- Meanwhile the other direction, the language of the meanings, the fuzzy
  search and the dictionary editor are greyed out.
- The Flatpak is no longer made, and the version that ran in the browser
  is gone with its code (`pages/index.html`, `pages/app.js`,
  `pages/build.py --browser`).
- The tests of the windows run on a virtual display of their own (Xvfb),
  without `xvfb-run`.
- The lists of `words_tui.py` (F5, F6) show their whole title.

## 3.16 — 2026-11-13

- Selected text in the results of the window is readable. It was drawn
  in the colours of the results (a headword, in light mode, in the very
  colour of the selection), and white on light grey where the results
  were not focused. Now it is white on the colour of the selection, in
  both modes.

## 3.15 — 2026-11-13

- The window has an Edit menu, with Cut, Copy and Paste (Ctrl and X, C,
  V), for the search box and the box of "Find in results", or for
  copying text selected in the results.
- In the terminal, F7 copies all the results as they are (not cut at the
  width of the screen), through the system's clipboard program
  (wl-copy, xclip, xsel, pbcopy, clip) or else the terminal itself (OSC
  52). When the keys do not fit in the last line, as in 80 columns,
  those between F5 and F10 are left out, so that F1 and F10 are always
  seen.
- The program is also a Flatpak (`tools/bundle-flatpak.py`,
  `release.py --flatpak`), attached to the releases of 3.15 and 3.16
  only. In the Flatpak the dictionary cannot be edited, and the program
  says so.
- The version that ran in the browser (Pyodide) is no longer published:
  its address sends to the server too.

## 3.14 — 2026-11-13

- **The terminal interface starts in the AppImage.** The Python in the
  AppImage could not read how most terminals describe themselves (those
  with 256 colours, as in Fedora and Debian 12 and later), and the `tui`
  stopped at once with "setupterm: could not find terminal". The
  AppImage now carries those descriptions in a form its ncurses can
  read.

## 3.13 — 2026-11-13

- An entry is shown once for each word, with all its forms under it. A
  verb's own forms and its participles came under two copies of the
  entry (*concito*: *concio* and *concieo* twice each), and so did
  entries of WORDS that show the same: *qui* has one for each gender and
  number (*quae* showed each pronoun up to three times), and an
  irregular form one for each case (*eadem*).

## 3.12 — 2026-11-13

- Entries of the same word that have the same forms, as a word of WORDS
  and its medieval sense from Latham (*subsisto*, *cura*), show those
  forms once, after the last of them, as WORDS did.
- 114 entries showed in English the same definition of Lewis and Short
  as another entry of the same word (*subsisto*, *agmen*), because 3.3
  had missed copies that differed only in capitals. Now only the entry
  it belongs to has it, and the others have their own meanings again.
- The RPM signing key is pinned in `packaging/build-rpm.sh`, which signs
  only with it and says how to import it when it is missing;
  `release.py --rpm` checks for it first. The next day it was replaced
  by a new key, `8187 0643 CA22 1AF9 0C30 554E BE68 32CD 3599 4948`
  (ed25519, valid until 2029), whose public key is in
  `packaging/RPM-GPG-KEY-py-words`.

## 3.11 — 2026-11-11

- On a hi-res display with the desktop scaled (at 200% in Plasma, for
  example), the windows of the AppImage came out very small: its Tk 8.6
  ignored the scaling that the desktop gives to X11 programs
  (`Xft.dpi`). Now the windows read it, and their text and size grow
  with it. The RPM, with the system's Tk 9, was already right.
- `tools/release.py --rpm` also sends the signed source RPM to Copr
  (`--no-copr` does not), and the RPMs are always signed. The READMEs
  give the installation from Copr first.

## 3.10 — 2026-11-11

- **An RPM package for Fedora** (`packaging/`), signed and attached to
  the releases with its public key. It installs the program in
  `/usr/share/py-words`, the `py-words` command (with the commands of
  the AppImage), the four menu entries and the icon. `build-rpm.sh
  --sign` signs it and refuses to pack a private key, and
  `tools/release.py --rpm` builds it and attaches it.
- The web page ends with the logo of the Universidad de los Andes
  (School of Arts and Humanities) and its legal notice, as the
  university asked.
- The former address of the site, <https://nicolasvaughan.org/py-words/>,
  sends to <https://nivaca.pythonanywhere.com/> with the search; the
  version that runs in the browser is now at `browser/`.

## 3.9 — 2026-11-09

- `words_web.py` can serve everyone: `public_app()` (the WSGI
  application for a web server, such as PythonAnywhere) and `--public`
  keep each visitor's settings, languages, dark mode and earlier
  searches in the cookies of their browser, and save nothing on the
  server. With no cookies, the page follows the language of the browser.

## 3.8 — 2026-11-06

- In the window, changing the language of the interface no longer
  leaves the parts of the window built before tied to the changes of the
  look and of the fonts, which gave errors after each change.
- If the file of a language of the interface is wrong, the window stays
  in the language it was in and says why in the status bar. Before, it
  went on in English without a word.

## 3.7 — 2026-11-06

- `words_install.py --uninstall` removes on Linux only the `.desktop`
  entries and the icons (`py-words.png` and `.svg`, in every size that
  is installed, even one the program no longer has), and nothing else.
  `icons/linux/uninstall.sh` removes the same, by their exact names.
- The titles, the web page and the menu entries say "A Latin Dictionary"
  ("Un diccionario de latín" in Spanish).

## 3.6 — 2026-11-05

- `words_install.py --only-gui` adds only the window's menu entry, and
  removes the other three if they were there.
- The scripts that make the zip and the AppImage are now in `tools/`:
  `tools/bundle-zip.py` and `tools/bundle-appimage.py`.
- `tools/icons.py` makes all the icons in `icons/` from
  `icons/py-words.svg`, with Inkscape and Pillow.

## 3.5 — 2026-11-03

- **An AppImage for Linux**: one file, with a Python of its own (with
  Tk), that runs without installing anything. It starts the window, and
  a first argument chooses another program (`cli`, `tui`, `web`, `edit`
  ...). `bundle-appimage.py` makes it, and a workflow on GitHub adds it
  to the release of each pushed tag.
- `bundle-zip.py` writes the zip in `dist/`, and the AppImage goes there
  too.
- The dictionary cannot be edited where its data folder cannot be
  written to, as in the AppImage: "Edit dictionary…" is greyed out, and
  the editors say why instead of failing when they save.
- The version is shown in the title of the window and of the editors,
  and at the start of the interactive mode.
- `tools/release.py` makes a release on GitHub and Codeberg.

## 3.4 — 2026-10-31

- With the medieval spellings, the e of a word that is found may also be
  ae or oe: *queruntur* gives *queror*, and also *quaeruntur*, of
  *quaero*. Only frequent entries are added, and not for a final e, so
  *esse*, *bene* or *ille* give nothing more.
- The windows look better. On Linux, light mode has the colours of the
  web page instead of Tk's plain grey theme; in both modes "Look up" is
  in the colour of the accent, the check boxes have a tick, and the
  results have more room.
- The window looks up the words given on its command line
  (`python3 words_gui.py perspicio`; with `-e`, to Latin).
- Some words showed the same meaning twice (*diligo*, *abnego*, *os*): a
  definition of De Miguel or of Lewis and Short had been given to every
  entry with the same stems. Now only the entry it belongs to has it,
  and 1,935 Spanish and 1,040 English meanings are again those of their
  own entries. The README lists this fix under 3.3, as it was made
  before the version number changed.
- In the search to Latin, the meanings no longer show the bars (|) with
  which WORDS marks the further senses of a word.
- In the web page too, the commit in "About" is a link. The README
  presents krunner-py-words, which puts the dictionary in KRunner.

## 3.3 — 2026-10-26

- "About" (in the window, the terminal, the web page, `~A` and
  `--version`) gives the commit the program comes from, as the address
  of that commit on GitHub; in the window it is a link with the short
  hash. The zip and the web site carry it in a file `COMMIT`.
- The Help menu of the window has "Web page", which opens the project
  page on GitHub.
- The documents, "About", the help and `--help` say that WORDS was the
  starting point, that its code and data were redesigned, and that
  py-words now includes a new English dictionary (Lewis and Short) and
  two new Spanish ones (Echave-Sustaeta and De Miguel).

## 3.2 — 2026-10-25

This tag also carries 3.1, which had no tag of its own.

### Added

- **The dictionary has 93,370 entries.** Lewis and Short gave 6,653 rare
  words and 1,783 names, R. de Miguel's *Nuevo diccionario latino-español
  etimológico* (1867) 25,149 words and names, and Latham 16,995 more
  medieval words.
- The Spanish meanings come from De Miguel (50,678, his whole
  definitions, in his spelling) and from Echave-Sustaeta (168) where
  they have the word; the other 42,515 are translations. The results
  name the source after the meaning: "(De Miguel)".
- The English meanings come from Lewis and Short (31,755) where he has
  the word and the sense; the others are those of WORDS. The results say
  "(Lewis and Short)" after them.
- In 3.1, the online version starts with a loading bar, and its zip is
  smaller (3.2 MB instead of 4.4): the meanings in French, German,
  Catalan and Galician were downloaded only when their language was
  chosen.

### Changed

- Only English and Spanish remain as languages of the meanings; those
  in French, German, Catalan and Galician, from Collatinus, are taken
  out.
- There are 18 settings instead of 33, in three groups: some became one,
  some are now always on, others got clearer names. `show_examples`,
  `unknowns_only` and `word_list_check` are gone. Configuration files
  with the old names are still read.
- The environment variables are now `$PY_WORDS_DATADIR`,
  `$PY_WORDS_CONFIG`, `$PY_WORDS_HISTORY` and `$PY_WORDS_CACHE`; the old
  `$WHITAKERS_WORDS_...` still work.
- New icons. The tests of the windows run under Xvfb.

## 3.0 — 2026-10-23

This tag also carries 2.16, which had no tag of its own; the new first
number marks the changes of 2.16.

### Added

- **The long vowels.** The forms show them in the stem and in the
  ending (*amīc-ōrum*, *am-ābat*, *ros-ā*), from the lemmas and the
  models of Collatinus, by Yves Ouvrard and Philippe Verkerk. The new
  file `data/quantities.xml` has the stems, and the endings have an
  attribute `long` in `data/inflections.xml`; the parameter
  `show_long_vowels` hides them.
- The meanings can also be in French, German, Catalan and Galician,
  taken from the lemmas of Collatinus.
- Medieval spellings are recognized in a more general way (*michi*,
  *ecclesie*, *hystorie*), the prodelision of est is understood
  (*amatust*, *bonumst*), and two words declined together
  (*rempublicam*) give only the forms that agree. Six abbreviations
  (*Agr.*, *Kalen.* ...) and the form *quaesumus* were added: 44,386
  entries.
- The program says where its dictionary comes from (WORDS, Latham,
  Echave-Sustaeta and Collatinus) and under which licence, in "About", in
  a new last section of the help, "Sources and licence", in the README
  and in `docs/`. The dictionaries and people that Collatinus thanks are
  thanked here too.

### Changed

- **The licence is now the GNU General Public License, version 3 or
  later** (until 2.15, the MIT License), so that py-words can take code
  and data from Collatinus.
- The settings that wrote the files WORD.OUT, WORD.UNK and WORD.STA are
  taken out, with the files. `-o FILE` keeps the results in a file; a
  configuration file that still has these settings is read without
  complaint.
- Dark mode is chosen with a moon (☾), which becomes a sun (☀) while the
  window or the page is dark, instead of the box "Dark mode".
- The button "Usual settings" is now "Default settings".

## 2.15 — 2026-10-22

This tag also carries 2.14.

- The dictionary was compared with the medieval word-list of R. E.
  Latham, and it now has 44,380 entries (39,846 before), all with their
  Spanish meanings: 2,444 medieval senses of words it had, 21 corrected
  meanings, 1,140 new words and parts of speech, and 1,204 spelling
  variants, with the source code M.
- In 2.14, the dictionary was compared with the Latin-Spanish basic
  vocabulary of J. Echave-Sustaeta: 321 entries were corrected and 254
  added, in English and in Spanish, with the new source code A.
- An entry can have several sources (`source="O M"`), and the codes show
  them with "+" (`[XXXCO+M]`); the dictionary editors have a field
  "other sources", and `words_check.py` checks each one.
- The menus of the window follow the dark mode too.
- `tools/screenshots.py` makes the pictures of the README.

## 2.13 — 2026-10-22

- First version in this repository: py-words, a Latin-English-Latin and
  Latin-Spanish-Latin dictionary, made from WORDS, the program of William
  Whitaker, with its code and data redesigned in Python. It analyses
  Latin words and finds the Latin for English or Spanish words, in a
  window (`words_gui.py`), on the command line (`words.py`), full-screen
  in the terminal (`words_tui.py`) and in a web browser
  (`words_web.py`), with two dictionary editors.
- The Spanish texts of the programs and of the README address the user
  with "usted" and not with "tú".

## 1.0 to 2.12 — before 2026-10-22

These versions came before the repository and have no dates.

- 2.12: the window is easier to read: the word looked up is bigger, the
  dictionary form is in bold, and the codes, forms and notes have other
  colours. A click on the first word of an entry, or a double click on
  any word, looks it up; the codes and the analyses explain themselves
  under the mouse. Three menus instead of four buttons, a right-click
  menu and Ctrl and F in the results. The web page has the same, from
  `layout.py`.
- 2.11: words written with long marks, breves, diaereses or the
  ligatures æ and œ are read correctly (*amīcus* was looked up as "am"
  and "cus").
- 2.10: "Fuzzy search" is a box on the main screen of the window and of
  the web page.
- 2.9: the online version starts more quickly, with the cache of the
  dictionary kept in the browser (IndexedDB).
- 2.8: a help guide in each program (`guide.py`): "Help", F1, `~H` and
  `--guide`.
- 2.7: **a fuzzy search**: when a word of three letters or more finds
  nothing, the results of three near spellings at most come after it
  ("amicuss" finds *amicus*); `--no-fuzzy` turns it off.
- 2.6: the online version picks up a new version on the next visit.
- 2.5: the dictionary is online, at <https://nicolasvaughan.org/py-words/>,
  published on GitHub Pages at each push.
- 2.4: a first version that works in the browser, without a server
  (Pyodide).
- 2.3: the screenshots of the Spanish README show the programs in
  Spanish.
- 2.2: dark mode for the windows and the web page.
- 2.1: **the complete dictionary in Spanish**, translated from the
  English, and the interface in Spanish (`data/interface/es.xml`). The
  editors edit the meanings in another language too. `README_es.md`.
- 2.0: the meanings can be in languages other than English, one file for
  each language in `data/languages/`; each entry, irregular form and
  affix has a stable `id`.
- 1.8: `words_web.py`, the dictionary in a web browser from a small
  local server; the analysis written in plain Python, without the
  structures kept from the Ada program.
- 1.7: `words_tui.py`, the dictionary full-screen in the terminal.
- 1.6: the searches are remembered between sessions and shared by the
  command line and the window.
- 1.5: a "Settings…" dialogue in the window; the parameter `use_glosses`.
- 1.4: the analyses are written with the abbreviations of the Leipzig
  Glossing Rules (`GEN.PL`, `2SG.PRF.ACT.IND`), kept in `data/gloss.xml`.
- 1.3: corrected dictionary forms of numerals with one stem and English
  examples of the subjunctive; more regression tests.
- 1.2: the two dictionary editors share one implementation (`editor.py`),
  and three of their bugs are corrected.
- 1.1: the dictionary editors no longer lose changes; the names of the
  sources are kept in `data/sources.xml`.
- 1.0: first public version: WORDS, the Latin dictionary of William
  Whitaker, in Python, from its Ada version, with its data in XML.
