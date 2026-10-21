#!/usr/bin/env python3
"""
make_stencils.py - Lady Luck playfield stencil generator
=========================================================

Reads a source SVG that has a "centerline" layer (the centre of the keyline
around a painted area) and writes cut-ready SVG files into a _generated folder in the directory the
script is run from (run it from the project root, so the outputs land in
./_generated/, beside scripts/). _generated is in .gitignore: these files are
throw-away outputs - remake them from the source instead of editing them.

  <name> - area stencil.svg    film with the area cut out (paint the area colour,
                               e.g. cream). The piece that drops out of this cut
                               is the matching area MASK - keep it on its backing.
  <name> - area mask.svg       the same shape again, in case you need to recut the
                               mask on its own (can be grown/shrunk separately).
  <name> - border stencil.svg  the keyline band (centre line +/- half the line
                               width, plus overlap) for painting the border colour.

Every output has:
  layer "cut"                          the lines to cut
  layer "holes (reference - no cut)"   the registration marks, for lining up
and alignment windows (cut) 0.02in smaller than the real holes inside the area,
so you can see the holes through clear stencil film.

Paths are written clean: straight edges are single lines, rounded corners are a
single arc (1-2 curves), circles are 4-node circles.

Source SVG conventions (300 units = 1 inch)
-------------------------------------------
  <g id="centerline" data-width="0.06in">  one closed path per area; data-width is
                                           the painted keyline width
                                           a path may have its own data-width (nested
                                           keylines of another width, e.g. a card)
                                           a closed path with id "noborder..." marks a
                                           region with no border (keyline stops there,
                                           e.g. under a saucer ring); it is not an area
  <g id="holes">  registration marks: groups "postN" (11/32in outline + screw hole)
                  and paths "holeN"

Usage
-----
  (from the project root)
  python scripts/make_stencils.py "stencils/UL slingshot.svg"
  python scripts/make_stencils.py "stencils/UL slingshot.svg" --overlap 0.005
  python scripts/make_stencils.py "stencils/UL slingshot.svg" --area-grow 0.01 --only area

Options (all in inches)
  --width W        keyline width (default: data-width in the file, else 0.06)
  --overlap X      border stencil extra on each side (default 0.005)
  --area-grow X    grow the area stencil past the centre line (default 0)
  --mask-grow X    grow the area mask (default 0; negative shrinks)
  --window-margin  how much smaller than the hole a window is (default 0.02)
  --min-window D   smallest hole diameter that gets a window (default 0.25)
  --windows LIST   comma list of hole ids to use as windows, or "none"
                   (default: every round hole >= --min-window inside the area; posts never)
  --only area|mask|border   make just one of the outputs
  --outdir DIR     where to write (default: _generated in the current directory)

Needs: Python 3.9+, numpy, shapely  (pip install numpy shapely)
"""
import argparse, math, os, re, sys
import xml.etree.ElementTree as ET
import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

U = 300.0                      # SVG units per inch
SVG_NS = 'http://www.w3.org/2000/svg'
INK = 'http://www.inkscape.org/namespaces/inkscape'
K = 0.5522847498               # circle-as-4-cubics constant

# ----------------------------------------------------------------- SVG reading
def _num_tokens(s):
    return re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?', s)

def _arc_points(p0, rx, ry, phi, fa, fs, p1, n=48):
    """sample an SVG elliptical arc (endpoint form)"""
    x1, y1 = p0; x2, y2 = p1
    if rx == 0 or ry == 0: return [p1]
    phi = math.radians(phi); c, s = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = c * dx + s * dy, -s * dx + c * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1p**2 / rx**2 + y1p**2 / ry**2
    if lam > 1: rx *= math.sqrt(lam); ry *= math.sqrt(lam)
    num = rx**2 * ry**2 - rx**2 * y1p**2 - ry**2 * x1p**2
    den = rx**2 * y1p**2 + ry**2 * x1p**2
    co = math.sqrt(max(0, num / den)) if den else 0
    if fa == fs: co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx = c * cxp - s * cyp + (x1 + x2) / 2; cy = s * cxp + c * cyp + (y1 + y2) / 2
    def ang(u, v):
        a = math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]); return a
    t1 = ang((1, 0), ((x1p - cxp) / rx, (y1p - cyp) / ry))
    dt = ang(((x1p - cxp) / rx, (y1p - cyp) / ry), ((-x1p - cxp) / rx, (-y1p - cyp) / ry))
    if not fs and dt > 0: dt -= 2 * math.pi
    if fs and dt < 0: dt += 2 * math.pi
    m = max(4, int(abs(dt) / (2 * math.pi) * n * 4))
    out = []
    for k in range(1, m + 1):
        t = t1 + dt * k / m
        out.append((cx + rx * math.cos(t) * c - ry * math.sin(t) * s, cy + rx * math.cos(t) * s + ry * math.sin(t) * c))
    return out

