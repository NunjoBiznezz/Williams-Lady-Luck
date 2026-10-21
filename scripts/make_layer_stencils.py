#!/usr/bin/env python3
"""
make_layer_stencils.py - Lady Luck stencils for flat-colour artwork (the girls etc.)
==================================================================================

For artwork drawn as one layer per paint colour (e.g. "CL dancing girl.svg":
green, blue, red, black + a hidden "area (reference - no cut)" outline) this writes
one cut file per paint step into a _generated folder in the directory you run it from:

    <name> - 1 area mask.svg     covers the figure while you paint the background
    <name> - 2 green stencil.svg
    <name> - 3 blue stencil.svg   ... one per colour layer, in the file's layer order
    <name> - 5 black stencil.svg  black always last

Every file has the SAME registration marks, outside the artwork:
  layer "cut"                          the stencil openings + a small round window at each mark
  layer "pen (Tool 2) - registration"  a cross at each mark, drawn with the pen in Tool 2
  layer "outline (reference - no cut)" the figure outline, for orientation only

Trim lines: a layer in the source whose label starts with "trim" (e.g. "trim (cut only)")
holds cut-only lines - straight, polyline or curved (lines, arcs and curves, absolute or
relative, as Inkscape writes them). Each path is cut exactly as drawn, and its two open ends
run on to the sheet edges in the same shape: straight ends straight, curved ends round their circle.
It goes into the "cut" layer of EVERY sheet as "trim-line-N" (blue stroke): cut only, never
painted, to trim the film where this piece meets a neighbour (e.g. UL/UR pop bumpers along
the CC pop bumper circle, and the two straight edges of the ADVANCE CARD banner notch).
The marks are then picked from the four corners so all three stay on the artwork side.

Lining up: stick a bit of masking tape under each mark window, put the first sheet
(the area mask) in place, and dot each tape through its window with a fine pencil.
Every later sheet goes down with its windows over the same dots.
The marks are not symmetric (three corners), so a sheet can't go on rotated or flipped.

The colour openings are copied exactly from the source (same nodes); the source SVG is
never changed. The mask is the area outline shrunk by --mask-grow (default -0.005in, so
the background runs a hair under the figure's black outline), using a node-preserving
offset, so it keeps the outline's node count.

Run (from the project root):
    bash scripts/layer_stencils.sh "stencils/CL dancing girl.svg"
Options (inches):
    --mask-grow -0.005   grow (+) or shrink (-) the area mask
    --mark-offset 0.20   distance of the marks outside the artwork
    --mark-size 0.25     length of each cross arm-to-arm
    --window 0.0625      diameter of the cut window at each mark (0 = none)
    --outdir DIR         default: ./_generated
Needs: Python 3.9+, numpy, shapely
"""
import argparse, os, re, sys, math
import xml.etree.ElementTree as ET
import numpy as np
from shapely.geometry import Polygon, Point
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_stencils import path_to_rings, circ_d, SVG_NS, INK, U

SKIP = ('reference', 'no cut', 'hole', 'centerline', 'centreline', 'photo', 'grid', 'pen')

