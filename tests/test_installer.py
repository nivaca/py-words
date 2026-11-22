"""Pruebas de tools/bundle-installer.py, que hace los instaladores con un
Python propio, y de lo que ponen: packaging/installer/launcher.py y el
instalador de Linux (install.sh).

No se descarga nada: en lugar del Python de python-build-standalone se
usa uno de mentira, un tarball con python/bin/python3, un script que
corre el Python de las pruebas.  Así, el .run de Linux se hace, se
instala en una carpeta personal temporal, se corre y se quita de verdad.
De Windows y macOS solo se arma la carpeta del instalador (--stage-only):
Inno Setup y pkgbuild no corren aquí (los prueba installers.yml).
"""

import importlib.util
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # el programa, desde cualquier carpeta
import isolate  # noqa: F401,E402  (before anything that reads settings)

from version import VERSION  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'tools', 'bundle-installer.py')
INSTALLER = os.path.join(ROOT, 'packaging', 'installer')


def load(path, name):
    # (el nombre lleva un guion, así que no se puede importar sin más)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bundle = load(SCRIPT, 'bundle_installer')
launcher = load(os.path.join(INSTALLER, 'launcher.py'), 'launcher')


def fake_python(folder: str, system: str = 'linux') -> str:
    """A tarball shaped like those of python-build-standalone, whose
    python3 runs the Python of the tests; also with what is trimmed."""
    python = os.path.join(folder, 'python')
    if system == 'windows':
        lib = os.path.join(python, 'Lib')
        for f in ('python.exe', 'pythonw.exe', 'include/Python.h',
                  'libs/python3.lib', 'Scripts/pip.exe'):
            os.makedirs(os.path.dirname(os.path.join(python, f)),
                        exist_ok=True)
            open(os.path.join(python, f), 'w').close()
    else:
        lib = os.path.join(python, 'lib', 'python3.13')
        os.makedirs(os.path.join(python, 'bin'))
        with open(os.path.join(python, 'bin', 'python3.13'), 'w') as f:
            f.write(f'#!/bin/sh\nexec {sys.executable} "$@"\n')
        os.chmod(os.path.join(python, 'bin', 'python3.13'), 0o755)
        os.symlink('python3.13', os.path.join(python, 'bin', 'python3'))
        os.symlink('pip3', os.path.join(python, 'bin', 'pip'))
        os.makedirs(os.path.join(python, 'include', 'python3.13'))
        for d in ('share/terminfo/x', 'share/man/man1'):
            os.makedirs(os.path.join(python, d))
        open(os.path.join(python, 'share/terminfo/x/xterm'), 'w').close()
        os.makedirs(os.path.join(lib, 'config-3.13-x86_64-linux-gnu'))
    for d in ('test', 'idlelib', 'json', 'site-packages/pip',
              'site-packages/pip-25.0.dist-info'):
        os.makedirs(os.path.join(lib, d))
        open(os.path.join(lib, d, '__init__.py'), 'w').close()
    path = os.path.join(folder, f'python-{system}.tar.gz')
    with tarfile.open(path, 'w:gz') as t:
        t.add(python, arcname='python')
    shutil.rmtree(python)
    return path


def run_builder(*args):
    return subprocess.run([sys.executable, SCRIPT, '--no-extras', *args],
                          capture_output=True, text=True, check=True)


