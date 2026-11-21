#!/usr/bin/env python3
"""Hace de nuevo todos los íconos a partir de icons/py-words.svg:

    python3 tools/icons.py [--svg FILE] [-o FOLDER] [--dry-run]

En FOLDER (icons/ por omisión) escribe:

* linux/icons/hicolor/NxN/apps/py-words.png, para cada N de HICOLOR_SIZES,
  y linux/icons/hicolor/scalable/apps/py-words.svg (una copia del SVG),
  para words_install.py, la ventana y el AppImage;
* macos/py-words.iconset/icon_NxN[@2x].png, macos/py-words.icns y
  macos/py-words-macos-1024.png;
* windows/py-words-N.png, para cada N de WINDOWS_SIZES, y
  windows/py-words.ico.

Inkscape dibuja cada tamaño a partir del SVG (nunca se reduce un PNG más
grande), todos en una sola ejecución.  El .ico se arma con Pillow a partir
de esos mismos PNG, y el .icns a partir del iconset, como lo hace
words_install.py (como lo haría iconutil, con los diez tamaños).

Se usa el inkscape que esté en el PATH (en el computador de desarrollo, un
script que llama al AppImage de Inkscape).  Solo si hay instalado un
Flatpak de Inkscape (org.inkscape.Inkscape) se prefiere este, y entonces
se corre con "flatpak run", con rutas absolutas y escribiendo solo dentro
de FOLDER, porque un Flatpak no ve el /tmp del sistema.  Por eso los PNG
se dibujan primero en una carpeta oculta dentro de FOLDER y solo se
mueven a su lugar cuando están todos.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NAME = "py-words"
FLATPAK_ID = "org.inkscape.Inkscape"
HICOLOR_SIZES = [16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512]
ICONSET_SIZES = [16, 32, 128, 256, 512]   # each also @2x
MACOS_BIG = 1024
WINDOWS_SIZES = [44, 50, 150, 256, 310]   # (mosaicos y menú Inicio)
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]

#  Todos los tamaños que se dibujan
SIZES = sorted(set(HICOLOR_SIZES) | set(ICONSET_SIZES) |
               {2 * n for n in ICONSET_SIZES} | {MACOS_BIG} |
               set(WINDOWS_SIZES) | set(ICO_SIZES))

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def find_inkscape():
    """The command to run Inkscape, and whether it is a Flatpak."""
    if shutil.which("flatpak"):
        found = subprocess.run(["flatpak", "info", FLATPAK_ID],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        if found.returncode == 0:
            return ["flatpak", "run", FLATPAK_ID], True
    native = shutil.which("inkscape")
    if native:
        return [native], False
    sys.exit("Inkscape was not found (neither the Flatpak %s nor inkscape "
             "on the PATH)." % FLATPAK_ID)


def render(inkscape, svg, folder, sizes):
    """Draws svg as folder/N.png for each N in sizes, in one run."""
    actions = []
    for n in sizes:
        actions += ["export-width:%d" % n, "export-height:%d" % n,
                    "export-type:png",
                    "export-filename:%s" % (folder / ("%d.png" % n)),
                    "export-do"]
    command = inkscape + [str(svg), "--actions=" + ";".join(actions)]
    result = subprocess.run(command, capture_output=True, text=True)
    missing = [n for n in sizes if not (folder / ("%d.png" % n)).is_file()]
    if result.returncode != 0 or missing:
        sys.stderr.write(result.stderr)
        sys.exit("Inkscape did not draw the sizes %s." %
                 ", ".join(map(str, missing or sizes)))


def check_sizes(folder, sizes):
    from PIL import Image
    for n in sizes:
        with Image.open(folder / ("%d.png" % n)) as im:
            if im.size != (n, n):
                sys.exit("%d.png came out %dx%d: is the SVG not square?"
                         % (n, *im.size))


def put(src, dst):
    """Copies src to dst, replacing it even if it is read-only."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    shutil.copyfile(src, dst)


def save_images(path, drawn, png, **options):
    """Saves the PNGs of the sizes drawn as one file (the .ico)."""
    from PIL import Image
    images = [Image.open(png(n)).convert("RGBA") for n in drawn]
    tmp = path.with_name(path.name + ".tmp")
    images[-1].save(tmp, format=path.suffix[1:].upper(),
                    append_images=images[:-1], **options)
    os.replace(tmp, path)


def main():
    parser = argparse.ArgumentParser(
        description="Makes all the icons afresh from the SVG.")
    parser.add_argument("--svg", type=Path, default=ROOT / "icons" /
                        (NAME + ".svg"), help="the SVG (icons/%s.svg)" % NAME)
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "icons",
                        help="the folder for the icons (icons/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="only show how Inkscape would be run")
    args = parser.parse_args()

    svg = args.svg.resolve()
    out = args.output.resolve()
    if not svg.is_file():
        sys.exit("There is no %s." % svg)
    try:
        import PIL  # noqa: F401
    except ImportError:
        sys.exit("Pillow is needed for the .ico "
                 "(dnf install python3-pillow, or pip install pillow).")

    inkscape, flatpak = find_inkscape()
    print("Inkscape: %s%s" % (" ".join(inkscape),
                              " (Flatpak)" if flatpak else ""))
    if flatpak and (out == Path("/tmp") or Path("/tmp") in out.parents):
        sys.exit("The Flatpak of Inkscape cannot write in /tmp; "
                 "choose another folder with -o.")
    if args.dry_run:
        print("Would draw %s at %s px into %s." %
              (svg, ", ".join(map(str, SIZES)), out))
        return

    out.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".render-", dir=out))
    try:
        render(inkscape, svg, stage, SIZES)
        check_sizes(stage, SIZES)

        def png(n):
            return stage / ("%d.png" % n)

        hicolor = out / "linux" / "icons" / "hicolor"
        for n in HICOLOR_SIZES:
            put(png(n), hicolor / ("%dx%d" % (n, n)) / "apps" /
                (NAME + ".png"))
        scalable = hicolor / "scalable" / "apps" / (NAME + ".svg")
        if svg != scalable.resolve():
            put(svg, scalable)

        macos = out / "macos"
        iconset = macos / (NAME + ".iconset")
        for n in ICONSET_SIZES:
            put(png(n), iconset / ("icon_%dx%d.png" % (n, n)))
            put(png(2 * n), iconset / ("icon_%dx%d@2x.png" % (n, n)))
        put(png(MACOS_BIG), macos / ("%s-macos-%d.png" % (NAME, MACOS_BIG)))
        from words_install import make_icns
        icns = macos / (NAME + ".icns")
        icns.with_name(icns.name + ".tmp").write_bytes(make_icns(iconset))
        os.replace(icns.with_name(icns.name + ".tmp"), icns)

        windows = out / "windows"
        for n in WINDOWS_SIZES:
            put(png(n), windows / ("%s-%d.png" % (NAME, n)))
        save_images(windows / (NAME + ".ico"), ICO_SIZES, png,
                    sizes=[(n, n) for n in ICO_SIZES])
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    print("Made the icons in %s:" % out)
    for part in ["linux/icons/hicolor", "macos", "windows"]:
        print("  %s/" % part)


if __name__ == "__main__":
    main()
