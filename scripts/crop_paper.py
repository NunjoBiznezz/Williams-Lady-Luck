#!/usr/bin/env python3
"""
crop_paper.py - crop the graph paper off rectified photos, keeping just the artwork.

Finds the graph paper by its grid of crosses and trims it off, stopping where
the artwork starts - it doesn't cut into the art. DPI is kept, so the result is
still true size.

Usage (from the Lady Luck folder):
  python3 scripts/crop_paper.py IMG_5580.png IMG_5581.png   # specific images
  python3 scripts/crop_paper.py images                       # every .png in the images folder
  python3 scripts/crop_paper.py --preview                    # only make crop_preview.jpg
                                                             #   (red box = crop) - nothing saved
Options:
  --tight          trim a bit harder so no paper at all shows at uneven edges
                   (may lose a sliver of artwork)
  --loose          keep ALL the artwork, even if more paper shows
  --inset IN       extra trim inside the edge, inches (default 0)
  --inplace        overwrite the image instead of saving NAME_cropped.png
  --all            also process unrectified photos (72 dpi straight from the phone);
                   by default only rectified images (~300 dpi) are cropped
"""
import argparse, glob, os, sys
import cv2, numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

def detect_crosses(rgb, spacing):
    """Return (N,2) array of grid-cross centres sitting on light, colourless paper."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    local = cv2.GaussianBlur(gray, (0, 0), max(3, spacing / 4))
    dark = ((local.astype(int) - gray) > 25).astype(np.float32)
    arm = max(4, int(spacing * 0.25)); n = 2 * arm + 1
    T = np.zeros((n, n), np.float32); T[arm, 1:-1] = 1; T[1:-1, arm] = 1
    r = cv2.matchTemplate(dark, T, cv2.TM_CCOEFF_NORMED)
    pk = (r == cv2.dilate(r, np.ones((n, n), np.uint8))) & (r > 0.45)
    ys, xs = np.where(pk)
    out = []
    c = max(1, arm // 2)
    for x, y in zip(xs + arm, ys + arm):
        q = (slice(max(0, y - arm), max(0, y - arm) + c), slice(max(0, x - arm), max(0, x - arm) + c))
        if hsv[..., 2][q].mean() > 70 and hsv[..., 1][q].mean() < 55:
            out.append((x, y))
    return np.array(out, float).reshape(-1, 2)

def largest_empty_rect(occ):
    """Largest all-zero axis-aligned rectangle in a 0/1 grid -> (r0, c0, r1, c1) inclusive."""
    R, C = occ.shape; h = np.zeros(C, int); best = (0, None)
    for r in range(R):
        h = np.where(occ[r] == 0, h + 1, 0)
        st = []
        for c in range(C + 1):
            cur = h[c] if c < C else 0
            start = c
            while st and st[-1][1] >= cur:
                s0, hh = st.pop()
                area = hh * (c - s0)
                if area > best[0]:
                    best = (area, (r - hh + 1, s0, r, c - 1))
                start = s0
            st.append((start, cur))
    return best[1]

def grid_crop(rgb, spacing, loose, tight=False):
    pts = detect_crosses(rgb, spacing)
    if len(pts) < 12:
        return None
    # real spacing from the data (grid paper may not be exactly 1/2")
    d = np.sqrt(((pts[:, None] - pts[None]) ** 2).sum(-1)); np.fill_diagonal(d, 1e9)
    nn = d.min(1); sp = float(np.median(nn[(nn > spacing * 0.7) & (nn < spacing * 1.4)])) if \
        np.any((nn > spacing * 0.7) & (nn < spacing * 1.4)) else spacing
    ox = sp / (2 * np.pi) * np.angle(np.exp(2j * np.pi * pts[:, 0] / sp).mean())
    oy = sp / (2 * np.pi) * np.angle(np.exp(2j * np.pi * pts[:, 1] / sp).mean())
    fx = (pts[:, 0] - ox) / sp; fy = (pts[:, 1] - oy) / sp
    on = (np.abs(fx - np.round(fx)) < 0.2) & (np.abs(fy - np.round(fy)) < 0.2)
    nb = ((d > sp * 0.8) & (d < sp * 1.2)).any(1)
    pts = pts[on & nb]
    if len(pts) < 12:
        return None
    H, W = rgb.shape[:2]
    i0 = int(np.floor((0 - ox) / sp)); i1 = int(np.ceil((W - ox) / sp))
    j0 = int(np.floor((0 - oy) / sp)); j1 = int(np.ceil((H - oy) / sp))
    occ = np.zeros((j1 - j0 + 1, i1 - i0 + 1), np.uint8)
    for x, y in pts:
        occ[int(round((y - oy) / sp)) - j0, int(round((x - ox) / sp)) - i0] = 1
    # lattice points outside the photo, or on blank fill, count as "paper" too
    white = np.all(rgb >= 250, axis=2)
    for jj in range(occ.shape[0]):
        for ii in range(occ.shape[1]):
            X = ox + (ii + i0) * sp; Y = oy + (jj + j0) * sp
            if not (0 <= X < W and 0 <= Y < H) or white[int(Y), int(X)]:
                occ[jj, ii] = 1
    rect = largest_empty_rect(occ)
    if rect is None:
        return None
    r0, c0, r1, c1 = rect
    # bounds: halfway between the last cross row/col and the first empty one, clipped to photo
    X0 = ox + (c0 + i0 - 0.8) * sp; X1 = ox + (c1 + i0 + 0.8) * sp
    Y0 = oy + (r0 + j0 - 0.8) * sp; Y1 = oy + (r1 + j0 + 0.8) * sp
    X0, Y0, X1, Y1 = max(0, X0), max(0, Y0), min(W, X1), min(H, Y1)
    if loose:
        return X0, Y0, X1, Y1
    # trim remaining plain paper strip at each edge (at most one grid square)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    paper = ((hsv[..., 1] < 45) & (hsv[..., 2] > 85)) | white
    x0, y0, x1, y1 = int(X0), int(Y0), int(X1) - 1, int(Y1) - 1
    lim = int(sp * 1.2); th = 0.25 if tight else 0.5     # stop where the edge is mostly artwork
    for _ in range(lim):
        if paper[y0:y1 + 1, x0].mean() > th: x0 += 1
        if paper[y0:y1 + 1, x1].mean() > th: x1 -= 1
        if paper[y0, x0:x1 + 1].mean() > th: y0 += 1
        if paper[y1, x0:x1 + 1].mean() > th: y1 -= 1
    return x0, y0, x1 + 1, y1 + 1

def colour_crop(rgb):
    """Fallback when no grid is visible: bounding box of the non-paper area."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    m = (~((hsv[..., 1] < 45) & (hsv[..., 2] > 85))).astype(np.uint8)
    k = max(3, int(min(rgb.shape[:2]) * 0.02) | 1)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n < 2:
        return None
    i = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA]); x, y, w, h = st[i, :4]
    return x, y, x + w, y + h

