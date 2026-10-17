#!/usr/bin/env python3
"""
stencil_rectify.py
Fix perspective and set true scale on photos taken over graph paper,
so they import into Silhouette Studio at real-world size for tracing.

AUTOMATIC MODE (default)
  The script first tries to find the grid marks (+ crosses or line crossings)
  by itself and fits them all - no clicking needed. If it cannot, it falls back
  to the manual clicking below (or force that with --manual).

MANUAL MODE
  1. A window opens with your photo. Click 4 grid intersections that form a
     rectangle on the graph paper, in ANY order - the script works out
     which is top-left, top-right, bottom-right and bottom-left.
     Pick points as far apart as possible (near the photo's edges) for accuracy.
     A magnifier follows the cursor so you can land exactly on the line crossing.
  2. Press ENTER, then type how many squares wide and tall that rectangle is.
  3. The script straightens the photo, scales it so 1 inch = --dpi pixels, and
     saves  <name>_rectified.png  (with DPI stored in the file)
     plus   <name>_check.png       (same image with a red grid drawn on top --
                                    if the red lines sit on the paper's lines,
                                    it's accurate).
  Your clicks are saved in <name>_points.json, so re-running reuses them
  (use --repick to click again).

KEYS IN THE WINDOW
  click  = place point      u = undo last point      r = reset
  ENTER  = accept           s = skip this photo      q / ESC = quit

SETUP (once, in Terminal on your Mac)
  python3 -m pip install opencv-python numpy pillow

EXAMPLES
  python3 stencil_rectify.py photo.jpg
  python3 stencil_rectify.py ~/Pinball/photos/*.jpg --dpi 300
  python3 stencil_rectify.py photo.jpg --crop --margin 0.5   # keep only the clicked area + 1/2"
"""

import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image

ORDER = ["TOP-LEFT", "TOP-RIGHT", "BOTTOM-RIGHT", "BOTTOM-LEFT"]
MAX_OUTPUT_PX = 20000  # safety cap on output size


