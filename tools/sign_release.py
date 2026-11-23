#!/usr/bin/env python3
"""Firma los archivos de una versión, como los recibirá quien los
descargue, y lo comprueba.

    python3 tools/sign_release.py --key HUELLA --public CLAVE
                                  --sums dist/SHA256SUMS ARCHIVO...

Escribe SUMS (el SHA-256 de cada ARCHIVO, por su nombre, como lo lee
`sha256sum -c`) y una firma separada en ASCII (ARCHIVO.asc) de cada
ARCHIVO y de SUMS, hecha por gpg con la clave HUELLA; luego comprueba cada
firma como lo haría el usuario: en un GNUPGHOME temporal que solo tiene
CLAVE, la clave pública que se publica con la versión.  Así se comprueban
a la vez las firmas y que la clave publicada es la que firmó.  Termina con
un error si algo no se comprueba.  tools/release.py lo corre antes de
poner la etiqueta y de publicar nada.
"""

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile

#  gpg, sin el entorno del usuario (salvo GNUPGHOME, al firmar)
PATH = '/usr/bin:/bin'


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def sign(path: str, key: str) -> str:
    """PATH.asc, the detached signature of PATH with KEY (gpg asks for the
    passphrase, if it is not cached)."""
    out = path + '.asc'
    subprocess.run(['gpg', '--batch', '--yes', '--local-user', key,
                    '--armor', '--detach-sign', '--output', out, path],
                   check=True)
    return out


def verify(files: list[str], public: str) -> list[str]:
    """What does not verify with only PUBLIC known (an empty list:
    everything does)."""
    failed = []
    with tempfile.TemporaryDirectory(prefix='sign-release-') as home:
        env = {'GNUPGHOME': home, 'PATH': PATH}
        #  (gpg quiere su carpeta solo para el usuario)
        os.chmod(home, 0o700)
        try:
            subprocess.run(['gpg', '--batch', '--quiet', '--import', public],
                           env=env, check=True, capture_output=True)
            for path in files:
                done = subprocess.run(
                    ['gpg', '--batch', '--verify', path + '.asc', path],
                    env=env, capture_output=True, text=True)
                if done.returncode != 0:
                    lines = done.stderr.strip().splitlines()
                    failed.append(f'{os.path.basename(path)}: '
                                  f'{lines[-1] if lines else "not good"}')
        finally:
            #  Un GNUPGHOME nuevo puede arrancar keyboxd o gpg-agent: se
            #  detienen antes de borrar la carpeta
            subprocess.run(['gpgconf', '--kill', 'all'], env=env,
                           capture_output=True)
    return failed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog='tools/sign_release.py',
        description='Sign the files of a release, and check each signature '
                    'with only the public key published.')
    parser.add_argument('--key', required=True,
                        help='the fingerprint of the signing key')
    parser.add_argument('--public', required=True,
                        help='the public key published with the release')
    parser.add_argument('--sums', required=True,
                        help='where to write the SHA-256 sums')
    parser.add_argument('files', nargs='+')
    args = parser.parse_args(argv)
    missing = [f for f in args.files if not os.path.isfile(f)]
    if missing:
        print(f'sign_release.py: missing: {", ".join(missing)}',
              file=sys.stderr)
        return 1
    names = [os.path.basename(f) for f in args.files]
    #  SHA256SUMS va por nombre: dos archivos con el mismo nombre no caben
    if len(set(names)) != len(names):
        print('sign_release.py: two files have the same name',
              file=sys.stderr)
        return 1
    with open(args.sums, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(f'{sha256(p)}  {n}\n'
                     for p, n in zip(args.files, names))
    # SUMS is signed too, after the files it lists
    signed = list(args.files) + [args.sums]
    try:
        for path in signed:
            sign(path, args.key)
    except (OSError, subprocess.CalledProcessError):
        print("sign_release.py: gpg could not sign (is the key's passphrase "
              'cached? see packaging/COPR.org)', file=sys.stderr)
        return 1
    failed = verify(signed, args.public)
    if failed:
        print("sign_release.py: these do not verify with the published "
              'key:\n  ' + '\n  '.join(failed), file=sys.stderr)
        return 1
    print('Signed and verified: '
          + ', '.join(os.path.basename(p) for p in signed))
    return 0


if __name__ == '__main__':
    sys.exit(main())
