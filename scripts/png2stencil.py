#!/usr/bin/env python3
"""
png2stencil.py - turn flat-colour artwork (PNG) into clean SVG cut files, one per paint colour.

Setup (once):
    pip3 install pillow numpy opencv-python potracer

Use:
    python3 png2stencil.py card_value_100_right.png
    python3 png2stencil.py exports/*.png --grow 0.015 --fit-circles
    python3 png2stencil.py art.png --dpi 300 --colors 4

For each input it writes a folder "<name>_svg" next to the PNG containing:
    <name>_layers.svg      all colours, one Inkscape layer per colour
    <name>_<colour>.svg    one file per colour, ready for the cutter
    <name>_preview.png     what the traced result looks like

How it works: the colours are found automatically, every pixel is assigned to the
nearest paint colour (soft anti-aliased edge pixels are decided by a majority vote of
their neighbours, so they never become slivers of a wrong colour), and each colour is
traced to smooth curves with potrace.
"""
import argparse
import glob
import os
import sys

import cv2
import numpy as np
import potrace
from PIL import Image

NAMED = {
    'black': (0, 0, 0), 'white': (255, 255, 255), 'cream': (229, 230, 218), 'grey': (128, 128, 128),
    'red': (200, 40, 10), 'orange': (240, 130, 20), 'yellow': (245, 215, 40), 'green': (40, 140, 60),
    'blue': (27, 90, 124), 'lightblue': (110, 180, 225), 'purple': (110, 50, 140), 'pink': (240, 150, 170),
    'brown': (110, 70, 40),
}


def find_palette(rgb, fg, max_colors, min_share):
    """Dominant flat colours among the foreground pixels."""
    px = rgb[fg]
    if len(px) == 0:
        return []
    q = (px // 16).astype(np.int32)
    key = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    keys, inv, counts = np.unique(key, return_inverse=True, return_counts=True)
    sums = np.zeros((len(keys), 3))
    for ch in range(3):
        sums[:, ch] = np.bincount(inv, weights=px[:, ch], minlength=len(keys))
    means = sums / counts[:, None]
    clusters = []                                   # [mean colour, pixel count]
    for i in np.argsort(-counts):
        for c in clusters:
            if np.linalg.norm(c[0] - means[i]) < 48:   # same paint, slightly different shade
                tot = c[1] + counts[i]
                c[0] = (c[0] * c[1] + means[i] * counts[i]) / tot
                c[1] = tot
                break
        else:
            clusters.append([means[i].copy(), int(counts[i])])
    clusters = [c for c in clusters if c[1] / len(px) >= min_share]
    clusters.sort(key=lambda c: -c[1])
    if max_colors:
        clusters = clusters[:max_colors]
    return [tuple(int(round(v)) for v in c[0]) for c in clusters]


def colour_name(c, used):
    name = min(NAMED, key=lambda n: sum((a - b) ** 2 for a, b in zip(NAMED[n], c)))
    if sum((a - b) ** 2 for a, b in zip(NAMED[name], c)) > 70 ** 2:
        name = '%02x%02x%02x' % c
    base, k = name, 2
    while name in used:
        name = '%s%d' % (base, k)
        k += 1
    return name


def label_pixels(rgb, fg, palette, vote=5):
    """Label image: 0 = background, i+1 = palette[i]. Edge pixels decided by neighbourhood vote."""
    pal = np.array(palette, dtype=np.float32)
    d = np.stack([((rgb.astype(np.float32) - p) ** 2).sum(-1) for p in pal], -1)
    near = d.argmin(-1)
    sure = np.sqrt(d.min(-1)) < 40                  # clearly one paint colour, not a blend
    classes = [(~fg)] + [fg & (near == i) for i in range(len(pal))]
    votes = np.stack([cv2.blur((m & (sure | (j == 0))).astype(np.float32), (vote, vote))
                      for j, m in enumerate(classes)], -1)
    lab = votes.argmax(-1)
    undecided = votes.max(-1) <= 0
    lab[undecided] = np.where(fg, near + 1, 0)[undecided]
    return lab.astype(np.int32)


def fit_round_holes(lab, dpi, log):
    """Replace roughly circular background holes (lamp inserts) with clean fitted ellipses."""
    bg = (lab == 0).astype(np.uint8)
    n, cc, st, _ = cv2.connectedComponentsWithStats(bg, 8)
    H, W = lab.shape
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if x == 0 or y == 0 or x + w >= W or y + h >= H:
            continue                                 # touches the border: not a hole
        if area < (0.2 * dpi) ** 2 or not 0.85 < w / h < 1.18 or area / (w * h) < 0.72:
            continue
        comp = cv2.morphologyEx((cc == i).astype(np.uint8), cv2.MORPH_CLOSE,
                                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21)))
        cnts = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]
        el = cv2.fitEllipse(max(cnts, key=cv2.contourArea))
        ring = cv2.dilate((cc == i).astype(np.uint8), np.ones((25, 25), np.uint8)).astype(bool) & (cc != i)
        around = np.bincount(lab[ring & (lab > 0)]).argmax() if (ring & (lab > 0)).any() else 0
        pad = 12
        lab[max(y - pad, 0):y + h + pad, max(x - pad, 0):x + w + pad][
            lab[max(y - pad, 0):y + h + pad, max(x - pad, 0):x + w + pad] == 0] = around
        hole = np.zeros(lab.shape, np.uint8)
        cv2.ellipse(hole, el, 1, -1, cv2.LINE_8)
        lab[hole == 1] = 0
        log('  round hole at (%.2f, %.2f) in, %.3f x %.3f in' %
            (el[0][0] / dpi, el[0][1] / dpi, el[1][0] / dpi, el[1][1] / dpi))
    return lab


