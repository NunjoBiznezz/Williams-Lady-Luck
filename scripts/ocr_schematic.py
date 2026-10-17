#!/usr/bin/env python3
"""
ocr_schematic.py
================
Turn a large-format scanned PDF (schematics, wiring diagrams, engineering
drawings, etc.) into a searchable PDF, even when the labels on the page run
in multiple directions (horizontal AND sideways/upside-down).

Standard OCR tools (including ocrmypdf's default mode) assume all text reads
left-to-right. On a schematic where component labels are rotated 90 degrees
to run alongside vertical wires, that assumption causes the invisible text
layer to end up misaligned with what's actually printed on the page. This
script works around that by running OCR FOUR times per page -- once with the
page as-is, and once with it rotated 90, 180, and 270 degrees -- keeping only
the highest-confidence reading for each spot on the page, and placing the
invisible, searchable text back at the correct position AND angle.

It also fixes a common scanner quirk where a PDF's visible page (CropBox) is
smaller than its full underlying canvas (MediaBox); left alone, that mismatch
can make some OCR tools rasterize the wrong region and produce a blank or
squashed-looking result.

--------------------------------------------------------------------------
SETUP (macOS)
--------------------------------------------------------------------------
1) Install command-line tools with Homebrew (https://brew.sh):

       brew install tesseract poppler

2) Install the Python packages (Python 3.9+ recommended). Easiest is a
   virtual environment so you don't touch your system Python:

       python3 -m venv ~/ocr-venv
       source ~/ocr-venv/bin/activate
       pip install pillow pytesseract reportlab pypdf pikepdf

   (Every time you want to run the script in a new terminal window, run
   `source ~/ocr-venv/bin/activate` first.)

--------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------
    python3 ocr_schematic.py input.pdf output.pdf

Common options:

    --dpi 300              Resolution to render/OCR at (default 300).
                            Higher = sharper text recognition and a bigger
                            file; 300 is a good balance for large drawings.
    --lang eng              Tesseract language (default eng).
    --min-conf 55           Minimum OCR confidence (0-100) to keep a word
                            (default 55). Lower catches more text but also
                            more garbage; higher is stricter.
    --single-orientation    Skip the 90/180/270 rotation passes and OCR the
                            page only as-is. Much faster -- use this for
                            ordinary documents where all the text reads the
                            normal way.
    --jpeg-quality 82       Quality (1-100) for the recompressed background
                            image (default 82). Lower = smaller file.

Example:

    python3 ocr_schematic.py "Schematic.pdf" "Schematic_OCR.pdf" --dpi 300

The output is a normal, searchable PDF you can open in Preview, Acrobat, or
any other PDF viewer, and Cmd-F / Ctrl-F to find text on it.
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # these are large, legitimate scans, not bombs

import pikepdf
import pytesseract
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as canvaslib

# ---------------------------------------------------------------------------
# Geometry helpers for the 4-orientation OCR pass
# ---------------------------------------------------------------------------

# For a word found after rotating the page image by `r` degrees
# counter-clockwise (via PIL's exact 90-degree transpose ops), these tables
# say: (a) what angle to draw the invisible text at on the ORIGINAL page so
# it lines up with the real, physically-rotated glyphs, and (b) which corner
# of the word's rotated-frame bounding box is the "start of the baseline" in
# original-page pixel coordinates (used as the text's anchor point).
ANGLE_FOR_ROTATION = {0: 0, 90: 270, 180: 180, 270: 90}
ANCHOR_FOR_ROTATION = {
    0: lambda w: (w["x0"], w["y1"]),
    90: lambda w: (w["x0"], w["y0"]),
    180: lambda w: (w["x1"], w["y0"]),
    270: lambda w: (w["x1"], w["y1"]),
}


def inverse_map(px, py, r, W, H):
    """Map a point from the `r`-degrees-rotated image back to the pixel
    coordinates of the original (0-degree) image, where W,H are the
    ORIGINAL image's width/height in pixels."""
    if r == 0:
        return px, py
    elif r == 90:
        return W - 1 - py, px
    elif r == 180:
        return W - 1 - px, H - 1 - py
    elif r == 270:
        return py, H - 1 - px
    raise ValueError(r)


