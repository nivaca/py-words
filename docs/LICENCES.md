Open-source software used by py-words
=====================================

py-words itself is under the GNU General Public License, version 3 or
later (GPL-3.0-or-later; see [LICENCE.txt](../LICENCE.txt)).  This list
gives the other free and open-source software it uses, with the licence
of each one, as SPDX identifiers where there is one.  The books and data
that the dictionary comes from (Lewis and Short, De Miguel,
Echave-Sustaeta, Latham ...) are not software; the README lists them, with
their licences, under "Sources".

The licences were taken from each project's own licence file or package
metadata, in November 2026.  If one of these projects changes its licence,
its own files say what holds.


1. What the program runs on
---------------------------

These are needed to run py-words, from the zip, the RPM, the .deb or a clone.
py-words does not include them: they come with Python or with the system.

| Software | What py-words uses it for | Licence |
|---|---|---|
| [Python](https://www.python.org) 3.13 or later, with its standard library | everything: py-words uses only the standard library, with no other Python packages | Python Software Foundation License, version 2 (`Python-2.0.1`); some modules of the standard library carry their own permissive licences (MIT, BSD, Apache-2.0 ...) |
| [Tcl/Tk](https://www.tcl-lang.org), through `tkinter` | the window (`words_gui.py`) and the dictionary editor in a window (`words_edit_gui.py`) | Tcl/Tk licence (`TCL`), a BSD-style licence |
| [ncurses](https://invisible-island.net/ncurses/), through `curses` (Linux and macOS) | the terminal in full screen (`words_tui.py`) and the editor in the terminal (`words_edit.py`) | MIT-style (`MIT-open-group`) |
| [windows-curses](https://github.com/zephyrproject-rtos/windows-curses) (Windows only; installed apart) | `curses` on Windows, for the same two programs | Python Software Foundation License; it is built on PDCurses, which is in the public domain |


2. Code and data taken into py-words
------------------------------------

Parts of these are inside py-words, in its code or in `data/`.

| Software | What py-words took from it | Licence |
|---|---|---|
| [WORDS](https://github.com/mk270/whitakers-words), by William Whitaker (1936-2010), in the Ada version maintained by mk270 | the starting point: the analyses, the inflections, the irregular forms and the original entries of the dictionary | Whitaker's permission "for any and all use of program and data" (quoted in full in LICENCE.txt) |
| [Collatinus](https://github.com/biblissima/collatinus) 11, by Yves Ouvrard and Philippe Verkerk | the long vowels of the stems and of the endings (from its inflection models), six abbreviations, the form quaesumus and the ideas of some tricks | GNU GPL: its source files say version 2 or later, and the project now distributes it under version 3 |
| [py-logeion](https://github.com/nivaca/py-logeion) 0.2.1, by Nicolas Vaughan | the code that asks Logeion and shows its entries (`logeion_api.py`, `logeion_entry.py`, `logeion_render.py`, `logeion_dom.py`, `logeion_text.py`) | GNU GPL, version 3 or later (`GPL-3.0-or-later`) |


3. Inside the AppImage
----------------------

The AppImage carries its own Python, so it holds copies of these.

| Software | What it is in the AppImage | Licence |
|---|---|---|
| Python, as built by [python-appimage](https://github.com/niess/python-appimage) | the Python 3.13 of the AppImage, with Tcl/Tk and ncurses | Python itself under the Python Software Foundation License; the python-appimage tool under the GNU GPL, version 3 (`GPL-3.0`), and its `AppRun` and other files under the MIT License |
| Tcl/Tk and ncurses, inside that Python | as in section 1 | `TCL`; `MIT-open-group` |
| the terminal descriptions (terminfo) of ncurses | copied from the system when the AppImage is made, so that its older ncurses can read them | `MIT-open-group` |
| [appimagetool](https://github.com/AppImage/appimagetool) and the [AppImage runtime](https://github.com/AppImage/type2-runtime) | the tool that makes the AppImage, and the small program at its start that mounts and runs it | MIT License (`MIT`) |


4. The RPM and the .deb
-----------------------

The RPM and the .deb install only py-words; Fedora, Debian or Ubuntu
provide what they need.  The .deb is made with Python's standard library
alone, so it needs no Debian tool.

| Software | What for | Licence |
|---|---|---|
| python3 and python3-tkinter (Fedora) | needed by the RPM, as in section 1 | `Python-2.0.1`; Tcl/Tk: `TCL` |
| [hicolor-icon-theme](https://gitlab.freedesktop.org/xdg/default-icon-theme) | needed by the RPM: the folders of the icons | GNU GPL, version 2 or later (`GPL-2.0-or-later`) |
| [rpm-build](https://rpm.org) and rpm-sign | making the RPM and signing it | `GPL-2.0-or-later` |
| [desktop-file-utils](https://www.freedesktop.org/wiki/Software/desktop-file-utils/) | installing and checking the menu entries while the RPM is made | `GPL-2.0-or-later` |
| [GnuPG](https://gnupg.org) | the key that signs the RPM | GNU GPL, version 3 or later (`GPL-3.0-or-later`), with parts under the LGPL and other free licences |
| [copr-cli](https://github.com/fedora-copr/copr) | sending the RPM to be built in Fedora's Copr | `GPL-2.0-or-later` |
| python3 and python3-tk (Debian, Ubuntu) | needed by the .deb, as in section 1 | `Python-2.0.1`; Tcl/Tk: `TCL` |
| hicolor-icon-theme (Debian, Ubuntu) | recommended by the .deb: the folders of the icons | `GPL-2.0-or-later` |
| GnuPG | the detached signature of the .deb, with the same key | `GPL-3.0-or-later` |


5. Tools used to make py-words
------------------------------

These are used only to develop, test and publish py-words; none of them
is in what is distributed.

| Software | What for | Licence |
|---|---|---|
| [Xvfb](https://www.x.org) (X.Org) | a virtual display for the tests of the windows and for the screenshots | MIT License and GNU GPL, version 2 (`MIT AND GPL-2.0-only`) |
| [tmux](https://github.com/tmux/tmux) | running the terminal programs out of sight for the screenshots | ISC License (`ISC`) |
| [ImageMagick](https://imagemagick.org) | taking, joining and trimming the screenshots | ImageMagick License (`ImageMagick`), based on the Apache License 2.0 |
| [Inkscape](https://inkscape.org) | drawing the icons in every size from `icons/py-words.svg` | GNU GPL, version 3 or later, for the program as a whole (most of its code is under version 2 or later) |
| [Pillow](https://python-pillow.org) | putting the Windows icon (`.ico`) together | MIT-CMU License (`MIT-CMU`) |
| [Git](https://git-scm.com) | the history of the code | GNU GPL, version 2 (`GPL-2.0-only`) |
| [GitHub CLI](https://github.com/cli/cli) (`gh`) | publishing the releases on GitHub | MIT License (`MIT`) |
| [tea](https://gitea.com/gitea/tea) | publishing the releases on Codeberg | MIT License (`MIT`) |
| [actions/checkout](https://github.com/actions/checkout) and [actions/setup-python](https://github.com/actions/setup-python) | the tests on GitHub at each push | MIT License (`MIT`) |
| [DejaVu fonts](https://dejavu-fonts.github.io) | the fonts of the tests of the windows on GitHub | Bitstream Vera licence, and public domain for the DejaVu changes |

`tools/screenshots.py` also uses a Chrome browser for the picture of the
web page.  Google Chrome is not open-source software; Chromium, under the
BSD-3-Clause licence and others, works the same, and the script uses it
when Chrome is not there.


Logeion
-------

The entries that py-words shows from
[Logeion](https://logeion.uchicago.edu) are asked of that service, of the
University of Chicago, over the internet.  No software or data of Logeion
is distributed with py-words; its dictionaries (Lewis and Short, Gaffiot,
the DMLBS ...) are under the terms of their own publishers.
