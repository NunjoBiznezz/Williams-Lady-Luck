#!/usr/bin/env python3
"""
Extract embedded images (backglass, DMD, and any other artwork) from a
Visual Pinball .directb2s file.

A .directb2s file is XML under the hood, with each piece of artwork stored
as base64-encoded image data inside an <Images> block (e.g. <BackglassImage
Value="..."/>, <DMDImage Value="..."/>). This script walks that block and
writes each one out as its own file.

No external dependencies - just the Python standard library, so it runs on
macOS with the Python 3 that's already there (check with `python3 --version`
in Terminal; if it's missing, `brew install python3`).

Usage:
    python3 extract_b2s_images.py path/to/table.directb2s [output_dir]

If output_dir is omitted, images are saved next to the .directb2s file in a
new folder named "<tablename>_images".
"""
import sys
import base64
import xml.etree.ElementTree as ET
from pathlib import Path


def extract_images(b2s_path: Path, output_dir: Path) -> int:
    tree = ET.parse(b2s_path)
    root = tree.getroot()

    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = b2s_path.stem

    saved = 0
    for images_block in root.findall(".//Images"):
        for elem in images_block:
            value = elem.get("Value")
            if not value:
                continue
            try:
                data = base64.b64decode(value)
            except Exception as e:
                print(f"  Skipped {elem.tag}: couldn't decode base64 data ({e})")
                continue

            # Nearly all directb2s images are PNG; verify with the file
            # signature rather than assuming, and fall back to .bin if not.
            ext = "png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "bin"
            out_path = output_dir / f"{base_name}_{elem.tag}.{ext}"
            out_path.write_bytes(data)
            print(f"  Saved {elem.tag} -> {out_path}")
            saved += 1

    return saved


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_b2s_images.py path/to/table.directb2s [output_dir]")
        sys.exit(1)

    b2s_path = Path(sys.argv[1]).expanduser()
    if not b2s_path.exists():
        print(f"File not found: {b2s_path}")
        sys.exit(1)

    output_dir = (
        Path(sys.argv[2]).expanduser()
        if len(sys.argv) > 2
        else b2s_path.parent / f"{b2s_path.stem}_images"
    )

    print(f"Extracting images from {b2s_path.name} ...")
    saved = extract_images(b2s_path, output_dir)

    if saved == 0:
        print("No embedded images found - check that this is a valid .directb2s file.")
        sys.exit(1)

    print(f"Done. Saved {saved} image(s) to: {output_dir}")


if __name__ == "__main__":
    main()
