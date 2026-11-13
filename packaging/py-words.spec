# py-words, a Latin dictionary and parser.
# Copyright (C) 2026 Nicolas Vaughan <nivaca@fastmail.com>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENCE.txt file, or <https://www.gnu.org/licenses/>.
#
# Build with packaging/build-rpm.sh, which makes the source tarball.

Name:           py-words
Version:        3.13
Release:        1%{?dist}
Summary:        Latin dictionary and parser (Latin-English and Latin-Spanish)

# The code is GPL-3.0-or-later. In data/: the Lewis and Short meanings are
# CC BY-SA 4.0 (the Perseus text); William Whitaker's WORDS data are free
# for any use. See LICENCE.txt and the README.
License:        GPL-3.0-or-later AND CC-BY-SA-4.0
URL:            https://github.com/nivaca/py-words
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils

Requires:       python3 >= 3.11
# The window (words_gui.py) and the dictionary editor's window are Tk.
Requires:       python3-tkinter
Requires:       hicolor-icon-theme

%description
py-words is a Latin dictionary that parses inflected Latin words: it gives
each form's analysis (case, number, tense ...) and the dictionary entry
with its meanings, in English or Spanish, and looks up words the other
way round. It started from WORDS by William Whitaker, with a redesigned
program and data, a new English dictionary (Lewis and Short) and two new
Spanish ones (Echave-Sustaeta and De Miguel).

It comes as a window, a command line, a full-screen terminal program and
a web page served on this computer, all started by the py-words command.

%prep
%autosetup -n %{name}-%{version}

%build
# Nothing to build: the program is Python.

%install
# The program: the top-level modules and what they read (data/ and the
# icons), not the tests, tools, docs or the site. words_install.py adds
# menu entries for a checkout; the package has its own.
install -d %{buildroot}%{_datadir}/%{name}
for f in *.py; do
    [ "$f" = words_install.py ] && continue
    install -pm 0644 "$f" %{buildroot}%{_datadir}/%{name}/
done
[ -f COMMIT ] && install -pm 0644 COMMIT %{buildroot}%{_datadir}/%{name}/
cp -pr data %{buildroot}%{_datadir}/%{name}/
install -d %{buildroot}%{_datadir}/%{name}/icons/linux/icons
install -pm 0644 icons/py-words.svg icons/uniandes.svg \
    %{buildroot}%{_datadir}/%{name}/icons/
cp -pr icons/linux/icons/hicolor \
    %{buildroot}%{_datadir}/%{name}/icons/linux/icons/
# Compiled now: users cannot write next to the modules, so Python would
# otherwise compile every module on every start.
%py_byte_compile %{python3} %{buildroot}%{_datadir}/%{name}

install -d %{buildroot}%{_bindir}
sed -e 's|@DATADIR@|%{_datadir}/%{name}|' -e 's|@PYTHON@|%{python3}|' \
    packaging/py-words-launcher.in > %{buildroot}%{_bindir}/py-words
chmod 0755 %{buildroot}%{_bindir}/py-words

for f in packaging/*.desktop; do
    desktop-file-install --dir=%{buildroot}%{_datadir}/applications "$f"
done
install -d %{buildroot}%{_datadir}/icons
cp -pr icons/linux/icons/hicolor %{buildroot}%{_datadir}/icons/

%check
for f in %{buildroot}%{_datadir}/applications/*.desktop; do
    desktop-file-validate "$f"
done
! grep -l '@[A-Z]*@' %{buildroot}%{_bindir}/py-words
# The installed command line finds its data and parses a word, with no
# settings or cache of the builder's.
export HOME="$PWD/check-home" PY_WORDS_CACHE= PY_WORDS_CONFIG="$PWD/check-home/config"
sed -e 's|@DATADIR@|%{buildroot}%{_datadir}/%{name}|' -e 's|@PYTHON@|%{python3}|' \
    packaging/py-words-launcher.in > check-py-words
out="$(bash check-py-words cli --interface en amo)"
echo "$out" | grep -q 'love'
bash check-py-words cli --version | grep -q '%{version}'

%files
%license LICENCE.txt
%doc README.md README_es.md docs/DESCRIPTION.md docs/DESCRIPCIÓN_es.md
%{_bindir}/py-words
%{_datadir}/%{name}/
%{_datadir}/applications/py-words.desktop
%{_datadir}/applications/py-words.cli.desktop
%{_datadir}/applications/py-words.tui.desktop
%{_datadir}/applications/py-words.web.desktop
%{_datadir}/icons/hicolor/*/apps/py-words.*

%changelog
* Fri Nov 13 2026 Nicolas Vaughan <nivaca@fastmail.com> - 3.13-1
- An entry is shown once per word, with all its forms: a verb's forms and
  its participles together, and entries that show the same only once

* Fri Nov 13 2026 Nicolas Vaughan <nivaca@fastmail.com> - 3.12-1
- Entries of the same word with the same forms show them once; 114 English
  meanings that repeated another entry's are their own again

* Wed Nov 11 2026 Nicolas Vaughan <nivaca@fastmail.com> - 3.11-1
- The windows follow the desktop's scaling (Xft.dpi) on hi-res displays

* Wed Nov 11 2026 Nicolas Vaughan <nivaca@fastmail.com> - 3.10-1
- First package: runs on the system's Python and Tk; the py-words
  command starts the window, the command line, the terminal program,
  the web page or the editor, as the AppImage does
- The web page ends with the logo and legal notice of the Universidad de
  los Andes