class Names(unittest.TestCase):

    def test_the_names(self):
        self.assertEqual(bundle.name('linux', 'x86_64'),
                         f'py-words-v.{VERSION}-linux-x86_64.run')
        self.assertEqual(bundle.name('windows', 'x64'),
                         f'py-words-v.{VERSION}-windows-x64-setup.exe')
        self.assertEqual(bundle.name('macos', 'arm64'),
                         f'py-words-v.{VERSION}-macos-arm64.pkg')

    def test_older_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            for n in ('py-words-v.1.0-linux-x86_64.run',
                      'py-words-v.1.0-linux-aarch64.run',
                      'py-words-v.1.0-macos-arm64.pkg',
                      bundle.name('linux', 'x86_64')):
                open(os.path.join(tmp, n), 'w').close()
            self.assertEqual(
                [os.path.basename(p)
                 for p in bundle.older(tmp, 'linux', 'x86_64')],
                ['py-words-v.1.0-linux-x86_64.run'])

    def test_file_version(self):
        self.assertRegex(bundle.file_version(), r'^\d+\.\d+\.\d+\.\d+$')
        self.assertTrue(bundle.file_version().startswith(VERSION))

    def test_every_python_has_its_checksum(self):
        for triple in bundle.TRIPLES.values():
            self.assertRegex(bundle.PBS_SHA256[triple], r'^[0-9a-f]{64}$')
        self.assertTrue(bundle.PYTHON_VERSION.startswith(
            bundle.PYTHON_MINOR + '.'))

    def test_an_unknown_architecture(self):
        with self.assertRaises(ValueError):
            bundle.build('windows', 'arm64', tempfile.gettempdir(),
                         python='none.tar.gz', extras=False)


class Launcher(unittest.TestCase):

    def test_usage_lists_every_command(self):
        text = launcher.usage()
        for command, script in launcher.COMMANDS:
            self.assertIn(command, text)
            self.assertIn(script, text)
        self.assertIn('uninstall', text)
        #  (the same commands as the AppImage)
        appimage = load(os.path.join(ROOT, 'tools', 'bundle-appimage.py'),
                        'bundle_appimage')
        self.assertEqual(launcher.COMMANDS, appimage.COMMANDS)

    def test_certificates(self):
        if launcher.WINDOWS:
            self.skipTest('Windows uses its own store')
        env = {'SSL_CERT_FILE': '/x'}
        launcher.certificates(env)
        self.assertEqual(env, {'SSL_CERT_FILE': '/x'})

    def test_tcl_and_tk(self):
        if launcher.WINDOWS:
            self.skipTest('not on Windows')
        with tempfile.TemporaryDirectory() as tmp:
            for d, f in (('tcl8.6', 'init.tcl'), ('tcl9.0', 'init.tcl'),
                         ('tk8.6', 'tk.tcl'), ('tk9.0', 'other')):
                os.makedirs(os.path.join(tmp, 'lib', d))
                open(os.path.join(tmp, 'lib', d, f), 'w').close()
            old = sys.base_prefix
            sys.base_prefix = tmp
            try:
                env = {}
                launcher.tcl_tk(env)
                kept = {'TCL_LIBRARY': 'mine'}
                launcher.tcl_tk(kept)
            finally:
                sys.base_prefix = old
        self.assertEqual(env, {
            'TCL_LIBRARY': os.path.join(tmp, 'lib', 'tcl9.0'),
            'TK_LIBRARY': os.path.join(tmp, 'lib', 'tk8.6')})
        self.assertEqual(kept['TCL_LIBRARY'], 'mine')