def _bez(p0, p1, p2, p3, n):
    t = np.linspace(0, 1, n + 1)[1:, None]
    p0, p1, p2, p3 = map(np.asarray, (p0, p1, p2, p3))
    return list(map(tuple, (1 - t)**3 * p0 + 3 * (1 - t)**2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3 * p3))

def path_to_rings(d, step=0.5):
    """SVG path data -> list of closed point lists (dense samples)"""
    tok = _num_tokens(d); i = 0; cmd = None
    rings = []; cur = []; pos = (0.0, 0.0); start = (0.0, 0.0); lastc = None; lastq = None
    def nxt():
        nonlocal i; v = float(tok[i]); i += 1; return v
    def seglen(*pts):
        return sum(math.dist(pts[k], pts[k + 1]) for k in range(len(pts) - 1))
    while i < len(tok):
        if re.match(r'[A-Za-z]', tok[i]): cmd = tok[i]; i += 1
        rel = cmd.islower(); C = cmd.upper()
        ox, oy = pos if rel else (0.0, 0.0)
        if C == 'Z':
            if cur: rings.append(cur)
            cur = []; pos = start; lastc = lastq = None; continue
        if C == 'M':
            if cur: rings.append(cur)
            pos = (ox + nxt(), oy + nxt()); start = pos; cur = [pos]; cmd = 'l' if rel else 'L'; lastc = lastq = None; continue
        if C == 'L':
            pos = (ox + nxt(), oy + nxt()); cur.append(pos); lastc = lastq = None
        elif C == 'H':
            pos = ((pos[0] if rel else 0) + nxt(), pos[1]); cur.append(pos); lastc = lastq = None
        elif C == 'V':
            pos = (pos[0], (pos[1] if rel else 0) + nxt()); cur.append(pos); lastc = lastq = None
        elif C in 'CS':
            if C == 'C': c1 = (ox + nxt(), oy + nxt())
            else: c1 = (2 * pos[0] - lastc[0], 2 * pos[1] - lastc[1]) if lastc else pos
            c2 = (ox + nxt(), oy + nxt()); p = (ox + nxt(), oy + nxt())
            n = max(2, int(seglen(pos, c1, c2, p) / step))
            cur += _bez(pos, c1, c2, p, n); lastc = c2; lastq = None; pos = p
        elif C in 'QT':
            if C == 'Q': q = (ox + nxt(), oy + nxt())
            else: q = (2 * pos[0] - lastq[0], 2 * pos[1] - lastq[1]) if lastq else pos
            p = (ox + nxt(), oy + nxt())
            c1 = (pos[0] + 2 / 3 * (q[0] - pos[0]), pos[1] + 2 / 3 * (q[1] - pos[1]))
            c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            n = max(2, int(seglen(pos, q, p) / step)); cur += _bez(pos, c1, c2, p, n); lastq = q; lastc = None; pos = p
        elif C == 'A':
            rx, ry, phi, fa, fs = nxt(), nxt(), nxt(), int(nxt()), int(nxt())
            p = (ox + nxt(), oy + nxt()); cur += _arc_points(pos, rx, ry, phi, fa, fs, p); pos = p; lastc = lastq = None
    if cur: rings.append(cur)
    return [r for r in rings if len(r) > 2]