def trace(mask, scale, speck, smooth):
    """Boolean mask -> SVG path data."""
    bm = potrace.Bitmap(~mask.astype(bool))          # potracer inverts its input
    plist = bm.trace(turdsize=speck, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
                     alphamax=1.0, opticurve=True, opttolerance=smooth)
    f = lambda p: '%.3f,%.3f' % (p.x * scale, p.y * scale)
    out, nodes = [], 0
    for curve in plist:
        out.append('M' + f(curve.start_point))
        for s in curve.segments:
            nodes += 1
            if s.is_corner:
                out.append('L%s L%s' % (f(s.c), f(s.end_point)))
            else:
                out.append('C%s %s %s' % (f(s.c1), f(s.c2), f(s.end_point)))
        out.append('Z')
    return ' '.join(out), len(plist), nodes


def write_svg(path, W, H, dpi, layers):
    """layers: list of (name, hex colour, path data), bottom layer first."""
    s = 96.0 / dpi
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<svg xmlns="http://www.w3.org/2000/svg" '
             'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
             'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" '
             'width="%.4fin" height="%.4fin" viewBox="0 0 %.3f %.3f">' % (W / dpi, H / dpi, W * s, H * s),
             '<sodipodi:namedview inkscape:document-units="in" units="in"/>']
    for name, hexc, d in layers:
        lines.append('<g inkscape:groupmode="layer" inkscape:label="%s" id="layer-%s">'
                     '<path id="%s" fill="%s" fill-rule="evenodd" stroke="none" d="%s"/></g>'
                     % (name, name, name, hexc, d))
    lines.append('</svg>')
    with open(path, 'w') as fh:
        fh.write('\n'.join(lines))


