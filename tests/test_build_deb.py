"""Pruebas de packaging/build-deb.py: hace el .deb en una carpeta temporal
(nunca en build/deb/ ni en dist/, donde está el de la versión publicada),
lo vuelve a abrir con la biblioteca estándar y corre el programa que
instala.

No hace falta dpkg: se comprueba el formato a mano (el archivo ar, los
dos tar y el control).
"""

import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "packaging", "build-deb.py")
sys.path.insert(0, ROOT)
from version import VERSION  # noqa: E402


def load():
    # El nombre lleva un guion, así que no se puede importar sin más
    spec = importlib.util.spec_from_file_location("build_deb", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_ar(data):
    """[(name, bytes)] of an ar archive."""
    assert data.startswith(b"!<arch>\n")
    out, i = [], 8
    while i < len(data):
        header = data[i:i + 60]
        assert header.endswith(b"`\n"), header
        name = header[:16].decode().strip()
        size = int(header[48:58])
        out.append((name, data[i + 60:i + 60 + size]))
        i += 60 + size + size % 2
    return out


@unittest.skipUnless(shutil.which("git") and
                     os.path.isdir(os.path.join(ROOT, ".git")),
                     "needs a git clone")
class Package(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        module = load()
        module.OUT = os.path.join(cls.tmp, "out")
        module.DIST = os.path.join(cls.tmp, "dist")
        with open(os.devnull, "w") as quiet:
            stdout, sys.stdout = sys.stdout, quiet
            try:
                cls.path = module.build(None)
            finally:
                sys.stdout = stdout
        cls.module = module
        with open(cls.path, "rb") as f:
            cls.parts = read_ar(f.read())
        cls.members = dict(cls.parts)

        def untar(name):
            with tarfile.open(fileobj=io.BytesIO(cls.members[name])) as t:
                return {m.name: (m, t.extractfile(m).read() if m.isfile()
                                 else None) for m in t.getmembers()}
        cls.control = untar("control.tar.xz")
        cls.data = untar("data.tar.xz")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_name_and_where_it_goes(self):
        self.assertEqual(os.path.basename(self.path),
                         "py-words_%s-1_all.deb" % VERSION)
        self.assertEqual(os.listdir(os.path.join(self.tmp, "dist")),
                         [os.path.basename(self.path)])

    def test_the_ar_members_in_debian_order(self):
        self.assertEqual([n for n, _ in self.parts],
                         ["debian-binary", "control.tar.xz", "data.tar.xz"])
        self.assertEqual(self.members["debian-binary"], b"2.0\n")

    def test_the_control_file(self):
        text = self.control["./control"][1].decode()
        self.assertIn("\nVersion: %s-1\n" % VERSION, text)
        self.assertIn("\nArchitecture: all\n", text)
        self.assertRegex(text, r"\nDepends: python3 \(>= 3\.13\), "
                               r"python3-tk\n")
        self.assertRegex(text, r"\nInstalled-Size: \d+\n")
        # Las líneas de la descripción larga empiezan con un espacio
        description = text.split("\nDescription: ", 1)[1]
        for line in description.splitlines()[1:]:
            self.assertTrue(line.startswith(" "), line)

    def test_the_maintainer_scripts_are_executable(self):
        for name in ("./postinst", "./prerm"):
            info, body = self.control[name]
            self.assertEqual(info.mode, 0o755)
            self.assertTrue(body.startswith(b"#!/bin/sh\n"))

    def test_md5sums_cover_every_file(self):
        listed = {}
        for line in self.control["./md5sums"][1].decode().splitlines():
            digest, path = line.split("  ", 1)
            listed[path] = digest
        files = {n[2:] for n, (m, _) in self.data.items() if m.isfile()}
        self.assertEqual(set(listed), files)

    def test_everything_belongs_to_root(self):
        for info, _ in self.data.values():
            self.assertEqual((info.uid, info.gid, info.uname, info.gname),
                             (0, 0, "root", "root"), info.name)

    def test_what_it_installs(self):
        names = set(self.data)
        for name in ("./usr/bin/py-words",
                     "./usr/share/py-words/words.py",
                     "./usr/share/py-words/version.py",
                     "./usr/share/py-words/COMMIT",
                     "./usr/share/py-words/icons/py-words.svg",
                     "./usr/share/applications/py-words.desktop",
                     "./usr/share/doc/py-words/copyright",
                     "./usr/share/doc/py-words/changelog.Debian.gz",
                     "./usr/share/doc/py-words/MANUAL_en.pdf",
                     # un nombre no ASCII: git lo cita si no se le pide -z
                     "./usr/share/doc/py-words/DESCRIPCIÓN_es.md"):
            self.assertIn(name, names)
        self.assertTrue(any(n.startswith("./usr/share/py-words/data/")
                            for n in names))
        self.assertTrue(any(n.startswith("./usr/share/icons/hicolor/")
                            for n in names))
        for name in names:
            self.assertNotIn("/tests/", name)
            self.assertNotIn("words_install.py", name)
            self.assertNotIn("__pycache__", name)

    def test_the_command(self):
        info, body = self.data["./usr/bin/py-words"]
        self.assertEqual(info.mode, 0o755)
        text = body.decode()
        self.assertNotRegex(text, r"@[A-Z]+@")
        self.assertIn('PROGRAM="/usr/share/py-words"', text)
        self.assertIn("installed by the .deb", text)

    def test_the_signing_key_is_the_rpms(self):
        with open(os.path.join(ROOT, "packaging", "build-rpm.sh"),
                  encoding="utf-8") as f:
            m = re.search(r'SIGNING_KEY="\$\{SIGNING_KEY:-([0-9A-F]{40})\}"',
                          f.read())
        self.assertEqual(self.module.SIGNING_KEY, m.group(1))

    def test_the_installed_program_runs(self):
        root = os.path.join(self.tmp, "root")
        with tarfile.open(fileobj=io.BytesIO(
                self.members["data.tar.xz"])) as t:
            t.extractall(root, filter="data")
        program = os.path.join(root, "usr", "share", "py-words")
        with open(os.path.join(root, "usr", "bin", "py-words"),
                  encoding="utf-8") as f:
            launcher = f.read().replace("/usr/share/py-words", program)
        home = os.path.join(self.tmp, "home")
        env = dict(os.environ, HOME=home, PY_WORDS_CACHE="",
                   PY_WORDS_CONFIG=os.path.join(home, "config"))
        out = subprocess.run(["bash", "-c", launcher, "py-words", "cli",
                              "--interface", "en", "amo"],
                             env=env, capture_output=True, text=True,
                             timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("love", out.stdout)


if __name__ == "__main__":
    unittest.main()
