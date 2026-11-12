"""packaging/build-rpm.sh's options, short of building anything, and the
spec's version.

Every case of the options stops in the checks before the build — so they
run in a second, need no rpm-sign, and never touch build/ or the user's
keys: gpg looks in an empty, temporary GNUPGHOME.
"""

import os
import shutil
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "packaging", "build-rpm.sh")


def pinned_key():
    """The project's signing key, as build-rpm.sh pins it."""
    with open(SCRIPT, encoding="utf-8") as f:
        m = re.search(r'SIGNING_KEY="\$\{SIGNING_KEY:-([0-9A-F]{40})\}"',
                      f.read())
    assert m, "build-rpm.sh must pin the project's signing key"
    return m.group(1)


@unittest.skipUnless(shutil.which("rpmbuild") and shutil.which("rpmspec"),
                     "rpm-build not installed")
class Options(unittest.TestCase):
    def run_script(self, *args, **env):
        gnupg = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, gnupg, True)
        os.chmod(gnupg, 0o700)
        full_env = dict(os.environ, GNUPGHOME=gnupg, **env)
        result = subprocess.run([SCRIPT, *args], env=full_env, timeout=60,
                                capture_output=True, text=True)
        return result.returncode, result.stdout + result.stderr

    def test_help_is_the_comment_block(self):
        code, out = self.run_script("--help")
        self.assertEqual(code, 0)
        self.assertIn("--sign[=KEY]", out)
        self.assertNotIn("set -euo", out)
        self.assertNotIn("GNU General Public License", out)

    def test_an_unknown_option_is_refused(self):
        code, out = self.run_script("--signn")
        self.assertEqual(code, 1)
        self.assertIn("unknown option --signn", out)

    def test_an_empty_key_name_is_refused(self):
        code, out = self.run_script("--sign=")
        self.assertEqual(code, 1)
        self.assertIn("--sign= needs a key", out)

    def test_a_missing_rpmsign_is_named_before_building(self):
        code, out = self.run_script("--sign", RPMSIGN="no-such-rpmsign-pw")
        self.assertEqual(code, 1)
        self.assertIn("dnf install rpm-sign", out)

    def test_without_the_signing_key_says_how_to_import_it(self):
        # An rpmsign that exists, so the key check is what fails; it would
        # never run, as nothing gets that far.  --sign uses only the
        # project's key, which the empty keyring doesn't have.
        code, out = self.run_script("--sign", RPMSIGN="/bin/true")
        self.assertEqual(code, 1)
        self.assertIn("no secret key matching " + pinned_key(), out)
        self.assertIn("gpg --import", out)

    def test_the_shipped_key_is_the_pinned_one(self):
        out = subprocess.run(
            ["gpg", "--batch", "--with-colons", "--show-keys",
             os.path.join(ROOT, "packaging", "RPM-GPG-KEY-py-words")],
            capture_output=True, text=True,
            env=dict(os.environ, GNUPGHOME=tempfile.mkdtemp())).stdout
        fprs = [line.split(":")[9] for line in out.splitlines()
                if line.startswith("fpr:")]
        self.assertEqual(fprs[:1], [pinned_key()])

    def test_an_unknown_key_is_named(self):
        code, out = self.run_script("--sign=nobody@example.invalid",
                                    RPMSIGN="/bin/true")
        self.assertEqual(code, 1)
        self.assertIn("no secret key matching nobody@example.invalid", out)


class Spec(unittest.TestCase):
    def test_the_version_is_the_programs(self):
        # The spec's Version: is written by hand; it must follow version.py
        # (and its %changelog should get an entry with it).
        sys.path.insert(0, ROOT)
        from version import VERSION
        with open(os.path.join(ROOT, "packaging", "py-words.spec"),
                  encoding="utf-8") as f:
            spec = f.read()
        self.assertRegex(spec, r"(?m)^Version:\s+%s$" % re.escape(VERSION))
        self.assertRegex(spec, r"(?m)^\* .* - %s-\d+$" % re.escape(VERSION))


if __name__ == "__main__":
    unittest.main()