# ----------------------------------------------------------------- absolute M/L/C/Z paths
def parse_abs(d):
    """absolute M/L/C/Z path -> list of subpaths of segments (2 pts = line, 4 pts = cubic); None if other commands"""
    if re.search(r'[A-BD-KN-Ya-z]', re.sub(r'e-?\d', '', d)): return None
    out = []; cur = None; pos = start = None
    for cmd, args in re.findall(r'([MLCZ])([^MLCZ]*)', d):
        v = [float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?', args)]
        if cmd == 'M':
            cur = []; out.append(cur); pos = np.array(v[:2]); start = pos.copy()
            for i in range(2, len(v), 2): p = np.array(v[i:i + 2]); cur.append(np.array([pos, p])); pos = p
        elif cmd == 'L':
            for i in range(0, len(v), 2): p = np.array(v[i:i + 2]); cur.append(np.array([pos, p])); pos = p
        elif cmd == 'C':
            for i in range(0, len(v), 6):
                c = np.array(v[i:i + 6]).reshape(3, 2); cur.append(np.vstack([pos, c])); pos = c[2]
        elif cmd == 'Z':
            if np.linalg.norm(pos - start) > 1e-6: cur.append(np.array([pos, start.copy()]))
            pos = start
    return out

def write_abs(subs):
    s = []
    for sp in subs:
        t = 'M%.2f,%.2f' % tuple(sp[0][0])
        for g in sp:
            t += (' L%.2f,%.2f' % tuple(g[1])) if len(g) == 2 else (' C%.2f,%.2f %.2f,%.2f %.2f,%.2f' % tuple(g[1:].ravel()))
        s.append(t + ' Z')
    return ' '.join(s)

def offset_subpath(sp, d, inside_test):
    """node-preserving offset (Tiller-Hanson) of a closed subpath: d>0 grows the filled side outward"""
    Q = [sp[0][0]] + [p for g in sp for p in g[1:]]; Q = np.array(Q); n = len(Q)
    keep = [0]
    for i in range(1, n):
        if np.linalg.norm(Q[i] - Q[keep[-1]]) > 1e-6: keep.append(i)
    if np.linalg.norm(Q[keep[-1]] - Q[0]) < 1e-6: keep = keep[:-1]
    K = Q[keep]; m = len(K)
    # which side is filled? test just left of the longest edge
    L = [np.linalg.norm(K[(i + 1) % m] - K[i]) for i in range(m)]; i0 = int(np.argmax(L))
    t = (K[(i0 + 1) % m] - K[i0]) / L[i0]; nl = np.array([-t[1], t[0]]); mid = (K[i0] + K[(i0 + 1) % m]) / 2
    side = -1 if inside_test(mid + 0.25 * nl) else 1          # normal pointing away from the fill
    E = []
    for i in range(m):
        a, b = K[i], K[(i + 1) % m]; t = (b - a) / np.linalg.norm(b - a)
        E.append((a, t, np.array([-t[1], t[0]]) * side))
    NK = np.zeros_like(K)
    for i in range(m):
        a1, t1, n1 = E[i - 1]; a2, t2, n2 = E[i]
        p1 = a1 + n1 * d; p2 = a2 + n2 * d; cr = t1[0] * t2[1] - t1[1] * t2[0]
        X = K[i] + (n1 + n2) / 2 * d
        if abs(cr) > 0.035:
            s = ((p2 - p1)[0] * t2[1] - (p2 - p1)[1] * t2[0]) / cr; Y = p1 + s * t1
            if np.linalg.norm(Y - K[i]) < 12 * abs(d) + 1e-9: X = Y
        NK[i] = X
    NQ = np.zeros_like(Q); j = 0
    for i in range(n):
        while j + 1 < len(keep) and i >= keep[j + 1]: j += 1
        NQ[i] = NK[j]
    NQ[-1] = NK[0] if np.linalg.norm(Q[-1] - Q[0]) < 1e-6 else NQ[-1]
    out = []; k = 1
    for g in sp:
        Lg = len(g) - 1; out.append(np.vstack([NQ[k - 1], NQ[k:k + Lg]])); k += Lg
    return out

def evenodd_poly(d):
    acc = Polygon()
    for r in path_to_rings(d):
        if len(r) > 2: acc = acc.symmetric_difference(Polygon(r).buffer(0))
    return acc

def _arc_to_cubics(p0, rx, ry, phi, fa, fs, p1):
    """SVG elliptical arc -> list of cubic segments (each <= 90 deg)"""
    if np.allclose(p0, p1): return []
    rx, ry = abs(rx), abs(ry)
    if rx < 1e-9 or ry < 1e-9: return [np.array([p0, p1])]
    c, s_ = math.cos(phi), math.sin(phi)
    d = (p0 - p1) / 2; x1 = c * d[0] + s_ * d[1]; y1 = -s_ * d[0] + c * d[1]
    lam = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
    if lam > 1: rx *= math.sqrt(lam); ry *= math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    co = math.sqrt(max(0.0, num / (rx * rx * y1 * y1 + ry * ry * x1 * x1)))
    if fa == fs: co = -co
    cx1, cy1 = co * rx * y1 / ry, -co * ry * x1 / rx
    ctr = np.array([c * cx1 - s_ * cy1, s_ * cx1 + c * cy1]) + (p0 + p1) / 2
    ang = lambda ux, uy: math.atan2(uy, ux)
    t0 = ang((x1 - cx1) / rx, (y1 - cy1) / ry); t1 = ang((-x1 - cx1) / rx, (-y1 - cy1) / ry)
    dt = t1 - t0
    if fs and dt < 0: dt += 2 * math.pi
    if not fs and dt > 0: dt -= 2 * math.pi
    n = max(1, int(math.ceil(abs(dt) / (math.pi / 2) - 1e-9))); h = dt / n; k = 4 / 3 * math.tan(h / 4)
    E = lambda t: ctr + np.array([c * rx * math.cos(t) - s_ * ry * math.sin(t), s_ * rx * math.cos(t) + c * ry * math.sin(t)])
    dE = lambda t: np.array([-c * rx * math.sin(t) - s_ * ry * math.cos(t), -s_ * rx * math.sin(t) + c * ry * math.cos(t)])
    out = []
    for i in range(n):
        a_, b_ = t0 + i * h, t0 + (i + 1) * h
        out.append(np.array([E(a_), E(a_) + k * dE(a_), E(b_) - k * dE(b_), E(b_)]))
    out[0][0] = p0; out[-1][-1] = p1
    return out

def trim_paths(d):
    """any SVG path (M L H V C S Q T A Z, absolute or relative) -> list of open subpaths,
    each a list of segments (2 points = line, 4 points = cubic), absolute coordinates"""
    toks = re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?', d)
    i = 0; cmd = None; pos = np.zeros(2); start = np.zeros(2); subs = []; cur = None; lastc = None
    def num():
        nonlocal i; v = float(toks[i]); i += 1; return v
    def pt(rel):
        p = np.array([num(), num()]); return p + pos if rel else p
    while i < len(toks):
        if re.match(r'[A-Za-z]', toks[i]): cmd = toks[i]; i += 1
        rel = cmd.islower(); C = cmd.upper()
        if C == 'Z':
            if cur is not None and np.linalg.norm(pos - start) > 1e-6: cur.append(np.array([pos, start.copy()]))
            pos = start.copy(); lastc = None; continue
        if C == 'M':
            p = pt(rel); cur = []; subs.append(cur); pos = p; start = p.copy(); cmd = 'l' if rel else 'L'; lastc = None; continue
        if C == 'L': p = pt(rel); cur.append(np.array([pos, p])); pos = p; lastc = None
        elif C == 'H': x = num(); p = np.array([x + (pos[0] if rel else 0), pos[1]]); cur.append(np.array([pos, p])); pos = p; lastc = None
        elif C == 'V': y = num(); p = np.array([pos[0], y + (pos[1] if rel else 0)]); cur.append(np.array([pos, p])); pos = p; lastc = None
        elif C == 'C':
            c1 = pt(rel); c2 = pt(rel); p = pt(rel); cur.append(np.array([pos, c1, c2, p])); pos = p; lastc = c2
        elif C == 'S':
            c1 = 2 * pos - lastc if lastc is not None else pos.copy(); c2 = pt(rel); p = pt(rel)
            cur.append(np.array([pos, c1, c2, p])); pos = p; lastc = c2
        elif C in 'QT':
            q = pt(rel) if C == 'Q' else (2 * pos - lastc if lastc is not None else pos.copy())
            p = pt(rel); cur.append(np.array([pos, pos + 2 / 3 * (q - pos), p + 2 / 3 * (q - p), p])); pos = p; lastc = q
        elif C == 'A':
            rx, ry, rot, fa, fs = num(), num(), num(), num(), num(); p = pt(rel)
            cur += _arc_to_cubics(pos, rx, ry, math.radians(rot), int(fa), int(fs), p); pos = p; lastc = None
    return [sp for sp in subs if sp]

def _bez(g, n=24):
    if len(g) == 2: return [g[0], g[1]]
    t = np.linspace(0, 1, n + 1)[:, None]
    return list((1 - t) ** 3 * g[0] + 3 * (1 - t) ** 2 * t * g[1] + 3 * (1 - t) * t * t * g[2] + t ** 3 * g[3])

def _end_dir(g, at_start):
    """unit direction pointing OUT of the path at its start (backwards) or end (forwards)"""
    if at_start:
        for q in g[1:]:
            v = g[0] - q
            if np.linalg.norm(v) > 1e-9: return v / np.linalg.norm(v)
    else:
        for q in g[-2::-1]:
            v = g[-1] - q
            if np.linalg.norm(v) > 1e-9: return v / np.linalg.norm(v)
    return None

def _ray_exit(P, v, box):
    """distance along ray P + t v (t >= 0) to where it leaves the box (x0, y0, x1, y1)"""
    ts = []
    for k, lo, hi in ((0, box[0], box[2]), (1, box[1], box[3])):
        if abs(v[k]) > 1e-12: ts.append(max((lo - P[k]) / v[k], (hi - P[k]) / v[k]))
    return max(0.0, min(ts)) if ts else 0.0

def _run_on(seg, at_start, box):
    """continue a trim path past one of its open ends to the sheet edge, in the same curve:
    a straight end runs on straight, a curved end runs on round the circle it lies on.
    Returns (list of segments going outward from the end, end point at the sheet edge)."""
    P = seg[0] if at_start else seg[-1]
    out_dir = _end_dir(seg, at_start)
    if out_dir is None: return [], P
    if len(seg) == 4:
        b = _bez(seg, 2)                                   # start, middle, end of the curve
        A, M, B = b[0], b[1], b[2]
        den = 2 * (A[0] * (M[1] - B[1]) + M[0] * (B[1] - A[1]) + B[0] * (A[1] - M[1]))
        if abs(den) > 1e-6 * max(1.0, np.linalg.norm(B - A)) ** 2:
            sq = lambda q: q @ q
            C = np.array([sq(A) * (M[1] - B[1]) + sq(M) * (B[1] - A[1]) + sq(B) * (A[1] - M[1]),
                          sq(A) * (B[0] - M[0]) + sq(M) * (A[0] - B[0]) + sq(B) * (M[0] - A[0])]) / den
            r = np.linalg.norm(P - C)
            if r < 50 * U:                                 # a real curve, not a near-straight line
                t0 = math.atan2(P[1] - C[1], P[0] - C[0])
                # turn direction: the one whose tangent at P points outward
                sgn = 1 if np.dot(np.array([-math.sin(t0), math.cos(t0)]), out_dir) > 0 else -1
                inside = lambda t: (box[0] <= C[0] + r * math.cos(t) <= box[2]) and (box[1] <= C[1] + r * math.sin(t) <= box[3])
                step = math.radians(0.25); t = 0.0
                while t < math.pi and inside(t0 + sgn * (t + step)): t += step
                if t >= math.pi: return [], P                # circle stays on the sheet: leave the end as it is
                lo, hi = t, t + step
                for _ in range(40):
                    mid = (lo + hi) / 2
                    if inside(t0 + sgn * mid): lo = mid
                    else: hi = mid
                dt = sgn * hi
                n = max(1, int(math.ceil(abs(dt) / (math.pi / 2))))
                h = dt / n; k = 4 / 3 * math.tan(h / 4)
                E = lambda a: C + r * np.array([math.cos(a), math.sin(a)])
                D = lambda a: r * np.array([-math.sin(a), math.cos(a)])
                segs = [np.array([E(t0 + i * h), E(t0 + i * h) + k * D(t0 + i * h),
                                  E(t0 + (i + 1) * h) - k * D(t0 + (i + 1) * h), E(t0 + (i + 1) * h)]) for i in range(n)]
                segs[0][0] = P
                return segs, segs[-1][-1]
    Q = P + _ray_exit(P, out_dir, box) * out_dir
    return ([np.array([P, Q])] if np.linalg.norm(Q - P) > 1e-6 else []), Q

# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description='One stencil per colour layer + area mask, with shared registration marks.')
    ap.add_argument('svg')
    ap.add_argument('--mask-grow', type=float, default=-0.005)
    ap.add_argument('--mark-offset', type=float, default=0.20)
    ap.add_argument('--mark-size', type=float, default=0.25)
    ap.add_argument('--window', type=float, default=0.0625)
    ap.add_argument('--outdir')
    a = ap.parse_args()

    root = ET.parse(a.svg).getroot()
    layers = []; area = None; trim_src = []
    for g in root.iter(f'{{{SVG_NS}}}g'):
        if g.get(f'{{{INK}}}groupmode') != 'layer': continue
        lab = (g.get(f'{{{INK}}}label') or g.get('id') or '').strip()
        paths = [p for p in g.iter(f'{{{SVG_NS}}}path') if p.get('d')]
        if not paths: continue
        if lab.lower().startswith('area'): area = paths; continue
        if lab.lower().startswith('trim'):
            if g.get('transform') or any(p.get('transform') for p in paths):
                print('  WARNING: trim layer/path has a transform - apply it in Inkscape (Path > Object to Path / ungroup) so the line is in file units')
            for p in paths:
                lab_p = (p.get(f'{{{INK}}}label') or p.get('id') or 'trim').strip()
                subs = trim_paths(p.get('d'))
                if not subs: print(f'  WARNING: trim path {p.get("id")} has no segments - skipped')
                for k, sp in enumerate(subs):
                    trim_src.append((lab_p if len(subs) == 1 else f'{lab_p} part {k + 1}', sp))
            continue
        if any(w in lab.lower() for w in SKIP): continue
        fill = '#888'
        m = re.search(r'fill:\s*(#[0-9a-fA-F]{3,6})', paths[0].get('style', '')) or re.search(r'(#[0-9a-fA-F]{6})', paths[0].get('fill', ''))
        if m: fill = m.group(1)
        layers.append((lab, fill, paths))
    if not layers: sys.exit('no colour layers found')
    layers.sort(key=lambda L: L[0].lower() == 'black')          # black always last

    # geometry for bounds / reporting
    geo = {lab: evenodd_poly(' '.join(p.get('d') for p in ps)) for lab, _, ps in layers}
    allg = Polygon()
    for g in geo.values(): allg = allg.union(g)
    area_d = ' '.join(p.get('d') for p in area) if area else None
    if area_d: allg = allg.union(evenodd_poly(area_d))
    minx, miny, maxx, maxy = allg.bounds

    # registration marks: three corners (top-left, top-right, bottom-left), outside the art
    off = a.mark_offset * U; h = a.mark_size * U / 2; wr = a.window * U / 2
    corners = [(minx - off, miny - off), (maxx + off, miny - off), (minx - off, maxy + off), (maxx + off, maxy + off)]
    pad = max(h, wr) + 0.1 * U
    vx, vy = minx - off - pad, miny - off - pad
    vw, vh = (maxx - minx) + 2 * (off + pad), (maxy - miny) + 2 * (off + pad)

    # trim lines (source layer "trim ..."): cut exactly as drawn; open ends run straight on to the sheet edges
    from shapely.geometry import LineString, box as sbox
    from shapely.ops import polygonize, unary_union
    sheet = (vx, vy, vx + vw, vy + vh)
    trims = []        # (label, path d, sampled polyline)
    art_region = sbox(*sheet)
    for lab, sp in trim_src:
        P0, P1 = sp[0][0], sp[-1][-1]
        d0, d1 = _end_dir(sp[0], True), _end_dir(sp[-1], False)
        closed = np.linalg.norm(P1 - P0) < 1e-6
        head, E0 = ([], P0) if closed else _run_on(sp[0], True, sheet)
        tail, E1 = ([], P1) if closed else _run_on(sp[-1], False, sheet)
        head = [g[::-1] for g in head[::-1]]               # run from the sheet edge in to P0
        full = head + list(sp) + tail
        dd = f'M{E0[0]:.2f},{E0[1]:.2f}'
        pts = [E0]
        for g in full:
            dd += (f' L{g[1][0]:.2f},{g[1][1]:.2f}' if len(g) == 2 else
                   ' C%.2f,%.2f %.2f,%.2f %.2f,%.2f' % tuple(g[1:].ravel()))
            pts += _bez(g)[1:]
        # directions at the sheet edge, for pushing the split line just past it
        d0 = _end_dir(full[0], True) if full else d0
        d1 = _end_dir(full[-1], False) if full else d1
        line = LineString([tuple(q) for q in pts])
        trims.append((lab, dd, line))
        # the art side of this trim: split the sheet by the line (ends pushed just past the edges)
        if not closed:
            ext = LineString([tuple(E0 + 2 * d0)] + [tuple(q) for q in pts] + [tuple(E1 + 2 * d1)])
            parts = list(polygonize(unary_union([sbox(*sheet).exterior, ext])))
            if len(parts) > 1:
                keep = max(parts, key=lambda q: q.intersection(allg).area)
                art_region = art_region.intersection(keep)
    def art_side(pt, clear=0.0):
        q = Point(pt)
        return art_region.contains(q) and all(t[2].distance(q) >= clear for t in trims)
    marks = [c for c in corners if art_side(c, h + wr)][:3]
    if len(marks) < 3:
        # trims cut off corners: pick 3 points round the mark rectangle (same offset from the art),
        # spread as far apart as possible, triangle with unequal sides so a sheet can't go on flipped
        x0, y0, x1, y1 = minx - off, miny - off, maxx + off, maxy + off
        cand = []
        for k in range(17):
            f = k / 16
            cand += [(x0 + f * (x1 - x0), y0), (x0 + f * (x1 - x0), y1), (x0, y0 + f * (y1 - y0)), (x1, y0 + f * (y1 - y0))]
        cand = [c for c in dict.fromkeys(cand) if art_side(c, h + wr)]
        best = None
        from itertools import combinations
        for A, B, C in combinations(cand, 3):
            l = sorted([math.dist(A, B), math.dist(B, C), math.dist(A, C)])
            if l[1] - l[0] < 0.1 * U or l[2] - l[1] < 0.1 * U: continue      # keep it lopsided
            area = abs((B[0] - A[0]) * (C[1] - A[1]) - (C[0] - A[0]) * (B[1] - A[1])) / 2
            if best is None or area > best[0]: best = (area, [A, B, C])
        if best:
            marks = best[1]
            print('  trim lines cut off the corners: marks moved along the sheet edges to ' +
                  ', '.join(f'({x / U:.2f}, {y / U:.2f}) in' for x, y in marks))
        else:
            print('  WARNING: trim lines leave no room for 3 marks; using the default corners')
            marks = corners[:3]
    pen = '\n'.join(f'<path id="mark{i + 1}" inkscape:label="mark {i + 1}" fill="none" stroke="#c00" stroke-width="1" '
                    f'd="M{x - h:.2f},{y:.2f} L{x + h:.2f},{y:.2f} M{x:.2f},{y - h:.2f} L{x:.2f},{y + h:.2f}"/>'
                    for i, (x, y) in enumerate(marks))
    windows = [circ_d(x, y, wr) for x, y in marks] if wr > 0 else []

    stem = os.path.splitext(os.path.basename(a.svg))[0]
    outdir = a.outdir or os.path.join(os.getcwd(), '_generated')
    os.makedirs(outdir, exist_ok=True)
    outline = (f'<g inkscape:groupmode="layer" id="outline" inkscape:label="outline (reference - no cut)">'
               f'<path fill="none" stroke="#999" stroke-width="0.6" stroke-dasharray="4 3" d="{area_d}"/></g>\n') if area_d else ''

    def write(step, kind, cut_paths, nodes, note, colour, pieces):
        fn = os.path.join(outdir, f'{stem} - {step} {kind}.svg')
        cut = '\n'.join(f'<path id="{pid}" fill="{colour}" fill-opacity="0.45" fill-rule="evenodd" stroke="#000" stroke-width="0.8" d="{d}"/>'
                        for pid, d in cut_paths)
        for i, (lab, dd, _) in enumerate(trims):
            cut += (f'\n<path id="trim-line-{i + 1}" inkscape:label="{lab} (cut, no paint)" fill="none" '
                    f'stroke="#0070c0" stroke-width="1.2" d="{dd}"/>')
        cut += '\n' + '\n'.join(f'<path id="mark{i + 1}-window" inkscape:label="mark {i + 1} window" fill="none" stroke="#000" stroke-width="0.8" d="{w}"/>'
                                for i, w in enumerate(windows))
        svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
               f'<svg xmlns="{SVG_NS}" xmlns:inkscape="{INK}" width="{vw / U:.4f}in" height="{vh / U:.4f}in" '
               f'viewBox="{vx:.2f} {vy:.2f} {vw:.2f} {vh:.2f}">\n'
               f'<!-- {stem} - step {step}: {kind}. Generated by make_layer_stencils.py. 300 units = 1 in, same coordinates as the source. '
               f'{note} Cut layer "cut"; draw layer "pen (Tool 2) - registration" with the pen; the outline layer is reference only. -->\n'
               f'{outline}'
               f'<g inkscape:groupmode="layer" id="cut" inkscape:label="cut">\n{cut}\n</g>\n'
               f'<g inkscape:groupmode="layer" id="pen" inkscape:label="pen (Tool 2) - registration">\n{pen}\n</g>\n</svg>\n')
        open(fn, 'w').write(svg)
        print(f'  {os.path.basename(fn)}: {nodes} nodes, {pieces}')

    print(f'{a.svg}: {len(layers)} colour layer(s), art {(maxx - minx) / U:.2f} x {(maxy - miny) / U:.2f} in, '
          f'sheet {vw / U:.2f} x {vh / U:.2f} in, {len(marks)} marks')
    for i, (lab, dd, line) in enumerate(trims):
        x = line.intersection(allg.buffer(-1.0)).length / U   # running along an art edge is fine
        print(f'  trim line {i + 1} ({lab}): {line.length / U:.2f} in' + (f'  WARNING: crosses {x:.3f} in of artwork' if x > 0.005 else ', clear of the artwork'))
    step = 1
    if area_d:
        subs = parse_abs(area_d)
        apoly = evenodd_poly(area_d)
        if subs is not None:
            grown = [offset_subpath(sp, a.mask_grow * U, lambda p: apoly.contains(Point(p))) for sp in subs]
            md = write_abs(grown); nodes = sum(len(sp) for sp in grown)
        else:   # fall back: plain buffer
            from make_stencils import geom_to_d, buf
            md, nodes = geom_to_d(buf(apoly, a.mask_grow * U))
        write(step, 'area mask', [('area-mask', md)], nodes,
              f'Area outline grown {a.mask_grow}in. Cut it out and keep the piece that drops out: that is the mask '
              f'(stick it on the figure, paint the background, peel it off).', '#f6e39c', 'one mask piece')
        step += 1
    else:
        print('  (no "area" layer - no mask made)')
    for lab, fill, ps in layers:
        cps = [(p.get('id') or f'{lab}-{i + 1}', p.get('d')) for i, p in enumerate(ps)]
        nodes = sum(len(re.findall(r'[LCAQSHVTlcaqshvt]', d)) for _, d in cps)
        g = geo[lab]; polys = [q for q in getattr(g, 'geoms', [g]) if q.area > 0.001 * U * U]   # ignore hairline slivers
        holes = sum(len(p.interiors) for p in polys if p.geom_type == 'Polygon')
        pieces = f'{len(polys)} opening(s)' + (f', {holes} loose film island(s) inside openings - keep them on transfer tape' if holes else '')
        write(step, f'{lab} stencil', cps, nodes, f'Paint {lab} through the openings.', fill, pieces)
        step += 1

if __name__ == '__main__':
    main()
