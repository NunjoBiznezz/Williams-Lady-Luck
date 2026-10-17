#!/usr/bin/env python3
"""
rescale_images.py - fix a uniform scale error in a batch of images.

Default: grid paper printed 10-3/16" where it should be 10"  -> images are
1.875% too small, so they are enlarged by 10.1875 / 10.

Examples
  python3 rescale_images.py *.png                          # uses 10.1875 / 10
  python3 rescale_images.py *.png --measured 10.1875 --expected 10
  python3 rescale_images.py *.png --factor 1.01875
  python3 rescale_images.py *.png --mode dpi               # lossless: only change DPI

Modes
  resample (default)  Resize the pixels, keep the DPI (e.g. 300).
                      Paletted/indexed PNGs are resized without blending, so
                      they keep exactly the same palette colours.
  dpi                 Keep the pixels, lower the DPI tag so the image prints and
                      imports into Silhouette Studio at the corrected size.

Output goes next to each file as <name>_scaled.<ext>; originals are untouched
(use --suffix "" --overwrite to replace them).

Setup (once):  python3 -m pip install pillow
"""

import argparse
import os
import sys

from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def main():
    ap = argparse.ArgumentParser(description="Rescale images by a correction factor.")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--measured", type=float, default=10.1875,
                    help="what the grid actually measured (default 10.1875)")
    ap.add_argument("--expected", type=float, default=10.0,
                    help="what it should have measured (default 10)")
    ap.add_argument("--factor", type=float, help="use this scale factor directly")
    ap.add_argument("--mode", choices=["resample", "dpi"], default="resample")
    ap.add_argument("--dpi", type=float, help="assume this DPI if a file has none (default 300)")
    ap.add_argument("--suffix", default="_scaled")
    ap.add_argument("--overwrite", action="store_true", help="allow replacing existing files")
    a = ap.parse_args()

    factor = a.factor if a.factor else a.measured / a.expected
    print(f"Scale factor: {factor:.5f}  ({(factor - 1) * 100:+.3f}%)  mode: {a.mode}\n")

    for path in a.images:
        stem, ext = os.path.splitext(path)
        if stem.endswith(a.suffix) and a.suffix:
            print(f"skip  {path} (already scaled)")
            continue
        out = stem + a.suffix + ext
        if os.path.exists(out) and not a.overwrite:
            print(f"skip  {path} ({os.path.basename(out)} exists; use --overwrite)")
            continue
        try:
            im = Image.open(path)
            im.load()
        except Exception as e:
            print(f"skip  {path} ({e})")
            continue

        dpi = im.info.get("dpi", (a.dpi or 300, a.dpi or 300))
        dpi = (float(dpi[0]) or 300, float(dpi[1]) or 300)
        w, h = im.size

        if a.mode == "resample":
            nw, nh = round(w * factor), round(h * factor)
            # indexed / 1-bit images: nearest keeps the exact palette colours
            method = Image.NEAREST if im.mode in ("P", "1", "L;1") else Image.LANCZOS
            new = im.resize((nw, nh), method)
            if im.mode == "P" and im.getpalette():
                new.putpalette(im.getpalette())
            new_dpi = dpi
        else:
            new, nw, nh = im, w, h
            new_dpi = (dpi[0] / factor, dpi[1] / factor)

        save_kw = {"dpi": (round(new_dpi[0], 3), round(new_dpi[1], 3))}
        if "transparency" in im.info:
            save_kw["transparency"] = im.info["transparency"]
        if ext.lower() in (".jpg", ".jpeg"):
            save_kw["quality"] = 95
        new.save(out, **save_kw)

        print(f"ok    {os.path.basename(path)}: {w}x{h} @ {dpi[0]:.0f} dpi "
              f"({w / dpi[0]:.3f}\" x {h / dpi[1]:.3f}\")  ->  {nw}x{nh} @ {new_dpi[0]:.2f} dpi "
              f"({nw / new_dpi[0]:.3f}\" x {nh / new_dpi[1]:.3f}\")")


if __name__ == "__main__":
    main()
