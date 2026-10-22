"""Tests of the language of the interface (interface.py and the files in
data/interface/): the translations, and that every text of the programs
is translated."""

import ast
import glob
import io
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere
import isolate  # noqa: F401,E402  (before anything that reads settings)

import interface  # noqa: E402
from interface import tr, yes  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#  argparse's own texts (see interface.translate_argparse)
ARGPARSE = ['usage: ', 'positional arguments', 'options',
            'show this help message and exit', ' (default: %(default)s)',
            'argument %(argument_name)s: %(message)s',
            'unrecognized arguments: %s',
            'the following arguments are required: %s',
            'expected one argument', 'expected at most one argument',
            'expected at least one argument',
            'invalid choice: %(value)r (choose from %(choices)s)',
            'invalid %(type)s value: %(value)r',
            'not allowed with argument %s',
            'ambiguous option: %(option)s could match %(matches)s',
            "can't open '%(filename)s': %(error)s",
            '%(prog)s: error: %(message)s\n']


def program_texts() -> set[str]:
    """The texts of the interface: those given to tr() and N_() in the
    program (but not in forms.py, whose tr is that of the results), and
    those of the tables translated where they are shown."""
    import editor
    import settings
    import version
    import words_edit
    import words_tui
    import words_web
    from xmldata import read_language
    texts = []
    for path in sorted(glob.glob(os.path.join(ROOT, '*.py'))):
        if os.path.basename(path) == 'forms.py':
            continue
        with open(path, encoding='utf-8') as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and \
                    isinstance(node.func, ast.Name) and \
                    node.func.id in ('tr', 'N_') and node.args and \
                    isinstance(node.args[0], ast.Constant):
                texts.append(node.args[0].value)
    texts += editor.FIELD_LABELS.values()
    texts += [d for _, d in editor.POS_CHOICES]
    for labels in editor.STEM_LABELS.values():
        texts += labels
    for table in editor.DESCRIPTIONS.values():
        texts += table.values()
    texts += [n.replace('_', ' ').capitalize()
              for n in settings.MODES + settings.DEV_MODES +
              tuple(a for _, a in settings.CHARACTERS)]
    for path in glob.glob(os.path.join(ROOT, 'data', 'languages', '*.xml')):
        texts.append(read_language(path).name)
    texts += ['word', 'error', 'warning', 'Added', 'Changed', 'stem',
              'form', 'fix', 'y', words_tui.HELP_TEXT,
              words_tui.__doc__.split('\n\n')[3], words_edit.HELP_TEXT]
    texts += words_web.__doc__.split('\n\n')[1:]
    texts += ARGPARSE
    texts += [version.CREDITS_TEXT, version.AUTHOR]
    return {interface.key_of(t) for t in texts if t.strip()}


class TranslationTests(unittest.TestCase):

    def tearDown(self):
        interface.use('en')

    def test_every_text_is_translated(self):
        for code, path in interface.files().items():
            translated = set(interface.read(path))
            needed = program_texts()
            self.assertEqual(sorted(needed - translated), [],
                             f'{code}: not translated')
            self.assertEqual(sorted(translated - needed), [],
                             f'{code}: not used')

    def test_tr(self):
        self.assertTrue(interface.use('es'))
        self.assertEqual(interface.code(), 'es')
        self.assertEqual(tr('Look up'), 'Buscar')
        self.assertEqual(tr('Saved in {path}', path='/x'), 'Guardado en /x')
        self.assertEqual(tr('usage: '), 'uso: ')      # (the spaces kept)
        self.assertEqual(tr('Not a text of the program'),
                         'Not a text of the program')
        self.assertEqual(tr('Not a text {x}', x=1), 'Not a text 1')
        self.assertTrue(yes('sí') and yes('y') and not yes('n'))
        interface.use('en')
        self.assertEqual(tr('Look up'), 'Look up')
        self.assertFalse(yes('s'))

    def test_names_and_unknown_languages(self):
        self.assertEqual(interface.names()['es'], 'Español')
        self.assertFalse(interface.use('xx'))
        self.assertEqual(interface.code(), 'en')

    def test_bad_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'xx.xml')
            for body, message in (
                    ('<text><en>a {x}</en><tr>b</tr></text>', 'parts'),
                    ('<text><en>a</en><tr>b</tr></text>'
                     '<text><en> a </en><tr>c</tr></text>', 'twice'),
                    ('<text><en>a</en></text>', 'needs')):
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(f'<interface code="xx" name="X">{body}'
                            '</interface>')
                with self.assertRaises(interface.InterfaceError) as e:
                    interface.read(path)
                self.assertIn(message, str(e.exception))