# ---------------------------------------------------------------- point picking
def pick_points(img, title):
    h, w = img.shape[:2]
    scale = min(1.0, 1200 / max(w, h))
    base = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    pts = []
    mouse = [0, 0]

    def on_mouse(event, x, y, flags, param):
        mouse[0], mouse[1] = x, y
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < 4:
            pts.append((x / scale, y / scale))

    win = "Click grid points - " + title
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(win, on_mouse)

    while True:
        frame = base.copy()
        # existing points + outline
        for i, (px, py) in enumerate(pts):
            p = (int(px * scale), int(py * scale))
            cv2.circle(frame, p, 6, (0, 0, 255), 2)
            cv2.putText(frame, str(i + 1), (p[0] + 8, p[1] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        if len(pts) > 1:
            poly = np.array([(int(x * scale), int(y * scale)) for x, y in pts], np.int32)
            cv2.polylines(frame, [poly], len(pts) == 4, (0, 200, 255), 1)

        # instructions
        msg = (f"Click a corner grid crossing, any order ({len(pts) + 1}/4)"
               if len(pts) < 4 else "ENTER = accept   u = undo   r = reset")
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 30), (0, 0, 0), -1)
        cv2.putText(frame, msg, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        # magnifier: 4x zoom of full-res image around the cursor
        mx, my = int(mouse[0] / scale), int(mouse[1] / scale)
        r = 30
        x0, y0 = max(mx - r, 0), max(my - r, 0)
        patch = img[y0:my + r, x0:mx + r]
        if patch.size:
            zoom = cv2.resize(patch, (patch.shape[1] * 5, patch.shape[0] * 5),
                              interpolation=cv2.INTER_NEAREST)
            cy, cx = (my - y0) * 5, (mx - x0) * 5
            cv2.line(zoom, (cx, 0), (cx, zoom.shape[0]), (0, 0, 255), 1)
            cv2.line(zoom, (0, cy), (zoom.shape[1], cy), (0, 0, 255), 1)
            zh, zw = zoom.shape[:2]
            # put magnifier in the corner away from the cursor
            ox = frame.shape[1] - zw - 5 if mouse[0] < frame.shape[1] / 2 else 5
            oy = 35
            if oy + zh <= frame.shape[0] and ox + zw <= frame.shape[1]:
                frame[oy:oy + zh, ox:ox + zw] = zoom
                cv2.rectangle(frame, (ox, oy), (ox + zw, oy + zh), (255, 255, 255), 1)

        cv2.imshow(win, frame)
        key = cv2.waitKey(20) & 0xFF
        if key in (13, 10) and len(pts) == 4:
            break
        if key == ord("u") and pts:
            pts.pop()
        elif key == ord("r"):
            pts.clear()
        elif key == ord("s"):
            pts = None
            break
        elif key in (ord("q"), 27):
            cv2.destroyAllWindows()
            sys.exit("Quit.")

    cv2.destroyWindow(win)
    cv2.waitKey(1)
    return pts


def ask_squares(default):
    hint = f" [{default}]" if default else ""
    while True:
        s = input(f"  Squares across x down for that rectangle (e.g. 30x20){hint}: ").strip().lower()
        if not s and default:
            s = default
        try:
            nx, ny = (float(v) for v in s.replace(" ", "").split("x"))
            if nx > 0 and ny > 0:
                return nx, ny, s
        except ValueError:
            pass
        print("  Please enter like 30x20")


# ---------------------------------------------------------------- rectify
def order_corners(pts):
    """Sort 4 points into TL, TR, BR, BL regardless of click order."""
    p = np.float64(pts)
    c = p.mean(axis=0)
    # sort by angle around the centre: TL -> TR -> BR -> BL (image y points down)
    p = p[np.argsort(np.arctan2(p[:, 1] - c[1], p[:, 0] - c[0]))]
    start = np.argmin(p.sum(axis=1))          # top-left has the smallest x + y
    return np.roll(p, -start, axis=0)


def rectify(img, src_pts, nx, ny, grid_in, dpi, crop, margin_in):
    sq = grid_in * dpi                      # pixels per grid square
    W, H = nx * sq, ny * sq
    src = np.float32(order_corners(src_pts))
    dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    M = cv2.getPerspectiveTransform(src, dst)

    if crop:
        m = margin_in * dpi
        x_min, y_min, x_max, y_max = -m, -m, W + m, H + m
    else:
        h, w = img.shape[:2]
        corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
        t = cv2.perspectiveTransform(corners, M).reshape(-1, 2)
        x_min, y_min = t.min(axis=0)
        x_max, y_max = t.max(axis=0)

    out_w, out_h = int(round(x_max - x_min)), int(round(y_max - y_min))
    if out_w > MAX_OUTPUT_PX or out_h > MAX_OUTPUT_PX:
        print("  Whole photo would be too large after straightening (steep angle?) - "
              "cropping to clicked area + margin instead.")
        return rectify(img, src_pts, nx, ny, grid_in, dpi, True, margin_in)

    T = np.array([[1, 0, -x_min], [0, 1, -y_min], [0, 0, 1]], dtype=np.float64)
    out = cv2.warpPerspective(img, T @ M, (out_w, out_h),
                              flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
    return out, (-x_min, -y_min), sq


# ---------------------------------------------------------------- automatic grid detection
def _detect_crosses(gray, arm):
    """Find '+' marks or line crossings; returns Nx2 points (in gray's coordinates)."""
    bg = cv2.GaussianBlur(gray, (0, 0), 15)
    dark = ((bg.astype(np.int16) - gray) > 30).astype(np.float32)   # works in shadows too
    n = 2 * arm + 1
    T = np.zeros((n, n), np.float32)
    T[arm, 2:n - 2] = 1
    T[2:n - 2, arm] = 1
    T = cv2.dilate(T, np.ones((2, 2), np.uint8))
    r = cv2.matchTemplate(dark, T, cv2.TM_CCOEFF_NORMED)
    peaks = (r == cv2.dilate(r, np.ones((n, n), np.uint8))) & (r > 0.45)
    ys, xs = np.where(peaks)
    return np.c_[xs + arm, ys + arm].astype(np.float64)


def _fit_grid(pts):
    """Grow a grid fit from a seed cell. Returns (H pixel->cell, inliers, rms_cells) or None."""
    if len(pts) < 12:
        return None
    d = np.hypot(*(pts[:, None, :] - pts[None, :, :]).transpose(2, 0, 1))
    np.fill_diagonal(d, np.inf)
    spacing = np.median(d.min(1))

    def find(p):
        k = np.hypot(*(pts - p).T)
        i = k.argmin()
        return i if k[i] < 0.25 * spacing else None

    # seed: a point with right / down / diagonal neighbours, in the densest area
    density = (d < 3 * spacing).sum(1)
    for i in np.argsort(-density):
        p = pts[i]
        j, k, l = find(p + [spacing, 0]), find(p + [0, spacing]), find(p + [spacing, spacing])
        if None not in (j, k, l):
            break
    else:
        return None

    src = np.float32([pts[i], pts[j], pts[l], pts[k]])
    H = cv2.getPerspectiveTransform(src, np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]))
    for it in range(60):
        uv = cv2.perspectiveTransform(pts.reshape(-1, 1, 2), H).reshape(-1, 2)
        r = np.round(uv)
        ok = (np.abs(uv - r).max(1) < 0.15) & (np.abs(r).max(1) <= 2 + it)
        if ok.sum() >= 4:
            Hn, _ = cv2.findHomography(pts[ok], r[ok], 0)
            if Hn is not None:            # None = points all in a line; keep the last good fit
                H = Hn
    for tol in (0.1, 0.06):  # final tightening, drops stray matches in the artwork
        uv = cv2.perspectiveTransform(pts.reshape(-1, 1, 2), H).reshape(-1, 2)
        r = np.round(uv)
        ok = np.abs(uv - r).max(1) < tol
        if ok.sum() < 12:
            return None
        H, _ = cv2.findHomography(pts[ok], r[ok], 0)
        if H is None:
            return None
    res = cv2.perspectiveTransform(pts[ok].reshape(-1, 1, 2), H).reshape(-1, 2) - r[ok]
    return H, int(ok.sum()), float(np.sqrt((res ** 2).mean()))


