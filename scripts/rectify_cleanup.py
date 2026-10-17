#!/usr/bin/env python3
"""
rectify_cleanup.py - tidy up after checking stencil_rectify.py output.

For every  NAME_rectified.png  : replaces NAME.png with it (the rectified
                                 image takes the original's name)
For every  NAME_check.png      : deletes it

The original photo is overwritten. If the folder is in git and the original
was committed, you can still get it back with:  git checkout -- "NAME.png"

Usage (from the Lady Luck folder):
  python3 scripts/rectify_cleanup.py            # show what will happen, then ask
  python3 scripts/rectify_cleanup.py -y         # do it without asking
  python3 scripts/rectify_cleanup.py -n         # dry run: only list the changes
  python3 scripts/rectify_cleanup.py images --suffix _cropped
                                                # NAME_cropped.png -> NAME.png (after crop_paper.py)
  python3 scripts/rectify_cleanup.py some/folder --points
                                                # other folder; also delete
                                                # NAME_points.json files

Options:
  --points   also delete NAME_points.json for each image that was replaced
             (those saved clicks match the OLD photo, not the rectified one)
"""

import argparse
import glob
import os
import sys


def main():
    ap = argparse.ArgumentParser(description="Replace NAME.png with NAME_rectified.png and remove NAME_check.png files.")
    ap.add_argument("folder", nargs="?", default=".", help="folder to clean (default: current folder)")
    ap.add_argument("-y", "--yes", action="store_true", help="don't ask for confirmation")
    ap.add_argument("-n", "--dry-run", action="store_true", help="only show what would happen")
    ap.add_argument("--points", action="store_true", help="also delete NAME_points.json of replaced images")
    ap.add_argument("--suffix", default="_rectified",
                    help="which files replace the originals: _rectified (default) or e.g. _cropped")
    a = ap.parse_args()

    folder = os.path.abspath(a.folder)
    if not os.path.isdir(folder):
        sys.exit(f"Not a folder: {folder}")

    renames, deletes = [], []

    tail = a.suffix + ".png"
    for src in sorted(glob.glob(os.path.join(folder, "*" + tail))):
        dst = src[: -len(tail)] + ".png"
        renames.append((src, dst))
        if a.points:
            pts = src[: -len(tail)] + "_points.json"
            if os.path.exists(pts):
                deletes.append(pts)

    if a.suffix == "_rectified":                      # check images only come from stencil_rectify
        deletes += sorted(glob.glob(os.path.join(folder, "*_check.png")))

    if not renames and not deletes:
        print(f"Nothing to clean up in {folder}")
        return

    print(f"In {folder}:\n")
    for src, dst in renames:
        note = "replaces existing" if os.path.exists(dst) else "new"
        print(f"  rename  {os.path.basename(src)}  ->  {os.path.basename(dst)}  ({note})")
    for f in deletes:
        print(f"  delete  {os.path.basename(f)}")
    print(f"\n{len(renames)} to rename, {len(deletes)} to delete.")

    if a.dry_run:
        print("Dry run - nothing changed.")
        return
    if not a.yes:
        if input("Go ahead? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Cancelled - nothing changed.")
            return

    errors = 0
    for src, dst in renames:
        try:
            os.replace(src, dst)
        except OSError as e:
            errors += 1
            print(f"  ! could not rename {os.path.basename(src)}: {e}")
    for f in deletes:
        try:
            os.remove(f)
        except OSError as e:
            errors += 1
            print(f"  ! could not delete {os.path.basename(f)}: {e}")

    print("Done." if not errors else f"Done with {errors} problem(s).")


if __name__ == "__main__":
    main()