def find_crop(im, loose, inset_in, dpi, tight=False):
    W, H = im.size
    f = 1000 / max(W, H)
    small = np.array(im.convert('RGB').resize((int(W * f), int(H * f)), Image.LANCZOS))
    hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
    if ((hsv[..., 1] < 45) & (hsv[..., 2] > 85)).mean() < 0.08:
        return None, 'no graph paper found'
    box = grid_crop(small, 0.5 * dpi * f, loose, tight)
    how = 'grid'
    if box is None:
        box, how = colour_crop(small), 'colour (no grid found)'
    if box is None:
        return None, how
    ins = inset_in * dpi * f * (-1 if loose else 1)
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = x0 + ins, y0 + ins, x1 - ins, y1 - ins
    if x1 - x0 < 20 or y1 - y0 < 20:
        return None, how
    return (max(0, int(x0 / f)), max(0, int(y0 / f)), min(W, int(x1 / f)), min(H, int(y1 / f))), how

def main():
    ap = argparse.ArgumentParser(description="Crop graph paper off rectified photos.")
    ap.add_argument('images', nargs='*')
    ap.add_argument('--preview', action='store_true')
    ap.add_argument('--loose', action='store_true')
    ap.add_argument('--inset', type=float, default=0.0)
    ap.add_argument('--tight', action='store_true')
    ap.add_argument('--inplace', action='store_true')
    ap.add_argument('--all', action='store_true')
    a = ap.parse_args()

    files, outdir = [], '.'
    for x in (a.images or ['.']):
        if os.path.isdir(x):
            outdir = x
            files += sorted(f for f in glob.glob(os.path.join(x, '*.png'))
                            if not f.endswith(('_cropped.png', '_check.png')) and 'crop_preview' not in f)
        else:
            files.append(x)
    thumbs = []
    for path in files:
        try:
            im = Image.open(path); im.load()
        except Exception as e:
            print(f"skip  {path}: {e}"); continue
        dpi = float((im.info.get('dpi') or (0, 0))[0] or 0)
        if dpi < 150 and not a.all:
            print(f"skip  {path}: {dpi:.0f} dpi - not rectified (use --all to include)"); continue
        box, how = find_crop(im, a.loose, a.inset + (0.05 if a.tight else 0), dpi or 300, a.tight)
        if not box:
            print(f"skip  {path}: {how if how != 'grid' else 'could not find the artwork'}"); continue
        x0, y0, x1, y1 = box; d = dpi or 300
        print(f"{'plan' if a.preview else 'crop'}  {path}: {im.width}x{im.height} -> {x1-x0}x{y1-y0}"
              f"  ({(x1-x0)/d:.2f}\" x {(y1-y0)/d:.2f}\")" + ("" if how == 'grid' else f"  [{how}]"))
        if a.preview:
            t = im.convert('RGB'); s = 300 / max(t.size); t = t.resize((int(t.width * s), int(t.height * s)))
            arr = np.array(t); cv2.rectangle(arr, (int(x0*s), int(y0*s)), (int(x1*s)-1, int(y1*s)-1), (255, 0, 0), 3)
            cv2.putText(arr, os.path.splitext(os.path.basename(path))[0], (5, 20), 0, 0.6, (255, 0, 0), 2)
            thumbs.append(Image.fromarray(arr))
            continue
        out = path if a.inplace else os.path.splitext(path)[0] + '_cropped.png'
        kw = {'dpi': im.info['dpi']} if 'dpi' in im.info else {}
        im.crop(box).save(out, **kw)
    if a.preview and thumbs:
        cols = 8; cw = 310; rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * cw, rows * cw), (90, 90, 90))
        for k, t in enumerate(thumbs):
            sheet.paste(t, ((k % cols) * cw, (k // cols) * cw))
        sheet.save(os.path.join(outdir, 'crop_preview.jpg'), quality=85)
        print(f"\nWrote {os.path.join(outdir, 'crop_preview.jpg')} - red box shows each crop. Nothing else was changed.")

if __name__ == '__main__':
    main()