def process(path, a):
    log = print
    img = Image.open(path)
    dpi = a.dpi or float((img.info.get('dpi') or (0, 0))[0]) or 0
    if dpi < 10:
        dpi = 300.0
        log('  no resolution stored in the file, assuming 300 dpi (use --dpi to set it)')
    im = np.array(img.convert('RGBA'))
    H, W = im.shape[:2]
    rgb = im[..., :3]
    fg = im[..., 3] > 128
    if fg.all():                                     # no transparency: corner colour is the background
        corner = np.median(np.array([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]]), axis=0)
        fg = np.sqrt(((rgb.astype(np.float32) - corner) ** 2).sum(-1)) > 30
        log('  no transparency, treating corner colour %s as background' % (tuple(int(v) for v in corner),))

    palette = find_palette(rgb, fg, a.colors, a.min_share)
    if not palette:
        log('  nothing to trace'); return
    lab = label_pixels(rgb, fg, palette)
    if a.fit_circles:
        lab = fit_round_holes(lab, dpi, log)

    used, names = set(), []
    for c in palette:
        n = colour_name(c, used); used.add(n); names.append(n)
    masks = [(lab == i + 1).astype(np.uint8) for i in range(len(palette))]

    lum = [0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] for c in palette]
    key = int(np.argmin(lum)) if min(lum) < 70 else None    # the dark outline colour, painted last
    grow_px = int(round(a.grow * dpi))
    if key is not None and grow_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow_px + 1, 2 * grow_px + 1))
        for i in range(len(masks)):
            if i != key:
                masks[i] = cv2.dilate(masks[i], k) & (masks[i] | masks[key])

    stem = os.path.splitext(os.path.basename(path))[0]
    out = a.outdir or os.path.join(os.path.dirname(os.path.abspath(path)), stem + '_svg')
    os.makedirs(out, exist_ok=True)
    speck = max(2, int((a.speck * dpi) ** 2))
    order = sorted(range(len(palette)), key=lambda i: -lum[i])   # light colours at the bottom, dark on top
    layers = []
    log('  %.2f x %.2f in at %g dpi, %d colours' % (W / dpi, H / dpi, dpi, len(palette)))
    for i in order:
        d, shapes, nodes = trace(masks[i], 96.0 / dpi, speck, a.smooth)
        hexc = '#%02x%02x%02x' % palette[i]
        layers.append((names[i], hexc, d))
        write_svg(os.path.join(out, '%s_%s.svg' % (stem, names[i])), W, H, dpi, [(names[i], hexc, d)])
        note = '  (outline colour, cut and paint last)' if i == key else ''
        log('  %-10s %s  %3d shapes, %4d nodes%s' % (names[i], hexc, shapes, nodes, note))
    write_svg(os.path.join(out, stem + '_layers.svg'), W, H, dpi, layers)

    prev = np.full((H, W, 3), 255, np.uint8)
    for i in order:
        prev[masks[i] == 1] = palette[i]
    Image.fromarray(prev).save(os.path.join(out, stem + '_preview.png'))
    log('  wrote ' + out)


def main():
    p = argparse.ArgumentParser(description='Flat-colour PNG to per-colour SVG stencil files.')
    p.add_argument('images', nargs='+', help='PNG files (wildcards are fine)')
    p.add_argument('--dpi', type=float, help='resolution of the image; default is read from the file')
    p.add_argument('--colors', type=int, default=0, help='limit to the N most common colours (default: automatic)')
    p.add_argument('--min-share', type=float, default=0.01,
                   help='ignore colours covering less than this fraction of the art (default 0.01)')
    p.add_argument('--grow', type=float, default=0.013,
                   help='inches each colour runs under the dark outline (default 0.013, 0 = off)')
    p.add_argument('--speck', type=float, default=0.012, help='drop specks smaller than this, in inches (default 0.012)')
    p.add_argument('--smooth', type=float, default=0.4, help='curve smoothing, 0.2 = tight, 1.0 = loose (default 0.4)')
    p.add_argument('--fit-circles', action='store_true', help='replace round holes (lamp inserts) with clean circles')
    p.add_argument('--outdir', help='output folder (default: "<name>_svg" next to each image)')
    a = p.parse_args()
    files = [f for pat in a.images for f in (sorted(glob.glob(pat)) or [pat])]
    for f in files:
        if not os.path.isfile(f):
            print('skipping %s (not found)' % f); continue
        print(f)
        process(f, a)


if __name__ == '__main__':
    sys.exit(main())