@unittest.skipIf(sys.platform == 'win32', 'the installer for Linux needs sh')
class LinuxInstaller(unittest.TestCase):
    """The .run, made once, installed in a temporary home."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tarball = fake_python(cls.tmp.name)
        cls.out = os.path.join(cls.tmp.name, 'out')
        os.makedirs(cls.out)
        run_builder('--system', 'linux', '--arch', 'x86_64', '--python',
                    tarball, '-o', cls.out)
        cls.run_file = os.path.join(cls.out,
                                    bundle.name('linux', 'x86_64'))

    @classmethod
    def tearDownClass(cls):
        for folder, _, _ in os.walk(cls.tmp.name):
            os.chmod(folder, 0o755)
        cls.tmp.cleanup()

    def setUp(self):
        self.home = tempfile.mkdtemp(dir=self.tmp.name)
        self.env = dict(os.environ, HOME=self.home, LANG='C',
                        XDG_DATA_HOME=os.path.join(self.home, 'share'))
        self.env.pop('LC_ALL', None)
        self.env.pop('LC_MESSAGES', None)
        self.prefix = os.path.join(self.home, 'share', 'py-words')
        self.bin = os.path.join(self.home, '.local', 'bin', 'py-words')
        self.apps = os.path.join(self.home, 'share', 'applications')

    def sh(self, *args, check=True, path=None):
        return subprocess.run(['sh', path or self.run_file, *args],
                              env=self.env, capture_output=True, text=True,
                              check=check, stdin=subprocess.DEVNULL)

    def test_it_is_whole(self):
        self.assertIn('is whole', self.sh('--check').stdout)
        with open(self.run_file, 'rb') as f:
            head = f.read(4096).decode('utf-8', 'replace')
        self.assertTrue(head.startswith('#!/bin/sh\n'))
        self.assertIn(f"VERSION='{VERSION}'", head)
        self.assertNotRegex(head.split('\n# --- Mensajes')[0], r'@[A-Z_]+@')
        self.assertTrue(os.stat(self.run_file).st_mode & stat.S_IXUSR)

    def test_a_damaged_one(self):
        damaged = os.path.join(self.home, 'damaged.run')
        shutil.copy(self.run_file, damaged)
        with open(damaged, 'ab') as f:
            f.write(b'x')
        result = self.sh('--check', check=False, path=damaged)
        self.assertEqual(result.returncode, 1)
        self.assertIn('damaged', result.stderr)

    def test_it_asks_unless_told_not_to(self):
        result = self.sh(check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn('--yes', result.stderr)
        self.assertFalse(os.path.exists(self.prefix))

    def test_install_run_and_uninstall(self):
        self.sh('--yes')
        #  What it installs: the program, its Python, the command, the
        #  four menu entries, the icons and the uninstaller
        for f in ('launcher.py', 'bin/py-words', 'program/words.py',
                  'program/COMMIT', 'python/bin/python3', 'uninstall.sh',
                  '.install-manifest'):
            self.assertTrue(os.path.exists(os.path.join(self.prefix, f)), f)
        self.assertEqual(os.readlink(self.bin),
                         os.path.join(self.prefix, 'bin', 'py-words'))
        self.assertEqual(sorted(os.listdir(self.apps)) and sorted(
            f for f in os.listdir(self.apps) if f.endswith('.desktop')),
            ['py-words.cli.desktop', 'py-words.desktop',
             'py-words.tui.desktop', 'py-words.web.desktop'])
        with open(os.path.join(self.apps, 'py-words.desktop')) as f:
            entry = f.read()
        self.assertIn(f'Exec={self.prefix}/bin/py-words gui\n', entry)
        self.assertIn('Terminal=false\n', entry)
        if shutil.which('desktop-file-validate'):
            subprocess.run(['desktop-file-validate',
                            os.path.join(self.apps, 'py-words.desktop')],
                           check=True)
        icons = os.path.join(self.home, 'share', 'icons', 'hicolor')
        self.assertTrue(os.path.isfile(os.path.join(
            icons, '256x256', 'apps', 'py-words.png')))
        #  Trimmed: no tests or pip in its Python, no words_install.py
        lib = os.path.join(self.prefix, 'python', 'lib', 'python3.13')
        self.assertTrue(os.path.isdir(os.path.join(lib, 'json')))
        for gone in ('test', 'idlelib', 'site-packages/pip',
                     'config-3.13-x86_64-linux-gnu'):
            self.assertFalse(os.path.exists(os.path.join(lib, gone)), gone)
        self.assertFalse(os.path.lexists(os.path.join(
            self.prefix, 'python', 'bin', 'pip')))
        #  (but its curses needs the terminal descriptions)
        self.assertTrue(os.path.isfile(os.path.join(
            self.prefix, 'python', 'share', 'terminfo', 'x', 'xterm')))
        self.assertFalse(os.path.exists(os.path.join(
            self.prefix, 'python', 'share', 'man')))
        self.assertFalse(os.path.exists(os.path.join(
            self.prefix, 'program', 'words_install.py')))
        #  The dictionary cannot be edited (an update would lose it)
        data = os.path.join(self.prefix, 'program', 'data')
        self.assertFalse(os.stat(data).st_mode & stat.S_IWUSR)
        #  It runs
        found = subprocess.run([self.bin, 'cli', '--language', 'en',
                                'amicus'], env=self.env, capture_output=True,
                               text=True, check=True).stdout
        self.assertIn('friend', found)
        self.assertIn('words_tui.py', subprocess.run(
            [self.bin, 'help'], env=self.env, capture_output=True,
            text=True, check=True).stdout)
        #  Again, with only the window: it is replaced
        self.sh('--yes', '--only-gui')
        self.assertEqual(sorted(f for f in os.listdir(self.apps)
                                if f.endswith('.desktop')),
                         ['py-words.desktop'])
        #  py-words uninstall removes all of it, and nothing else
        subprocess.run([self.bin, 'uninstall', '--yes'], env=self.env,
                       capture_output=True, check=True)
        self.assertFalse(os.path.exists(self.prefix))
        self.assertFalse(os.path.lexists(self.bin))
        self.assertEqual([f for f in os.listdir(self.apps)
                          if f.endswith('.desktop')], [])
        self.assertEqual([p for p in os.listdir(icons)
                          if os.listdir(os.path.join(icons, p, 'apps'))], [])

    def test_elsewhere_without_menu_or_command(self):
        prefix = os.path.join(self.home, 'opt', 'py words')
        self.sh('--yes', '--prefix', prefix, '--no-menu', '--no-command')
        self.assertTrue(os.path.isfile(os.path.join(prefix, 'launcher.py')))
        self.assertFalse(os.path.lexists(self.bin))
        self.assertFalse(os.path.exists(self.apps))
        self.sh('--uninstall', '--yes', '--prefix', prefix)
        self.assertFalse(os.path.exists(prefix))

    def test_it_leaves_other_folders_alone(self):
        prefix = os.path.join(self.home, 'mine')
        os.makedirs(prefix)
        open(os.path.join(prefix, 'notes.txt'), 'w').close()
        for args in (('--yes', '--prefix', prefix),
                     ('--uninstall', '--yes', '--prefix', prefix)):
            result = self.sh(*args, check=False)
            self.assertEqual(result.returncode, 1, args)
            self.assertIn('not made by this installer', result.stderr)
        self.assertEqual(os.listdir(prefix), ['notes.txt'])

    def test_extract(self):
        folder = os.path.join(self.home, 'unpacked')
        self.sh('--extract', folder)
        self.assertTrue(os.path.isfile(os.path.join(folder, 'launcher.py')))
        self.assertFalse(os.path.exists(self.prefix))

    def test_in_spanish(self):
        self.env['LANG'] = 'es_CO.UTF-8'
        self.assertIn('Instala el programa', self.sh('--help').stdout)
        self.assertIn('está entero', self.sh('--check').stdout)


class Staged(unittest.TestCase):
    """The folders of the installers for Windows and macOS."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folders = {}
        for system, arch in (('windows', 'x64'), ('macos', 'arm64')):
            tarball = fake_python(cls.tmp.name, system)
            run_builder('--system', system, '--arch', arch, '--python',
                        tarball, '-o', cls.tmp.name, '--stage-only')
            cls.folders[system] = os.path.join(
                cls.tmp.name, f'py-words-{system}-{arch}')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_windows(self):
        image = os.path.join(self.folders['windows'], 'image')
        for f in ('launcher.py', 'py-words.ico', 'bin/py-words.cmd',
                  'program/words_gui.py', 'program/data/dictionary.xml',
                  'program/LICENCE.txt', 'python/pythonw.exe'):
            self.assertTrue(os.path.isfile(os.path.join(image, f)), f)
        for gone in ('include', 'libs', 'Scripts', 'Lib/test',
                     'Lib/site-packages/pip', 'program/words_install.py'):
            self.assertFalse(os.path.exists(os.path.join(image, gone)), gone)
        with open(os.path.join(image, 'bin', 'py-words.cmd'), 'rb') as f:
            command = f.read()
        self.assertIn(b'\r\n', command)
        self.assertIn(b'launcher.py', command)

    def test_the_inno_setup_script(self):
        with open(os.path.join(INSTALLER, 'py-words.iss'),
                  encoding='utf-8') as f:
            iss = f.read()
        image = os.path.join(self.folders['windows'], 'image')
        #  What it names in the folder is there
        for f in re.findall(r'\{#SourceDir\}\\([^"\s]+)', iss):
            if '*' not in f:
                self.assertTrue(os.path.exists(os.path.join(
                    image, *f.split('\\'))), f)
        for f in re.findall(r'\{app\}\\([\w.\\-]+\.(?:py|exe|ico))', iss):
            if f != 'unins000.exe':
                self.assertTrue(os.path.exists(os.path.join(
                    image, *f.split('\\'))), f)
        #  The same values that build_windows gives, and both languages
        for define in ('AppVersion', 'FileVersion', 'SourceDir',
                       'OutputDir', 'OutputName'):
            self.assertIn(define, iss)
        for message in re.findall(r'^english\.(\w+)=', iss, re.M):
            self.assertRegex(iss, rf'(?m)^spanish\.{message}=')
        self.assertIn('{{A9367516-180D-4B55-922F-6353A6F6561F}', iss)

    def test_macos(self):
        work = self.folders['macos']
        app = os.path.join(work, 'roots', 'app', 'py-words.app',
                           'Contents')
        with open(os.path.join(app, 'Info.plist'), 'rb') as f:
            info = plistlib.load(f)
        self.assertEqual(info['CFBundleIdentifier'], bundle.BUNDLE_ID)
        self.assertEqual(info['CFBundleShortVersionString'], VERSION)
        for f in ('MacOS/py-words', 'Resources/launcher.py',
                  'Resources/bin/py-words', 'Resources/uninstall.sh',
                  'Resources/python/bin/python3.13',
                  'Resources/program/words.py', 'Resources/py-words.icns'):
            path = os.path.join(app, f)
            self.assertTrue(os.path.isfile(path), f)
            if f.split('/')[-1] in ('py-words', 'uninstall.sh'):
                self.assertTrue(os.stat(path).st_mode & stat.S_IXUSR, f)
        for kind in ('CLI', 'TUI', 'Web'):
            contents = os.path.join(work, 'roots', 'terminal',
                                    f'py-words ({kind}).app', 'Contents')
            with open(os.path.join(contents, 'Resources',
                                   'run.command')) as f:
                self.assertIn(f'bin/py-words {kind.lower()}\n', f.read())
        link = os.path.join(work, 'roots', 'command', 'usr', 'local', 'bin',
                            'py-words')
        self.assertEqual(os.readlink(link), '/Applications/py-words.app/'
                         'Contents/Resources/bin/py-words')
        self.assertTrue(os.stat(os.path.join(
            work, 'scripts', 'preinstall')).st_mode & stat.S_IXUSR)
        with open(os.path.join(work, 'app.plist'), 'rb') as f:
            self.assertFalse(plistlib.load(f)[0]['BundleIsRelocatable'])

    def test_the_distribution(self):
        work = self.folders['macos']
        tree = ET.parse(os.path.join(work, 'distribution.xml')).getroot()
        self.assertEqual(tree.find('options').get('hostArchitectures'),
                         'arm64')
        refs = {r.get('id'): r.text for r in tree.findall('pkg-ref')}
        self.assertEqual(refs, {f'{bundle.BUNDLE_ID}.{c}': f'{c}.pkg'
                                for c in ('app', 'terminal', 'command')})
        #  Each text has its Spanish, and each page is in both languages
        with open(os.path.join(work, 'resources', 'es.lproj',
                               'Localizable.strings'),
                  encoding='utf-8') as f:
            strings = dict(re.findall(r'^"(.*)" = "(.*)";$', f.read(), re.M))
        for choice in tree.findall('choice'):
            self.assertIn(choice.get('title'), strings)
            self.assertIn(choice.get('description'), strings)
        for lproj in ('en.lproj', 'es.lproj'):
            for page in ('welcome.html', 'conclusion.html', 'LICENCE.txt'):
                path = os.path.join(work, 'resources', lproj, page)
                with open(path, encoding='utf-8') as f:
                    text = f.read()
                self.assertNotIn('@VERSION@', text)
            with open(os.path.join(work, 'resources', lproj,
                                   'welcome.html'), encoding='utf-8') as f:
                self.assertIn(VERSION, f.read())


if __name__ == '__main__':
    unittest.main()
