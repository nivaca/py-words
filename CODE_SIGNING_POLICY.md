Code signing policy
===================

Free code signing provided by [SignPath.io](https://about.signpath.io),
certificate by [SignPath Foundation](https://signpath.org).

What is signed
--------------

The installer for Windows (`py-words-v.VERSION-windows-x64-setup.exe`) is
signed with Authenticode by SignPath Foundation's certificate. It is built
from the source of this repository, at the tag of each release, by the
workflow `.github/workflows/installers.yml` on GitHub's own runners, and it
is sent to SignPath from that same workflow; no installer built anywhere
else is signed. Each signing request is approved by hand.

The software that the installer carries (Python and its standard library,
with Tcl/Tk and the rest, listed with their licences in
[docs/LICENCES.md](docs/LICENCES.md)) is not signed by this project: it is
that of its own maintainers.

Apart from that, every file of every release, the installers too, has a
detached signature (`FILE.asc`) made with the project's own GPG key,
[packaging/RPM-GPG-KEY-py-words](packaging/RPM-GPG-KEY-py-words); see the
README.

Team roles
----------

py-words has one maintainer, who holds every role:

- Committers and reviewers: [Nicolas Vaughan](https://github.com/nivaca)
- Approvers: [Nicolas Vaughan](https://github.com/nivaca)

Changes proposed by anyone else (pull requests) are reviewed by him
before they are merged. Multi-factor authentication is used for GitHub and
for SignPath.

Privacy policy
--------------

This program will not transfer any information to other networked systems
unless specifically requested by the user or the person installing or
operating it.

py-words looks words up in its own dictionary, on the computer itself. It
connects to the internet only when the user chooses Logeion as the source
of the entries (in the window, the terminal interface, the command line or
the web page; the source at first is the program's own dictionary). Then
the words looked up, or their dictionary forms, are sent to Logeion, the
Latin and Greek dictionaries of the University of Chicago
(logeion.uchicago.edu, through anastrophe.uchicago.edu), and what Logeion
records of a request falls under that university's policies. The choice is
kept in the settings until the user changes it back.

The web page of py-words is served by the program itself, and only to this
computer, unless the person running it says otherwise (`--host`).
