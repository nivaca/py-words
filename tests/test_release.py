"""Pruebas de tools/release.py --keep-in-dist: al final de una publicación,
dist/ guarda el zip y el código fuente de la etiqueta más nuevos, en lugar
de los viejos, y deja lo demás que haya allí (el RPM) como estaba.

No publican nada: llaman la función en una carpeta temporal.
"""

import contextlib
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import release  # noqa: E402


class KeepInDist(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.dist = os.path.join(self.root, 'dist')

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, text):
        path = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(text)

    def keep(self):
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return release.keep_in_dist(self.root)

    def test_newest_replace_the_old(self):
        for made, _ in release.KEPT:
            self.write(made, 'new')
        self.write('dist/py-words-v.0.1.zip', 'old')
        self.write('dist/py-words-0.1-source.tar.gz', 'old')
        self.write('dist/py-words-0.1-1.fc45.noarch.rpm', 'rpm')
        self.assertEqual(self.keep(), 0)
        self.assertEqual(
            sorted(os.listdir(self.dist)),
            sorted(['py-words-0.1-1.fc45.noarch.rpm',
                    os.path.basename(release.ZIP),
                    os.path.basename(release.SOURCE)]))
        with open(os.path.join(self.dist,
                               os.path.basename(release.ZIP))) as f:
            self.assertEqual(f.read(), 'new')

    def test_a_missing_file_fails(self):
        self.write(release.ZIP, 'new')
        self.assertEqual(self.keep(), 1)

    def test_the_release_ends_with_it(self):
        """clean_up plans --keep-in-dist before it deletes build/."""
        steps = []
        fake = type('Fake', (), {'plan': lambda self, *a: steps.append(a)})()
        release.Release.clean_up(fake)
        self.assertIn('--keep-in-dist', steps[0])
        self.assertEqual(steps[1][1], 'rm')


if __name__ == '__main__':
    unittest.main()