def parse_transform(t):
    M = np.eye(3)
    for name, args in re.findall(r'(\w+)\s*\(([^)]*)\)', t or ''):
        a = [float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?', args)]
        if name == 'matrix': T = np.array([[a[0], a[2], a[4]], [a[1], a[3], a[5]], [0, 0, 1]])
        elif name == 'translate': T = np.array([[1, 0, a[0]], [0, 1, a[1] if len(a) > 1 else 0], [0, 0, 1]])
        elif name == 'scale':
            sx = a[0]; sy = a[1] if len(a) > 1 else a[0]; T = np.diag([sx, sy, 1.0])
        elif name == 'rotate':
            r = math.radians(a[0]); c, s = math.cos(r), math.sin(r)
            T = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
            if len(a) == 3:
                T = np.array([[1, 0, a[1]], [0, 1, a[2]], [0, 0, 1]]) @ T @ np.array([[1, 0, -a[1]], [0, 1, -a[2]], [0, 0, 1]])
        else: continue
        M = M @ T
    return M

def shapes_in(elem, M=np.eye(3)):
    """yield (id, element, rings) for every path/circle under elem, with transforms applied"""
    M = M @ parse_transform(elem.get('transform'))
    tag = elem.tag.split('}')[-1]
    rings = []
    if tag == 'path': rings = path_to_rings(elem.get('d', ''))
    elif tag == 'circle':
        cx, cy, r = (float(elem.get(k, 0)) for k in ('cx', 'cy', 'r'))
        rings = [[(cx + r * math.cos(t), cy + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 200, endpoint=False)]]
    elif tag == 'ellipse':
        cx, cy, rx, ry = (float(elem.get(k, 0)) for k in ('cx', 'cy', 'rx', 'ry'))
        rings = [[(cx + rx * math.cos(t), cy + ry * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 200, endpoint=False)]]
    if rings:
        out = []
        for r in rings:
            P = np.c_[np.asarray(r), np.ones(len(r))] @ M.T; out.append(P[:, :2])
        yield elem.get('id', ''), elem, out
    for ch in elem: yield from shapes_in(ch, M)

def find_layer(root, name):
    for g in root.iter(f'{{{SVG_NS}}}g'):
        if g.get('id') == name or (g.get(f'{{{INK}}}label') or '').lower().startswith(name): return g
    return None

def layer_matrix(root, target):
    """accumulated transform of the ancestors of target"""
    parent = {c: p for p in root.iter() for c in p}
    chain = []; e = target
    while e in parent: e = parent[e]; chain.append(e)
    M = np.eye(3)
    for e in reversed(chain): M = M @ parse_transform(e.get('transform'))
    return M

# ----------------------------------------------------------------- geometry
def fitcircle(P):
    A = np.c_[2 * P, np.ones(len(P))]; b = (P**2).sum(1)
    c = np.linalg.lstsq(A, b, rcond=None)[0]; cx, cy = c[:2]; r = math.sqrt(max(1e-12, c[2] + cx * cx + cy * cy))
    return cx, cy, r, float(np.abs(np.hypot(P[:, 0] - cx, P[:, 1] - cy) - r).max())

def circ_d(cx, cy, r):
    k = K * r
    return (f'M{cx + r:.2f},{cy:.2f}C{cx + r:.2f},{cy + k:.2f} {cx + k:.2f},{cy + r:.2f} {cx:.2f},{cy + r:.2f}'
            f'C{cx - k:.2f},{cy + r:.2f} {cx - r:.2f},{cy + k:.2f} {cx - r:.2f},{cy:.2f}'
            f'C{cx - r:.2f},{cy - k:.2f} {cx - k:.2f},{cy - r:.2f} {cx:.2f},{cy - r:.2f}'
            f'C{cx + k:.2f},{cy - r:.2f} {cx + r:.2f},{cy - k:.2f} {cx + r:.2f},{cy:.2f}Z')

def ring_to_d(coords, tol=0.25):
    """closed ring -> path with single lines and single arcs (cubic, <=90 deg each)"""
    P = np.asarray(coords, float)
    if np.allclose(P[0], P[-1]): P = P[:-1]
    P = np.asarray(Polygon(P).simplify(0.05).exterior.coords)[:-1]
    n = len(P)
    if n >= 8:
        cx, cy, r, dev = fitcircle(P)
        if dev < tol: return circ_d(cx, cy, r), 4
    # start at the beginning of the longest segment so we never start mid-arc
    seg = np.hypot(*np.diff(np.vstack([P, P[:1]]), axis=0).T)
    P = np.roll(P, -int(np.argmax(seg)), 0); P = np.vstack([P, P[:1]])
    out = [f'M{P[0, 0]:.2f},{P[0, 1]:.2f}']; nodes = 0; s = 0
    while s < n:
        # how far does a straight line reach?
        e_line = s + 1
        while e_line + 1 <= n:
            Q = P[s:e_line + 2]; a, b = Q[0], Q[-1]; L = np.linalg.norm(b - a)
            v = Q - a; dev = np.abs((b - a)[0] * v[:, 1] - (b - a)[1] * v[:, 0]) / L if L else 0
            if np.max(dev) > tol: break
            e_line += 1
        # how far does a circular arc reach?
        e_arc = s + 1
        while e_arc + 1 <= n:
            Q = P[s:e_arc + 2]
            if len(Q) < 3: e_arc += 1; continue
            cx, cy, r, dev = fitcircle(Q)
            mid = (Q[1:] + Q[:-1]) / 2          # chord midpoints must also lie on the arc
            mdev = np.abs(np.hypot(mid[:, 0] - cx, mid[:, 1] - cy) - r).max()
            if dev > tol or mdev > tol: break
            e_arc += 1
        if e_line >= e_arc or e_arc - s < 2:
            e = e_line; out.append(f'L{P[e, 0]:.2f},{P[e, 1]:.2f}'); nodes += 1
        else:
            e = e_arc; Q = P[s:e + 1]; cx, cy, r, _ = fitcircle(Q)
            ang = np.unwrap(np.arctan2(Q[:, 1] - cy, Q[:, 0] - cx)); tot = ang[-1] - ang[0]
            m = max(1, int(math.ceil(abs(tot) / (math.pi / 2) - 1e-6)))
            for q in range(m):
                t0 = ang[0] + tot * q / m; t1 = ang[0] + tot * (q + 1) / m; h = 4 / 3 * math.tan((t1 - t0) / 4)
                p0 = np.array([cx + r * math.cos(t0), cy + r * math.sin(t0)])
                p3 = Q[-1] if q == m - 1 else np.array([cx + r * math.cos(t1), cy + r * math.sin(t1)])
                p1 = p0 + h * r * np.array([-math.sin(t0), math.cos(t0)])
                p2 = p3 - h * r * np.array([-math.sin(t1), math.cos(t1)])
                out.append(f'C{p1[0]:.2f},{p1[1]:.2f} {p2[0]:.2f},{p2[1]:.2f} {p3[0]:.2f},{p3[1]:.2f}'); nodes += 1
        s = e
    out.append('Z')
    return ''.join(out), nodes

def geom_to_d(g):
    parts = []; nodes = 0
    for poly in getattr(g, 'geoms', [g]):
        if poly.geom_type != 'Polygon' or poly.area < 1: continue
        for ring in [poly.exterior, *poly.interiors]:
            d, k = ring_to_d(ring.coords); parts.append(d); nodes += k
    return ' '.join(parts), nodes

def buf(g, d):
    return g.buffer(d, join_style=1, quad_segs=64) if abs(d) > 1e-9 else g

def band_of(pg, half):
    """keyline band = centre line +/- half. Mitre joins, so sharp tips stay sharp
    (round joins cut the point off a banner tip); curves are many small segments,
    so they come out the same as before."""
    return pg.buffer(half, join_style=2, mitre_limit=10).difference(pg.buffer(-half, join_style=2, mitre_limit=10))

# ----------------------------------------------------------------- main
KIND = 'bordered area (centerline layer): area stencil, area mask, border stencil'

def applies(root):
    """True if this source SVG is a bordered area: it has a centerline layer with a path in it"""
    cl = find_layer(root, 'centerline')
    return cl is not None and any(e.get('d') for e in cl.iter(f'{{{SVG_NS}}}path'))

def build_parser():
    ap = argparse.ArgumentParser(description='Make area stencil, area mask and border stencil from a centerline SVG.')
    ap.add_argument('svg')
    ap.add_argument('--width', type=float)
    ap.add_argument('--overlap', type=float, default=0.005)
    ap.add_argument('--area-grow', type=float, default=0.0)
    ap.add_argument('--mask-grow', type=float, default=0.0)
    ap.add_argument('--window-margin', type=float, default=0.02)
    ap.add_argument('--min-window', type=float, default=0.25)
    ap.add_argument('--windows', default=None)
    ap.add_argument('--only', choices=['area', 'mask', 'border'])
    ap.add_argument('--outdir')
    return ap

def main(argv=None):
    a = build_parser().parse_args(argv)

    ET.register_namespace('', SVG_NS); ET.register_namespace('inkscape', INK)
    tree = ET.parse(a.svg); root = tree.getroot()
    cl = find_layer(root, 'centerline')
    if cl is None: sys.exit('No layer with id "centerline" found in ' + a.svg)
    width = a.width
    if width is None:
        m = re.match(r'([\d.]+)\s*(in)?', cl.get('data-width', '') or '')
        width = float(m.group(1)) if m else 0.06
    M0 = layer_matrix(root, cl)
    areas = []; noborder = []; lines = []        # lines: (polygon, keyline width in inches)
    for _id, _e, rings in shapes_in(cl, M0):
        for r in rings:
            # a closed path whose id starts with "noborder" is not an area: no border is
            # painted inside it (e.g. where a saucer ring sits on top of the keyline)
            if _id.lower().startswith('noborder'): noborder.append(Polygon(r).buffer(0)); continue
            pg = Polygon(r).buffer(0); areas.append(pg)
            # a path may carry its own data-width (e.g. a card outline inside an arrow)
            pm = re.match(r'([\d.]+)\s*(in)?', _e.get('data-width', '') or '')
            lines.append((pg, float(pm.group(1)) if (pm and a.width is None) else width))
    if not areas: sys.exit('The centerline layer has no closed paths.')
    area = unary_union(areas)

    # registration marks
    marks = []                                   # (id, kind, polygon, circle-or-None)
    hl = find_layer(root, 'holes')
    if hl is not None:
        Mh = layer_matrix(root, hl)
        for _id, e, rings in shapes_in(hl, Mh):
            for r in rings:
                P = np.asarray(r); cx, cy, rr, dev = fitcircle(P)
                circ = (cx, cy, rr) if dev < max(1.0, 0.03 * rr) else None
                marks.append((_id, Polygon(P).buffer(0), circ))

    # alignment windows
    if a.windows == 'none': wanted = []
    elif a.windows:
        ids = [x.strip() for x in a.windows.split(',')]
        wanted = [m for m in marks if m[0] in ids and m[2]]
    else:
        wanted = [m for m in marks if m[2] and not m[0].lower().startswith('post') and 2 * m[2][2] >= a.min_window * U and area.contains(Point(m[2][:2]))]
    windows = [(c[0], c[1], c[2] - a.window_margin * U) for _, _, c in wanted if c[2] - a.window_margin * U > 3]

    def with_windows(shape):
        """cut outline + windows; a window that crosses the edge becomes part of the outline"""
        inner = []
        for cx, cy, r in windows:
            Wn = Point(cx, cy).buffer(r, quad_segs=64)
            if shape.buffer(-0.5).contains(Wn): inner.append(circ_d(cx, cy, r))
            elif shape.intersects(Wn): shape = shape.difference(Wn)
        d, k = geom_to_d(shape)
        return ' '.join([d] + inner), k + 4 * len(inner), shape

    stem = os.path.splitext(os.path.basename(a.svg))[0]
    outdir = a.outdir or os.path.join(os.getcwd(), '_generated')
    os.makedirs(outdir, exist_ok=True)
    vb = root.get('viewBox'); wid = root.get('width'); hei = root.get('height')
    # reference copy of the registration marks for every output
    # (built from a copy - the source file is never changed). Each loose hole path is
    # wrapped in its own group "hole N", like the posts, so Silhouette Studio lists it
    # as an object that can be selected and shown/hidden on its own.
    ref = ''
    if hl is not None:
        import copy
        hc = copy.deepcopy(hl)
        for i, ch in enumerate(list(hc)):
            if ch.tag.split('}')[-1] in ('path', 'circle', 'ellipse'):
                hid = ch.get('id') or f'hole{i + 1}'
                lab = ch.get(f'{{{INK}}}label') or re.sub(r'^([A-Za-z]+)(\d+)$', r'\1 \2', hid)
                g = ET.Element(f'{{{SVG_NS}}}g', {'id': hid, f'{{{INK}}}label': lab})
                g.tail = ch.tail; ch.tail = None
                ch.set('id', hid + '-outline'); ch.attrib.pop(f'{{{INK}}}label', None)
                hc.remove(ch); hc.insert(i, g); g.append(ch)
        ref = ET.tostring(hc, encoding='unicode')
    ref = re.sub(r'<(\w+:)?g ', '<g ', ref, count=1)
    ref = re.sub(r'\sid="holes"', ' id="holes-ref"', ref, count=1)
    ref = re.sub(r'label="[^"]*"', 'label="holes (reference - no cut)"', ref, count=1)

    def write(kind, d, nodes, note, colour):
        fn = os.path.join(outdir, f'{stem} - {kind}.svg')
        svg = (f'<svg xmlns="{SVG_NS}" xmlns:inkscape="{INK}" width="{wid}" height="{hei}" viewBox="{vb}">\n'
               f'<!-- {stem} - {kind}. Generated by make_stencils.py. 300 units = 1 in. {note} '
               f'Cut layer "cut" only; "holes (reference - no cut)" is for lining up. -->\n'
               f'<g inkscape:groupmode="layer" id="cut" inkscape:label="cut"><path id="{kind.replace(" ", "-")}" '
               f'fill="{colour}" fill-opacity="0.35" fill-rule="evenodd" stroke="#000" stroke-width="1" d="{d}"/></g>\n'
               f'{ref}\n</svg>\n')
        open(fn, 'w').write(svg)
        minx, miny, maxx, maxy = area.bounds
        print(f'  {os.path.basename(fn)}: {nodes} nodes')
        return fn

    ws = sorted({round(w, 4) for _, w in lines}) or [width]
    print(f'{a.svg}: keyline {", ".join(str(w) for w in ws)}in, {len(windows)} alignment window(s)')
    if a.only in (None, 'area'):
        d, k, _ = with_windows(buf(area, a.area_grow * U))
        write('area stencil', d, k, f'Area = centre line grown {a.area_grow}in. The piece that drops out is the area mask.', '#f6e39c')
    if a.only in (None, 'mask'):
        d, k, _ = with_windows(buf(area, a.mask_grow * U))
        write('area mask', d, k, f'Mask = centre line grown {a.mask_grow}in.', '#f6e39c')
    if a.only in (None, 'border'):
        half = (width / 2 + a.overlap) * U
        # every centre line gets its own band (nested lines, e.g. a card inside an
        # arrow or a ring inside a banner, each keep their keyline at their own width)
        band = unary_union([band_of(pg, (w / 2 + a.overlap) * U) for pg, w in lines])
        if noborder: band = band.difference(unary_union(noborder))
        island = area.difference(band)
        d, k = geom_to_d(band)
        inner = []
        for cx, cy, r in windows:
            Wn = Point(cx, cy).buffer(r, quad_segs=64)
            if island.buffer(-0.5).contains(Wn): inner.append(circ_d(cx, cy, r))
        write('border stencil', ' '.join([d] + inner), k + 4 * len(inner),
              f'Band = centre line +/- {width / 2 + a.overlap:.4f}in ({width}in line + {a.overlap}in overlap each side).', '#1a5470')
    minx, miny, maxx, maxy = area.bounds
    print(f'  area size {(maxx - minx) / U:.2f} x {(maxy - miny) / U:.2f} in')

if __name__ == '__main__':
    main()
