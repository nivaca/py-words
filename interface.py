"""The language of the interface: the menus, buttons, labels, messages and
help of the programs.  (The results are in the language of the meanings:
see languages.py.)

The interface is written in English.  Another language has a file next
to the program, data/interface/CODE.xml (see words.xsd):

    <interface code="es" name="Spanish" native="Español">
      <text>
        <en>Save these settings?</en>
        <tr>¿Guardar estos ajustes?</tr>
      </text>
      ...
    </interface>

A text is found by its English, with its spaces made single (so a text
may be laid out on several lines); the translation is shown as it is
written.  A text may have named parts, as "Saved in {path}", which tr()
fills in; the translation has the same parts.  What the file does not
translate is shown in English.

The language is the setting `interface` of the configuration file
([parameters]; en unless it says otherwise).  The programs call use()
when they start, and again when it is changed.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

REFERENCE = 'en'
FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data',
                      'interface')
PART = re.compile(r'\{(\w+)\}')

_code = REFERENCE
_texts: dict[str, str] = {}


class InterfaceError(Exception):
    """A file of the interface that cannot be read."""


def files() -> dict[str, str]:
    """{code: path} of the languages of the interface besides English."""
    try:
        names = sorted(os.listdir(FOLDER))
    except OSError:
        return {}
    return {name[:-4]: os.path.join(FOLDER, name) for name in names
            if name.endswith('.xml')}


def names() -> dict[str, str]:
    """{code: name} of the languages of the interface, each in itself
    (English, Español ...)."""
    out = {REFERENCE: 'English'}
    for code, path in files().items():
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError):
            continue
        out[code] = root.get('native') or root.get('name') or code
    return out


def read(path: str) -> dict[str, str]:
    """The texts of the interface file PATH: {English: translation}
    (raises InterfaceError)."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as e:
        raise InterfaceError(f'{path}: {e}') from None
    if root.tag != 'interface':
        raise InterfaceError(f'{path}: the root element must be '
                             '<interface>')
    texts = {}
    for item in root:
        english, translation = item.find('en'), item.find('tr')
        if item.tag != 'text' or english is None or translation is None:
            raise InterfaceError(f'{path}: each <text> needs an <en> and a '
                                 '<tr>')
        key = key_of(english.text or '')
        value = translation.text or ''
        if sorted(PART.findall(key)) != sorted(PART.findall(value)):
            raise InterfaceError(f'{path}: the parts of "{key}" are not '
                                 'those of its translation')
        if key in texts:
            raise InterfaceError(f'{path}: "{key}" is there twice')
        texts[key] = value
    return texts


def key_of(english: str) -> str:
    return ' '.join(english.split())


def use(code: str | None) -> bool:
    """Shows the interface in language CODE (English if None, or if there
    is no such language or its file is wrong).  Returns whether CODE is
    the one in use."""
    global _code, _texts
    path = files().get(code or '')
    texts = {}
    if path is not None:
        try:
            texts = read(path)
        except InterfaceError:
            path = None
    _code = code if path is not None else REFERENCE
    _texts = texts
    return _code == (code or REFERENCE)


def use_configured() -> str:
    """Uses the language of the configuration file (before the settings
    are read: the programs call this first, for their help).  Returns its
    code."""
    import config
    try:
        code = config.read().get('parameters', {}).get('interface')
    except config.ConfigError:
        code = None
    use(code if isinstance(code, str) else None)
    return _code


def code() -> str:
    """The language of the interface in use."""
    return _code


#  Ojo: todo texto nuevo con tr() o N_() necesita su entrada en
#  data/interface/es.xml, o falla test_interface.  Y si sobra una, también.
def tr(english: str, /, **parts) -> str:
    """ENGLISH, a text of the interface, in the language in use, with its
    PARTS ({path} ...) filled in."""
    text = _texts.get(key_of(english)) if _texts else None
    if text is None:
        text = english
    else:                       # (with the spaces around the English)
        stripped = english.strip()
        if stripped:
            start = english.index(stripped[0])
            text = english[:start] + text.strip() + \
                english[start + len(stripped):]
    return text.format(**parts) if parts else text


def N_(english: str) -> str:
    """Marks a text to be translated where it is shown (with tr): the
    texts of tables made when the program starts."""
    return english


def translate_argparse() -> None:
    """Makes argparse write its own texts (usage:, options ...) in the
    language in use."""
    import argparse
    argparse._ = tr
    argparse.ngettext = lambda one, many, n: tr(one if n == 1 else many)


def yes(answer: str | None) -> bool:
    """Whether ANSWER, typed to a question that says (y/n), is yes (in
    English or in the language in use: s, sí)."""
    first = (answer or '').strip().lower()[:1]
    return bool(first) and first in ('y', tr('y').lower()[:1])


def translate_tk(root) -> None:
    """Tk's own dialogues (Yes, No, Cancel ...) in the language in use, if
    Tk has it."""
    try:
        root.tk.call('package', 'require', 'msgcat')
        root.tk.call('::msgcat::mclocale', _code)
    except Exception:               # (tkinter.TclError: no msgcat)
        pass