def auto_grid(img):
    """Returns H mapping full-res pixels -> grid-cell coordinates, or None."""
    h, w = img.shape[:2]
    f = 2000 / max(h, w)
    gray = cv2.cvtColor(cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA),
                        cv2.COLOR_BGR2GRAY)
    best = None
    for arm in (8, 12, 16, 22, 30):
        fit = _fit_grid(_detect_crosses(gray, arm))
        if fit and fit[2] < 0.05 and (best is None or fit[1] > best[1]):
            best = fit
    if not best:
        return None
    H, n, rms = best
    S = np.diag([f, f, 1.0])            # full-res -> detection scale
    return H @ S, n, rms


def rectify_auto(img, Hc, grid_in, dpi):
    sq = grid_in * dpi
    h, w = img.shape[:2]
    c = cv2.perspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2),
                                 Hc).reshape(-1, 2)
    # keep the area the photo fully covers (no blank wedges)
    u0, u1 = max(c[0, 0], c[3, 0]), min(c[1, 0], c[2, 0])
    v0, v1 = max(c[0, 1], c[1, 1]), min(c[2, 1], c[3, 1])
    W, Ht = int((u1 - u0) * sq), int((v1 - v0) * sq)
    if W <= 0 or Ht <= 0 or W > MAX_OUTPUT_PX or Ht > MAX_OUTPUT_PX:
        return None
    S = np.array([[sq, 0, -u0 * sq], [0, sq, -v0 * sq], [0, 0, 1]])
    out = cv2.warpPerspective(img, S @ Hc, (W, Ht), flags=cv2.INTER_CUBIC,
                              borderValue=(255, 255, 255))
    return out, (-u0 * sq, -v0 * sq), sq


