"""Tests of words_install.py (the applications menu entry)."""

import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))                        # the program, when run from anywhere

import words_install


class InstallTests(unittest.TestCase):

    #  Each test works in a temporary home folder
    ENV = ('XDG_DATA_HOME', 'HOME', 'APPDATA', 'PATH')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = {k: os.environ.get(k) for k in self.ENV}
        os.environ['XDG_DATA_HOME'] = self.tmp.name
        os.environ['HOME'] = self.tmp.name
        os.environ['APPDATA'] = os.path.join(self.tmp.name, 'AppData')

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_install_and_uninstall(self):
        paths = words_install.install()
        self.assertEqual([os.path.basename(p) for p in paths],
                         ['py-whitaker-words.desktop',
                          'py-whitaker-words.cli.desktop'])
        entries = []
        for path, program in zip(paths, ('words_gui.py', 'words.py')):
            with open(path, encoding='utf-8') as f:
                entry = f.read()
            entries.append(entry)
            self.assertIn('Exec=%s %s\n' % (
                words_install.exec_arg(sys.executable),
                words_install.exec_arg(os.path.join(words_install.HERE,
                                                    program))), entry)
            self.assertNotIn('~', entry)
            if shutil.which('desktop-file-validate'):
                result = subprocess.run(['desktop-file-validate', path],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
                self.assertEqual(result.stdout, b'')
        self.assertIn('Terminal=false', entries[0])
        self.assertIn('Terminal=true', entries[1])
        icons = words_install.icon_files()
        self.assertTrue(icons)
        for _, rel in icons:
            self.assertTrue(os.path.isfile(os.path.join(
                self.tmp.name, 'icons', 'hicolor', rel)))
        removed = words_install.uninstall()
        self.assertEqual(len(removed), len(icons) + 2)
        for path in paths:
            self.assertFalse(os.path.exists(path))

    def test_quoting(self):
        q = words_install.exec_arg
        self.assertEqual(q('/usr/bin/python3'), '/usr/bin/python3')
        self.assertEqual(q('/home/a b/words_gui.py'),
                         '"/home/a b/words_gui.py"')
        self.assertEqual(q('/x/$y'), '"/x/\\$y"')


    def test_icns(self):
        data = words_install.make_icns(words_install.ICONSET)
        self.assertEqual(data[:4], b'icns')
        self.assertEqual(struct.unpack('>I', data[4:8])[0], len(data))
        kinds, pos = [], 8
        while pos < len(data):
            kind = data[pos:pos + 4].decode()
            size = struct.unpack('>I', data[pos + 4:pos + 8])[0]
            self.assertEqual(data[pos + 8:pos + 16], b'\x89PNG\r\n\x1a\n')
            kinds.append(kind)
            pos += size
        self.assertEqual(pos, len(data))
        self.assertEqual(kinds, [k for k, _ in words_install.ICNS_TYPES])

    def test_macos(self):
        apps = words_install.install_macos()
        self.assertEqual([os.path.basename(a) for a in apps],
                         ['Py-Whitaker-Words (GUI).app',
                          'Py-Whitaker-Words (CLI).app'])
        for app in apps:
            with open(os.path.join(app, 'Contents', 'Info.plist'),
                      'rb') as f:
                info = plistlib.load(f)
            launcher = os.path.join(app, 'Contents', 'MacOS',
                                    info['CFBundleExecutable'])
            self.assertTrue(os.access(launcher, os.X_OK))
            self.assertTrue(os.path.isfile(os.path.join(
                app, 'Contents', 'Resources',
                info['CFBundleIconFile'] + '.icns')))
            subprocess.run(['sh', '-n', launcher], check=True)
        command = os.path.join(apps[1], 'Contents', 'Resources',
                               'run.command')
        with open(command) as f:
            self.assertIn('words.py', f.read())
        # the command line runs: the script works without Terminal
        result = subprocess.run(
            ['sh', command], input=b'amicorum\n\n\n',
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=dict(os.environ, TERM='dumb'))
        self.assertIn(b'amic-orum', result.stdout)
        # it is replaced when installed again, and removed
        words_install.install_macos()
        self.assertEqual(words_install.uninstall_macos(), apps)
        # an application of the same name made by someone else is kept
        os.makedirs(os.path.join(apps[0], 'Contents'))
        with self.assertRaises(OSError):
            words_install.install_macos()
        self.assertEqual(words_install.uninstall_macos(), [])
        self.assertTrue(os.path.isdir(apps[0]))

    @unittest.skipIf(sys.platform == 'win32', 'uses a shell stand-in')
    def test_windows(self):
        """With a stand-in for PowerShell that writes the shortcut's
        values into the .lnk file."""
        bin_dir = os.path.join(self.tmp.name, 'bin')
        os.mkdir(bin_dir)
        fake = os.path.join(bin_dir, 'powershell')
        with open(fake, 'w') as f:
            f.write('#!/bin/sh\nprintf "%s|%s|%s|%s" "$PYW_TARGET" '
                    '"$PYW_ARGS" "$PYW_DIR" "$PYW_ICON" > "$PYW_LNK"\n')
        os.chmod(fake, 0o755)
        os.environ['PATH'] = bin_dir + os.pathsep + os.environ['PATH']
        paths = words_install.install_windows()
        self.assertEqual([os.path.basename(p) for p in paths],
                         ['Py-Whitaker-Words (GUI).lnk',
                          'Py-Whitaker-Words (CLI).lnk'])
        self.assertTrue(paths[0].startswith(os.path.join(
            self.tmp.name, 'AppData', 'Microsoft', 'Windows', 'Start Menu',
            'Programs')))
        with open(paths[1]) as f:
            target, args, folder, icon = f.read().split('|')
        self.assertEqual(target, sys.executable)
        self.assertEqual(args, '"%s"' % os.path.join(words_install.HERE,
                                                     'words.py'))
        self.assertEqual(folder, words_install.HERE)
        self.assertTrue(icon.endswith('py-whitaker-words.ico,0'))
        self.assertEqual(words_install.uninstall_windows(), paths)


if __name__ == '__main__':
    unittest.main()