class ProgramTests(unittest.TestCase):

    def tearDown(self):
        interface.use('en')

    def test_setting(self):
        from settings import Settings
        s = Settings()
        self.assertEqual(s.apply_config({'parameters': {'interface': 'es'}}),
                         [])
        self.assertEqual(s.interface, 'es')
        self.assertEqual(s.config_section('parameters')['interface'], 'es')

    def test_command_line(self):
        import words
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            words.main(['--interface', 'es', '--help'])
        self.assertIn('uso: words', out.getvalue())
        self.assertIn('mostrar esta ayuda y terminar', out.getvalue())

    def test_web_page(self):
        import words_web
        app = words_web.WebApp(os.path.join(ROOT, 'data'))
        try:
            interface.use('es')
            status = []
            body = b''.join(app({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/',
                                 'QUERY_STRING': ''},
                                lambda s, h: status.append(s))).decode()
        finally:
            app.close()
        self.assertEqual(status, ['200 OK'])
        self.assertIn('<html lang="es">', body)
        self.assertIn('Búsquedas anteriores', body)
        self.assertIn('Idioma de la interfaz', body)



def _display():
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return False
    try:
        import tkinter
        tkinter.Tk().destroy()
        return True
    except Exception:
        return False


class KeptTests(unittest.TestCase):
    """The language of the interface is kept in the configuration file,
    whichever program chooses it, and the others start in it."""

    def setUp(self):
        import config
        self.config = config
        self.tearDown()

    def tearDown(self):
        interface.use('en')
        try:
            os.remove(self.config.config_path())
        except FileNotFoundError:
            pass

    def kept(self) -> str:
        """The language the configuration file keeps (and that a program
        starting now uses)."""
        from settings import Settings
        s = Settings()
        s.load(os.path.join(ROOT, 'data'))
        self.assertEqual(interface.use_configured(), s.interface)
        interface.use('en')
        return s.interface

    def meanings(self) -> str:
        """The language of the meanings the configuration file keeps."""
        return self.config.read()['parameters']['language']

    def test_other_settings_keep_it(self):
        """A program that saves another setting does not put back the
        language it started with."""
        from settings import Settings
        older = Settings()                      # (started in English)
        self.config.update('parameters', {'interface': 'es'})
        older.trim_output = False
        older.save('parameters', only=['trim_output'])
        self.assertEqual(self.config.read()['parameters'],
                         {'interface': 'es', 'trim_output': False})
        self.assertEqual(self.kept(), 'es')

    def test_web_page(self):
        import words_web
        app = words_web.WebApp(os.path.join(ROOT, 'data'))
        try:
            body = f'token={app.token}&interface=es'.encode()
            app({'REQUEST_METHOD': 'POST', 'PATH_INFO': '/interface',
                 'CONTENT_LENGTH': str(len(body)),
                 'wsgi.input': io.BytesIO(body)}, lambda s, h: None)
        finally:
            app.close()
        self.assertEqual(interface.code(), 'es')
        self.assertEqual(self.kept(), 'es')
        self.assertEqual(self.meanings(), 'es')     # (they follow it)

    def test_command_line(self):
        """The # dialogue asks for it, and saves it with the
        parameters."""
        import words
        from lexicon import Lexicon
        from session import Session
        from settings import Settings
        session = Session(Lexicon.load(os.path.join(ROOT, 'data')),
                          Settings(), write=lambda text: None)

        def ask(prompt):
            """Enter keeps each parameter; then es, and save (asked in
            Spanish by then)."""
            if prompt.startswith('INTERFACE'):
                return 'es'
            return 's' if prompt.startswith('¿Guardar') else ''
        words.change_parameters(session, ask, lambda text: None)
        self.assertEqual(interface.code(), 'es')
        self.assertEqual(session.language.code, 'es')
        self.assertEqual(self.kept(), 'es')
        self.assertEqual(self.meanings(), 'es')

    @unittest.skipUnless(_display(), 'needs a display')
    def test_window(self):
        import tkinter as tk
        import words_gui
        root = tk.Tk()
        try:
            app = words_gui.App(root, os.path.join(ROOT, 'data'))
            for _ in range(600):
                if app.session is not None:
                    break
                root.update()
                time.sleep(0.05)
            app.change_setting('interface', 'es')
            self.assertEqual(root.title(), 'py-words: un diccionario de latín')
            self.assertTrue(app.text.get('1.0', 'end').startswith(
                'Escriba una palabra'))     # (the welcome, in Spanish)
            self.assertEqual(app.session.language.code, 'es')
            self.assertEqual(app.language.get(), 'español')
        finally:
            root.destroy()
        self.assertEqual(self.kept(), 'es')


if __name__ == '__main__':
    unittest.main()