def draw_check(img, origin, sq):
    chk = img.copy()
    t = max(1, int(sq // 60))  # line thickness scales with resolution
    h, w = chk.shape[:2]
    ox, oy = origin
    k0 = int(np.floor(-ox / sq))
    for k in range(k0, int((w - ox) / sq) + 2):
        x = int(round(ox + k * sq))
        if 0 <= x < w:
            cv2.line(chk, (x, 0), (x, h), (0, 0, 255), t)
    k0 = int(np.floor(-oy / sq))
    for k in range(k0, int((h - oy) / sq) + 2):
        y = int(round(oy + k * sq))
        if 0 <= y < h:
            cv2.line(chk, (0, y), (w, y), (0, 0, 255), t)
    return chk


def save_png(bgr, path, dpi):
    Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).save(path, dpi=(dpi, dpi))


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Straighten and scale graph-paper photos for stencils.")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--grid", type=float, default=0.5, help="grid spacing in inches (default 0.5)")
    ap.add_argument("--dpi", type=int, default=300, help="output pixels per inch (default 300)")
    ap.add_argument("--crop", action="store_true", help="keep only the clicked rectangle + margin")
    ap.add_argument("--margin", type=float, default=0.5, help="margin in inches with --crop (default 0.5)")
    ap.add_argument("--repick", action="store_true", help="ignore saved points and click again")
    ap.add_argument("--points", help='non-interactive: "x,y;x,y;x,y;x,y" (TL,TR,BR,BL)')
    ap.add_argument("--squares", help='non-interactive: e.g. "30x20"')
    ap.add_argument("--manual", action="store_true", help="skip automatic grid detection and click points")
    ap.add_argument("--outdir", help="output folder (default: next to each photo)")
    a = ap.parse_args()

    last_sq = a.squares
    for path in a.images:
        print(f"\n{os.path.basename(path)}")
        img = cv2.imread(path)
        if img is None:
            print("  Could not read - skipped.")
            continue

        stem = os.path.splitext(path)[0]
        if a.outdir:
            os.makedirs(a.outdir, exist_ok=True)
            stem = os.path.join(a.outdir, os.path.basename(stem))
        side = stem + "_points.json"

        if not (a.manual or a.points or a.crop):
            fit = auto_grid(img)
            res = fit and rectify_auto(img, fit[0], a.grid, a.dpi)
            if res:
                out, origin, sq = res
                save_png(out, stem + "_rectified.png", a.dpi)
                save_png(draw_check(out, origin, sq), stem + "_check.png", a.dpi)
                h, w = out.shape[:2]
                print(f"  Auto grid: {fit[1]} crossings found, avg error "
                      f"{fit[2] * a.grid:.3f}\" ({fit[2] * a.grid * 25.4:.2f} mm)")
                print(f"  Saved {os.path.basename(stem)}_rectified.png  "
                      f"({w / a.dpi:.2f}\" x {h / a.dpi:.2f}\" at {a.dpi} DPI)")
                print(f"  Check {os.path.basename(stem)}_check.png - red lines should sit on the grid.")
                continue
            print("  Couldn't detect the grid automatically - click points instead.")

        pts, sq_str = None, None
        if a.points:
            pts = [tuple(map(float, p.split(","))) for p in a.points.split(";")]
            sq_str = a.squares
        elif os.path.exists(side) and not a.repick:
            with open(side) as f:
                d = json.load(f)
            pts, sq_str = d["points"], d["squares"]
            print(f"  Using saved points ({sq_str} squares). Use --repick to redo.")
        else:
            pts = pick_points(img, os.path.basename(path))
            if pts is None:
                print("  Skipped.")
                continue

        if sq_str:
            nx, ny = (float(v) for v in sq_str.lower().split("x"))
        else:
            nx, ny, sq_str = ask_squares(last_sq)
        last_sq = sq_str

        with open(side, "w") as f:
            json.dump({"points": pts, "squares": sq_str}, f, indent=1)

        out, origin, sq = rectify(img, pts, nx, ny, a.grid, a.dpi, a.crop, a.margin)
        save_png(out, stem + "_rectified.png", a.dpi)
        save_png(draw_check(out, origin, sq), stem + "_check.png", a.dpi)

        h, w = out.shape[:2]
        print(f"  Saved {os.path.basename(stem)}_rectified.png  "
              f"({w / a.dpi:.2f}\" x {h / a.dpi:.2f}\" at {a.dpi} DPI)")
        print(f"  Check {os.path.basename(stem)}_check.png - red lines should sit on the grid.")


if __name__ == "__main__":
    main()