def rotate_image(im, r):
    if r == 0:
        return im
    elif r == 90:
        return im.transpose(Image.ROTATE_90)
    elif r == 180:
        return im.transpose(Image.ROTATE_180)
    elif r == 270:
        return im.transpose(Image.ROTATE_270)
    raise ValueError(r)


def ocr_one_orientation(im, r, lang, min_conf):
    """Run tesseract on `im` rotated by r degrees, return a list of word
    dicts with bounding boxes already mapped back into the ORIGINAL image's
    pixel coordinate space."""
    W, H = im.size  # original (0-degree) size
    rim = rotate_image(im, r)

    data = pytesseract.image_to_data(
        rim, lang=lang, output_type=pytesseract.Output.DICT, config="--psm 11", timeout=280
    )

    words = []
    n = len(data["text"])
    for i in range(n):
        txt = data["text"][i].strip()
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1
        if not txt or conf < min_conf or len(txt) < 2:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        rx0, ry0, rx1, ry1 = x, y, x + w, y + h
        corners = [
            inverse_map(rx0, ry0, r, W, H),
            inverse_map(rx1, ry0, r, W, H),
            inverse_map(rx1, ry1, r, W, H),
            inverse_map(rx0, ry1, r, W, H),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        words.append({
            "text": txt, "conf": conf, "r": r,
            "x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys),
            "rw": rx1 - rx0, "rh": ry1 - ry0,
        })
    return words


def iou(a, b):
    ax0, ay0, ax1, ay1 = a["x0"], a["y0"], a["x1"], a["y1"]
    bx0, by0, bx1, by1 = b["x0"], b["y0"], b["x1"], b["y1"]
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (ax1 - ax0) * (ay1 - ay0)
    area_b = (bx1 - bx0) * (by1 - by0)
    return inter / max(1e-6, min(area_a, area_b))


def dedupe_words(words):
    """Keep the highest-confidence reading for each spot on the page,
    discarding lower-confidence overlapping guesses from the "wrong"
    orientation passes."""
    words = sorted(words, key=lambda w: -w["conf"])
    accepted = []
    for w in words:
        if not any(iou(w, a) > 0.25 for a in accepted):
            accepted.append(w)
    return accepted


# ---------------------------------------------------------------------------
# PDF box normalization (fixes the CropBox/MediaBox mismatch pitfall)
# ---------------------------------------------------------------------------

def normalize_boxes(input_pdf, normalized_pdf):
    pdf = pikepdf.open(input_pdf)
    for page in pdf.pages:
        crop = page.get("/CropBox")
        media = page.get("/MediaBox")
        if crop is not None and list(crop) != list(media):
            page.MediaBox = crop
        for box in ("/TrimBox", "/BleedBox", "/ArtBox"):
            if box in page:
                del page[box]
    pdf.save(normalized_pdf)


# ---------------------------------------------------------------------------
# Main per-page pipeline
# ---------------------------------------------------------------------------

def process_page(png_path, dpi, lang, min_conf, jpeg_quality, single_orientation, page_pdf_path):
    im = Image.open(png_path).convert("L")  # grayscale for OCR: lighter/faster
    W, H = im.size

    orientations = [0] if single_orientation else [0, 90, 180, 270]
    all_words = []
    for r in orientations:
        print(f"    OCR pass at {r} degrees...", flush=True)
        all_words.extend(ocr_one_orientation(im, r, lang, min_conf))

    accepted = dedupe_words(all_words) if not single_orientation else all_words
    print(f"    kept {len(accepted)} words after de-duplication", flush=True)

    # Background image, recompressed to keep file size reasonable
    bg_im = Image.open(png_path).convert("RGB")
    bg_path = png_path + ".bg.jpg"
    bg_im.save(bg_path, "JPEG", quality=jpeg_quality)

    page_w_pt = W / dpi * 72.0
    page_h_pt = H / dpi * 72.0

    c = canvaslib.Canvas(page_pdf_path, pagesize=(page_w_pt, page_h_pt))
    c.drawImage(ImageReader(bg_path), 0, 0, width=page_w_pt, height=page_h_pt)

    for w in accepted:
        text = w["text"]
        r = w["r"]
        px, py = ANCHOR_FOR_ROTATION[r](w)
        x_pt = px / dpi * 72.0
        y_pt = page_h_pt - (py / dpi * 72.0)
        fontsize = max(3.0, (w["rh"] / dpi * 72.0) * 0.85)
        target_width_pt = w["rw"] / dpi * 72.0

        c.saveState()
        c.translate(x_pt, y_pt)
        c.rotate(ANGLE_FOR_ROTATION[r])
        try:
            natural_width = c.stringWidth(text, "Helvetica", fontsize)
        except Exception:
            natural_width = 0
        scale = 100.0
        if natural_width > 0.01:
            scale = max(20.0, min(400.0, 100.0 * target_width_pt / natural_width))

        to = c.beginText(0, 0)
        to.setTextRenderMode(3)  # invisible
        to.setFont("Helvetica", fontsize)
        to.setHorizScale(scale)
        to.textOut(text)
        c.drawText(to)
        c.restoreState()

    c.showPage()
    c.save()
    os.remove(bg_path)


def natural_page_number(path):
    m = re.search(r"-(\d+)\.png$", path)
    return int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_pdf")
    ap.add_argument("output_pdf")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--lang", default="eng")
    ap.add_argument("--min-conf", type=float, default=55)
    ap.add_argument("--jpeg-quality", type=int, default=82)
    ap.add_argument("--single-orientation", action="store_true",
                     help="Skip the 90/180/270 passes (faster; use for normal upright text).")
    args = ap.parse_args()

    for tool in ("pdftoppm", "tesseract"):
        if shutil.which(tool) is None:
            sys.exit(f"Error: '{tool}' not found. Install with: brew install tesseract poppler")

    with tempfile.TemporaryDirectory() as tmp:
        normalized_pdf = os.path.join(tmp, "normalized.pdf")
        print("Normalizing page boxes...", flush=True)
        normalize_boxes(args.input_pdf, normalized_pdf)

        print(f"Rasterizing at {args.dpi} dpi...", flush=True)
        prefix = os.path.join(tmp, "page")
        subprocess.run(["pdftoppm", "-png", "-r", str(args.dpi), normalized_pdf, prefix], check=True)

        png_files = sorted(glob.glob(prefix + "-*.png"), key=natural_page_number)
        if not png_files:
            # single-page PDFs sometimes get named without a page suffix
            png_files = sorted(glob.glob(prefix + "*.png"))
        if not png_files:
            sys.exit("Error: rasterization produced no page images.")

        page_pdfs = []
        for i, png in enumerate(png_files, start=1):
            print(f"Page {i}/{len(png_files)}: {os.path.basename(png)}", flush=True)
            page_pdf = os.path.join(tmp, f"page_{i}.pdf")
            process_page(png, args.dpi, args.lang, args.min_conf, args.jpeg_quality,
                         args.single_orientation, page_pdf)
            page_pdfs.append(page_pdf)

        print("Assembling final PDF...", flush=True)
        writer = PdfWriter()
        for p in page_pdfs:
            reader = PdfReader(p)
            for page in reader.pages:
                writer.add_page(page)
        with open(args.output_pdf, "wb") as f:
            writer.write(f)

    print(f"Done: {args.output_pdf}")


if __name__ == "__main__":
    main()
