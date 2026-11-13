"""tools/bundle-flatpak.py, short of building anything: the manifest and
the metainfo agree with the program, and the manifests it writes keep
everything but the sources of py-words."""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from version import VERSION  # noqa: E402


def bundle_flatpak():
    spec = importlib.util.spec_from_file_location(
        'bundle_flatpak', os.path.join(ROOT, 'tools', 'bundle-flatpak.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Flatpak(unittest.TestCase):
    def setUp(self):
        self.tool = bundle_flatpak()

    def test_metainfo(self):
        """The metainfo is valid XML, of the application, and its newest
        release is this version (a version bump adds one)."""
        root = ET.parse(self.tool.METAINFO).getroot()
        self.assertEqual(root.findtext('id'), self.tool.APP_ID)
        self.assertEqual(root.find('launchable').text,
                         self.tool.APP_ID + '.desktop')
        self.assertEqual(self.tool.released(), VERSION)

    @unittest.skipUnless(shutil.which('appstreamcli'), 'no appstreamcli')
    def test_metainfo_validates(self):
        out = subprocess.run(['appstreamcli', 'validate', '--no-net',
                              self.tool.METAINFO],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_manifest(self):
        """The manifest is of the application, the py-words sources are
        the last thing in it, and the files it reads are there."""
        with open(self.tool.MANIFEST, encoding='utf-8') as f:
            text = f.read()
        self.assertIn(f'app-id: {self.tool.APP_ID}\n', text)
        self.assertEqual(text.count(self.tool.SOURCES), 1)
        self.assertNotIn('\n  - name:',
                         text[text.index(self.tool.SOURCES):])
        for f in self.tool.PACKAGING:
            self.assertTrue(os.path.isfile(
                os.path.join(ROOT, 'packaging', f)), f)
        for f in re.findall(r'packaging/[\w./-]+', text):
            if '$' not in f:
                self.assertTrue(os.path.exists(os.path.join(ROOT, f)), f)

    def test_with_sources(self):
        """Only the sources of py-words change."""
        with open(self.tool.MANIFEST, encoding='utf-8') as f:
            text = f.read()
        new = self.tool.with_sources('      - type: dir\n        path: X\n')
        head = text[:text.index(self.tool.SOURCES)]
        self.assertEqual(new, head + '    sources:\n'
                         '      - type: dir\n        path: X\n')

    def test_tree(self):
        """The tree it builds from has the program and the files of
        packaging/ that the build reads, and no tests."""
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'tree')
            self.tool.tree(out)
            for f in ('words_gui.py', 'data/dictionary.xml', 'LICENCE.txt',
                      'icons/py-words.svg') + tuple(
                    os.path.join('packaging', p)
                    for p in self.tool.PACKAGING):
                self.assertTrue(os.path.isfile(os.path.join(out, f)), f)
            self.assertFalse(os.path.exists(os.path.join(out, 'tests')))
            self.assertFalse(os.path.exists(os.path.join(out, 'tools')))


if __name__ == '__main__':
    unittest.main()
