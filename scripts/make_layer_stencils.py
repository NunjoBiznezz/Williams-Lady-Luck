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
holds straight lines (each path: first point to last point). Each is run out to the sheet
edges and added to the "cut" layer of EVERY sheet as "trim-line-N" (blue stroke): cut
only, never painted, to trim the film where this piece meets a neighbour (e.g. UL/UR pop
bumpers where they meet the CC pop bumper). The marks are then picked from the four
corners so all three stay on the artwork side of every trim line.

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

def line_ends(d):
    """first and last point of a path made of M/L/H/V commands (absolute or relative, as Inkscape writes them)"""
    pos = np.zeros(2); first = None
    for cmd, args in re.findall(r'([MmLlHhVvZz])([^MmLlHhVvZz]*)', d):
        v = [float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?', args)]
        if cmd in 'Mm' or cmd in 'Ll':
            for i in range(0, len(v) - 1, 2):
                q = np.array(v[i:i + 2]); pos = q if cmd in 'ML' or (cmd == 'm' and first is None and i == 0) else pos + q
                if first is None: first = pos.copy()
        elif cmd in 'Hh':
            for x in v: pos = np.array([x, pos[1]]) if cmd == 'H' else pos + [x, 0]
        elif cmd in 'Vv':
            for y in v: pos = np.array([pos[0], y]) if cmd == 'V' else pos + [0, y]
    if re.search(r'[^MmLlHhVvZz\s\d.,eE+-]', d) or first is None or np.linalg.norm(pos - first) < 1e-6: return None
    return first, pos

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
                ends = line_ends(p.get('d'))
                if ends: trim_src.append(((p.get(f'{{{INK}}}label') or p.get('id') or 'trim').strip(), *ends))
                else: print(f'  WARNING: trim path {p.get("id")} skipped - draw it as straight line segment(s)')
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

    # trim lines (source layer "trim ..."): straight cut lines run out to the sheet edges
    trims = []
    for lab, P, Q in trim_src:
        dv = Q - P; ts = []
        for k, lo, hi in ((0, vx, vx + vw), (1, vy, vy + vh)):
            if abs(dv[k]) > 1e-9: ts += [(lo - P[k]) / dv[k], (hi - P[k]) / dv[k]]
        ok = [t for t in ts if vx - 1e-6 <= (P + t * dv)[0] <= vx + vw + 1e-6 and vy - 1e-6 <= (P + t * dv)[1] <= vy + vh + 1e-6]
        trims.append((lab, P + min(ok) * dv, P + max(ok) * dv))
    def art_side(pt, clear=0.0):
        c = np.array(allg.representative_point().coords[0])
        for _, A, B in trims:
            side = lambda q: (B[0] - A[0]) * (q[1] - A[1]) - (B[1] - A[1]) * (q[0] - A[0])
            dist = abs(side(pt)) / np.linalg.norm(B - A)
            if side(pt) * side(c) <= 0 or dist < clear: return False
        return True
    marks = [c for c in corners if art_side(c, h + wr)][:3]
    if len(marks) < 3:
        print('  WARNING: trim lines leave fewer than 3 clear corners for marks; using the default corners')
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
        for i, (lab, A, B) in enumerate(trims):
            cut += (f'\n<path id="trim-line-{i + 1}" inkscape:label="{lab} (cut, no paint)" fill="none" '
                    f'stroke="#0070c0" stroke-width="1.2" d="M{A[0]:.2f},{A[1]:.2f} L{B[0]:.2f},{B[1]:.2f}"/>')
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
    from shapely.geometry import LineString
    for i, (lab, A, B) in enumerate(trims):
        x = LineString([tuple(A), tuple(B)]).intersection(allg).length / U
        print(f'  trim line {i + 1} ({lab}): {np.linalg.norm(B - A) / U:.2f} in' + (f'  WARNING: crosses {x:.3f} in of artwork' if x > 0.005 else ', clear of the artwork'))
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
        g = geo[lab]; polys = list(getattr(g, 'geoms', [g]))
        holes = sum(len(p.interiors) for p in polys if p.geom_type == 'Polygon')
        pieces = f'{len(polys)} opening(s)' + (f', {holes} loose film island(s) inside openings - keep them on transfer tape' if holes else '')
        write(step, f'{lab} stencil', cps, nodes, f'Paint {lab} through the openings.', fill, pieces)
        step += 1

if __name__ == '__main__':
    main()
