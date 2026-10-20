#!/usr/bin/env python3
"""Green ring stencils for the two green rings round the ADVANCE CARD rollover (LC).

Plain Python 3, no packages.  Run from the Lady Luck folder:
    python3 scripts/make_green_rings.py
Reads the green ring circles (measured, same as playfield background.svg) and the
playfield holes from "Lady Luck playfield.svg"; writes
    stencils/LC green rings stencil pieces.svg   all pieces at their board position
    _generated/LC green rings - sheet N.svg       the pieces laid out on 12 x 12in sheets

The stencil is FILM, not openings: each piece is the clear film that stays on the
board; the green ring is the gap between the pieces (weed it out - the weeded ring
pieces double as green masks later).  Pieces butt together along straight radial
seams and along one circle (R_MID) between the rings, so all 5 can be stuck down
at once.  The outer ring ends where it meets the lower slings' blue border (centre
line of the LL / LR slingshot.svg border), not at the wood lobes: the green is not
seen inside the cream slings.  Pieces 1, 3 and 4 fall apart into separate strips /
an island once the ring is weeded: put transfer tape over each piece before lifting
it so the ring width stays exact.  Black = cut, red = pen (Tool 2) registration = playfield holes under the film.
300 units = 1in.  Every circle 4 cubics, every arc 1 cubic per <= 90 deg.
"""
import math, os, re, sys

# ---- settings (inches) ----------------------------------------------------
FILM = 1.0          # film beyond the outer ring's outer edge and past the ring ends
R_MID_IN = 5.5      # seam circle between the rings (inner sheet = 11in disc)
SHEET = 12.0        # stencil sheet size
MARGIN = 0.25
U = 300.0

# ---- green ring geometry (board units, y down from the top edge) -----------
# from playfield background.svg (fits to the aligned whole-board photo)
O_IN = (2770.62, 8396.88, 1854.48)    # outer ring, inner edge
O_OUT = (2769.69, 8405.46, 1972.50)   # outer ring, outer edge
I_OUT = (2768.55, 8388.27, 1227.24)   # inner ring, outer edge
I_IN = (2771.10, 8387.64, 1129.83)    # inner ring, inner edge
# outer ring ends: the green stops on the centre line of each lower sling's blue
# border (LL / LR slingshot.svg centerline layer, moved to board units).  The ring's
# inner edge meets the sling's long straight inner edge; its outer edge meets the
# sling's rounded top.  So each end = straight piece + part of the top-cap cubic.
# (straight edge: from point A up to its top point Q; cap cubic starts at Q)
L_SLING = dict(A=(1746.12, 10111.83), Q=(834.91, 8624.44),
               cap=((834.91, 8624.44), (813.04, 8588.74), (772.05, 8569.44), (730.59, 8575.34)))
R_SLING = dict(A=(3788.63, 10122.72), Q=(4717.40, 8646.24),
               cap=((4717.40, 8646.24), (4739.70, 8610.80), (4780.92, 8591.99), (4822.30, 8598.38)))

def bez(c, t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = c
    u = 1 - t
    return (u**3*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3, u**3*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3)

def bez_head(c, t):
    """the part of cubic c from 0 to t (de Casteljau)"""
    p0, p1, p2, p3 = c
    lerp = lambda a, b: (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    q0, q1, q2 = lerp(p0, p1), lerp(p1, p2), lerp(p2, p3)
    r0, r1 = lerp(q0, q1), lerp(q1, q2)
    return (p0, q0, r0, lerp(r0, r1))

def crossing(f, lo, hi):
    """bisection: f changes sign between lo and hi"""
    flo = f(lo)
    for _ in range(60):
        mid = (lo + hi) / 2
        if (f(mid) > 0) == (flo > 0):
            lo, flo = mid, f(mid)
        else:
            hi = mid
    return (lo + hi) / 2

def sling_end(sl):
    A, Q, cap = sl['A'], sl['Q'], sl['cap']
    on_line = lambda t: (A[0] + (Q[0] - A[0]) * t, A[1] + (Q[1] - A[1]) * t)
    r_in = lambda p: math.hypot(p[0] - O_IN[0], p[1] - O_IN[1]) - O_IN[2]
    r_out = lambda p: math.hypot(p[0] - O_OUT[0], p[1] - O_OUT[1]) - O_OUT[2]
    # inner edge: last crossing along the straight edge before Q (scan from Q down)
    ts = [k / 400 for k in range(401)]
    t_in = None
    for k in range(400, 0, -1):
        if (r_in(on_line(ts[k])) > 0) != (r_in(on_line(ts[k - 1])) > 0):
            t_in = crossing(lambda t: r_in(on_line(t)), ts[k - 1], ts[k]); break
    t_out = crossing(lambda t: r_out(bez(cap, t)), 0.0, 1.0)
    head = bez_head(cap, t_out)
    e_in, e_out = on_line(t_in), head[3]
    fwd = [('L', Q), ('C', head[1], head[2], head[3])]          # e_in -> e_out
    back = [('C', head[2], head[1], Q), ('L', e_in)]            # e_out -> e_in
    return e_in, e_out, fwd, back

L_END_IN, L_END_OUT, L_FWD, L_BACK = sling_end(L_SLING)
R_END_IN, R_END_OUT, R_FWD, R_BACK = sling_end(R_SLING)
C = (O_IN[0], O_IN[1])                # common centre for seams and the film edges
R_MID = R_MID_IN * U
R_OUT = O_OUT[2] + FILM * U + 8.6     # +8.6 = the outer edge's centre offset

def ang(p, c=C):
    return math.degrees(math.atan2(p[1] - c[1], p[0] - c[0]))

def P(r, a, c=C):
    t = math.radians(a)
    return (c[0] + r * math.cos(t), c[1] + r * math.sin(t))

def ray_circle(a, circ):
    """point where the ray from C at angle a meets circle circ (cx, cy, r)"""
    ux, uy = math.cos(math.radians(a)), math.sin(math.radians(a))
    dx, dy = C[0] - circ[0], C[1] - circ[1]
    b = dx * ux + dy * uy
    cc = dx * dx + dy * dy - circ[2] ** 2
    t = -b + math.sqrt(b * b - cc)
    return (C[0] + t * ux, C[1] + t * uy)

def arc(circ, p0, p1, cw):
    """cubic(s) along circle circ from p0 to p1; cw = increasing screen angle"""
    cx, cy, r = circ
    a0, a1 = ang(p0, (cx, cy)), ang(p1, (cx, cy))
    d = (a1 - a0) % 360 if cw else -((a0 - a1) % 360)
    n = max(1, math.ceil(abs(d) / 90 - 1e-9))
    out = []
    for i in range(n):
        s, e = math.radians(a0 + d * i / n), math.radians(a0 + d * (i + 1) / n)
        k = 4 / 3 * math.tan((e - s) / 4) * r
        q0 = (cx + r * math.cos(s), cy + r * math.sin(s))
        q3 = (cx + r * math.cos(e), cy + r * math.sin(e))
        q1 = (q0[0] - k * math.sin(s), q0[1] + k * math.cos(s))
        q2 = (q3[0] + k * math.sin(e), q3[1] - k * math.cos(e))
        out.append(('C', q1, q2, q3 if i < n - 1 else p1))
    return out

def short_arc(circ, p0, p1):
    """the shorter way round circle circ from p0 to p1"""
    c = (circ[0], circ[1])
    return arc(circ, p0, p1, (ang(p1, c) - ang(p0, c)) % 360 < 180)

def circle(circ):
    cx, cy, r = circ
    p = (cx + r, cy)
    return [('M', p)] + arc(circ, p, (cx - r, cy), True) + arc(circ, (cx - r, cy), p, True) + [('Z',)]

def closed(start, *segs):
    path = [('M', start)]
    for s in segs:
        path += s
    return path + [('Z',)]

def L(p):
    return [('L', p)]

# ---- piece angles ------------------------------------------------------------
a_left_end = min(ang(L_END_IN), ang(L_END_OUT))           # lower left
a_right_end = max(ang(R_END_IN), ang(R_END_OUT)) + 360    # lower right, past the top
ext = math.degrees(FILM * U / O_OUT[2])
A0, A1 = a_left_end - ext, a_right_end + ext
step = (A1 - A0) / 4
SEAMS = [A0 + step * i for i in range(5)]   # A0, s1, s2 (top), s3, A1

def outer_end_piece(left):
    if left:
        ae, as_ = SEAMS[0], SEAMS[1]
        e_in, e_out, end_fwd = L_END_IN, L_END_OUT, L_FWD
    else:
        ae, as_ = SEAMS[4], SEAMS[3]
        e_in, e_out, end_fwd = R_END_IN, R_END_OUT, R_FWD
    cw = left    # direction from the free end towards the seam, along the ring
    q_in, q_out = ray_circle(as_, O_IN), ray_circle(as_, O_OUT)
    # film outline: outer film edge (seam -> free end), end line, seam circle back,
    # seam line, ring inner edge to the ring end, along the sling line, ring outer edge to the seam
    return closed(P(R_OUT, as_),
                  arc((C[0], C[1], R_OUT), P(R_OUT, as_), P(R_OUT, ae), not cw),
                  L(P(R_MID, ae)),
                  arc((C[0], C[1], R_MID), P(R_MID, ae), P(R_MID, as_), cw),
                  L(q_in),
                  arc(O_IN, q_in, e_in, not cw),
                  end_fwd,
                  arc(O_OUT, e_out, q_out, cw),
                  L(P(R_OUT, as_)))

def outer_mid_piece(a0, a1):
    o0, o1 = ray_circle(a0, O_OUT), ray_circle(a1, O_OUT)
    i0, i1 = ray_circle(a0, O_IN), ray_circle(a1, O_IN)
    outer_strip = closed(o0, arc(O_OUT, o0, o1, True), L(P(R_OUT, a1)),
                         arc((C[0], C[1], R_OUT), P(R_OUT, a1), P(R_OUT, a0), False), L(o0))
    inner_strip = closed(P(R_MID, a0), arc((C[0], C[1], R_MID), P(R_MID, a0), P(R_MID, a1), True),
                         L(i1), arc(O_IN, i1, i0, False), L(P(R_MID, a0)))
    return [outer_strip, inner_strip]

# ---- holes ------------------------------------------------------------------
def read_holes(master):
    s = open(master, encoding='utf-8').read()
    i = s.find('id="holes"')
    s = s[i:]
    j = s.find('inkscape:groupmode="layer"', 40)
    s = s[:j] if j > 0 else s
    holes = {}
    for m in re.finditer(r'<path id="([^"]+)"[^>]*d="([^"]+)"', s):
        nums = [float(x) for x in re.findall(r'-?\d+\.?\d*', m.group(2))]
        xs, ys = nums[0::2], nums[1::2]
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        r = (max(xs) - min(xs)) / 2
        name = m.group(1)
        key = re.sub(r'-(outline|screw)$', '', name)
        holes.setdefault(key, []).append((name, cx, cy, r))
    return holes

def dist(p, c):
    return math.hypot(p[0] - c[0], p[1] - c[1])

def in_green(p):
    a = ang(p) % 360
    in_span = a >= a_left_end % 360 - 0.5 or a <= a_right_end % 360 + 0.5
    if in_span and dist(p, O_IN) > O_IN[2] and dist(p, O_OUT) < O_OUT[2]:
        return True
    return dist(p, I_OUT) < I_OUT[2] and dist(p, I_IN) > I_IN[2]

def piece_of(p):
    """which piece's film covers point p (None = not on film)"""
    if in_green(p):
        return None
    r = dist(p, C)
    if r <= R_MID:
        return 1 if (dist(p, I_IN) <= I_IN[2] or dist(p, I_OUT) >= I_OUT[2]) else None
    if r > R_OUT:
        return None
    a = ang(p)
    while a < SEAMS[0]:
        a += 360
    for k in range(4):
        if SEAMS[k] <= a <= SEAMS[k + 1]:
            return k + 2
    return None

def hole_pieces(holes):
    out = {}
    for key, parts in holes.items():
        big = max(parts, key=lambda t: t[3])
        _, cx, cy, r = big
        owners = set(piece_of((cx + r * math.cos(t / 8 * math.pi), cy + r * math.sin(t / 8 * math.pi)))
                     for t in range(16))
        owners.add(piece_of((cx, cy)))
        if len(owners) == 1 and None not in owners:
            out.setdefault(owners.pop(), []).append((key, parts))
    return out

def hole_path(cx, cy, r):
    return circle((cx, cy, r))

# ---- output -------------------------------------------------------------------
def fmt(path, T=lambda p: p):
    s = []
    for seg in path:
        if seg[0] == 'M':
            s.append('M%.2f,%.2f' % T(seg[1]))
        elif seg[0] == 'L':
            s.append('L%.2f,%.2f' % T(seg[1]))
        elif seg[0] == 'C':
            s.append('C%.2f,%.2f %.2f,%.2f %.2f,%.2f' % (T(seg[1]) + T(seg[2]) + T(seg[3])))
        else:
            s.append('Z')
    return ' '.join(s)

def nodes(path):
    return sum(1 for s in path if s[0] in 'LC')

def pts(path):
    for s in path:
        for q in s[1:]:
            yield q

def piece_svg(pid, label, cuts, pen, T, w=0):
    g = ['<g id="piece%d" inkscape:label="%s">' % (pid, label)]
    for n, (lab, p) in enumerate(cuts):
        g.append('<path id="piece%d-cut%d" inkscape:label="%s" fill="none" stroke="#000" stroke-width="1" d="%s"/>'
                 % (pid, n + 1, lab, fmt(p, T)))
    for key, parts in pen:
        short = key.replace('-', ' ').replace('_', ' ')
        if len(parts) > 1:
            g.append('<g inkscape:label="%s">' % short)
        for name, cx, cy, r in parts:
            g.append('<path id="piece%d-%s" inkscape:label="%s" fill="none" stroke="#c00" stroke-width="1" d="%s"/>'
                     % (pid, name, name.split('_')[-1], fmt(hole_path(cx, cy, r), T)))
        if len(parts) > 1:
            g.append('</g>')
    g.append('</g>')
    return '\n'.join(g)

HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="%.4fin" height="%.4fin" '
        'viewBox="%.2f %.2f %.2f %.2f">\n')

def main():
    root = os.getcwd()
    master = os.path.join(root, 'Lady Luck playfield.svg')
    holes = hole_pieces(read_holes(master))

    pieces = {
        1: ('1 inner ring', [('1a centre disc (island)', circle(I_IN)),
                             ('1b band', circle((C[0], C[1], R_MID)) [:-1] + circle(I_OUT)[0:0] or None)]),
    }
    # piece 1b = band between the inner ring's outer edge and the seam circle (two subpaths)
    band = circle((C[0], C[1], R_MID))
    inner = circle(I_OUT)
    # reverse the inner circle so the band is a proper ring (evenodd anyway)
    pieces[1] = ('1 inner ring', [('1a centre disc (island)', circle(I_IN)), ('1b band', band + inner)])
    pieces[2] = ('2 outer ring - lower left', [('2 film', outer_end_piece(True))])
    mid3 = outer_mid_piece(SEAMS[1], SEAMS[2])
    mid4 = outer_mid_piece(SEAMS[2], SEAMS[3])
    pieces[3] = ('3 outer ring - upper left', [('3a outer strip', mid3[0]), ('3b inner strip', mid3[1])])
    pieces[4] = ('4 outer ring - upper right', [('4a outer strip', mid4[0]), ('4b inner strip', mid4[1])])
    pieces[5] = ('5 outer ring - lower right', [('5 film', outer_end_piece(False))])
    mids = {1: None, 2: (SEAMS[0] + SEAMS[1]) / 2, 3: (SEAMS[1] + SEAMS[2]) / 2,
            4: (SEAMS[2] + SEAMS[3]) / 2, 5: (SEAMS[3] + SEAMS[4]) / 2}

    report = []
    for pid, (lab, cuts) in pieces.items():
        n = [nodes(p) for _, p in cuts]
        report.append('piece %s: cut nodes %s, holes %d' % (lab, n, len(holes.get(pid, []))))

    # green reference (clean): outer ring + inner ring
    g_outer = closed(L_END_IN, arc(O_IN, L_END_IN, R_END_IN, True),
                     R_FWD,
                     arc(O_OUT, R_END_OUT, L_END_OUT, False),
                     L_BACK)
    g_inner = circle(I_OUT) + circle(I_IN)

    # ---- assembly file (board position) ----
    allp = [q for _, cuts in pieces.values() for _, p in cuts for q in pts(p)]
    x0 = math.floor(min(q[0] for q in allp) / 30) * 30 - 30
    y0 = math.floor(min(q[1] for q in allp) / 30) * 30 - 30
    x1 = math.ceil(max(q[0] for q in allp) / 30) * 30 + 30
    y1 = math.ceil(max(q[1] for q in allp) / 30) * 30 + 30
    T = lambda p: (p[0] - x0, p[1] - y0)
    out = [HEAD % ((x1 - x0) / U, (y1 - y0) / U, 0, 0, x1 - x0, y1 - y0)]
    out.append('<!-- LC green rings - stencil pieces at board position. Generated by scripts/make_green_rings.py. '
               '300 units = 1in. This file\'s top-left corner = board X %.4f, Y %.4f in (origin lower-left). '
               'Pieces are FILM: cut on the black lines, weed out the green ring; the 5 pieces butt along the '
               'radial seams and the seam circle (R %.3fin) so they can all go down at once. Red = pen (Tool 2): '
               'playfield holes under the film, for lining up. Green layer = reference only. '
               'Film reaches %.2fin outside the outer ring - mask the rest of the board with paper. '
               'The outer ring ends on the lower slings\' blue border centre line. Lift pieces with transfer tape; '
               'tape over the butt seams. -->\n'
               % (x0 / U, 42 - y0 / U, R_MID / U, FILM))
    out.append('<g inkscape:groupmode="layer" id="green" inkscape:label="green ring (reference - no cut)" '
               'sodipodi:insensitive="true" style="opacity:0.35">'.replace(' sodipodi:insensitive="true"', ''))
    out.append('<path id="green-outer" fill="#16a050" stroke="none" d="%s"/>' % fmt(g_outer, T))
    out.append('<path id="green-inner" fill="#16a050" fill-rule="evenodd" stroke="none" d="%s"/>' % fmt(g_inner, T))
    out.append('</g>')
    out.append('<g inkscape:groupmode="layer" id="pieces" inkscape:label="stencil pieces (black cut, red pen)">')
    for pid, (lab, cuts) in pieces.items():
        out.append(piece_svg(pid, lab, cuts, holes.get(pid, []), T))
    out.append('</g>\n</svg>\n')
    os.makedirs(os.path.join(root, 'stencils'), exist_ok=True)
    fn = os.path.join(root, 'stencils', 'LC green rings stencil pieces.svg')
    open(fn, 'w', encoding='utf-8').write('\n'.join(out))
    report.append('wrote ' + fn + '  (%.2f x %.2f in)' % ((x1 - x0) / U, (y1 - y0) / U))

    # ---- sheets ----
    S = SHEET * U
    def rot(a):
        t = math.radians(a)
        c, s = math.cos(t), math.sin(t)
        return lambda p: (C[0] + (p[0] - C[0]) * c - (p[1] - C[1]) * s,
                          C[1] + (p[0] - C[0]) * s + (p[1] - C[1]) * c)
    def bbox(ps):
        xs, ys = [q[0] for q in ps], [q[1] for q in ps]
        return min(xs), min(ys), max(xs), max(ys)
    sheets = [[1], [2, 3], [4, 5]]
    os.makedirs(os.path.join(root, '_generated'), exist_ok=True)
    for sn, plist in enumerate(sheets, 1):
        body = []
        ycur = MARGIN * U
        for pid in plist:
            lab, cuts = pieces[pid]
            R = rot(0) if mids[pid] is None else rot(-90 - mids[pid])
            bx = bbox([R(q) for _, p in cuts for q in pts(p)])
            w, h = bx[2] - bx[0], bx[3] - bx[1]
            if mids[pid] is None:
                dx, dy = (S - w) / 2 - bx[0], (S - h) / 2 - bx[1]
            else:
                dx, dy = (S - w) / 2 - bx[0], ycur - bx[1]
                ycur += h + 0.25 * U
            T = (lambda R, dx, dy: (lambda p: (R(p)[0] + dx, R(p)[1] + dy)))(R, dx, dy)
            body.append(piece_svg(pid, lab, cuts, holes.get(pid, []), T))
            report.append('sheet %d: piece %d  %.2f x %.2f in' % (sn, pid, w / U, h / U))
        if ycur - 0.25 * U > S - MARGIN * U:
            report.append('  WARNING: sheet %d is over %gin tall' % (sn, SHEET))
        name = 'LC green rings - sheet %d (piece%s %s).svg' % (sn, 's' if len(plist) > 1 else '',
                                                              ' + '.join(str(p) for p in plist))
        out = [HEAD % (SHEET, SHEET, 0, 0, S, S)]
        out.append('<!-- %s. Generated by scripts/make_green_rings.py. %g x %gin sheet, 300 units = 1in. '
                   'Black = cut (film pieces; weed out the green ring between them), red = pen (Tool 2) '
                   'registration (playfield holes under the film). Each piece is a group - move/rotate it freely. '
                   'Pieces 1, 3, 4 split into strips/islands when weeded: lift each with transfer tape. '
                   'See "stencils/LC green rings stencil pieces.svg" for where the pieces go. -->\n'
                   % (name[:-4], SHEET, SHEET))
        out.append('<g inkscape:groupmode="layer" id="pieces" inkscape:label="pieces (black cut, red pen)">')
        out += body
        out.append('</g>\n</svg>\n')
        fn = os.path.join(root, '_generated', name)
        open(fn, 'w', encoding='utf-8').write('\n'.join(out))
        report.append('wrote ' + fn)
    print('\n'.join(report))
    print('seams (deg, screen angle from C): ' + ', '.join('%.2f' % (a % 360) for a in SEAMS))
    print('R_MID %.1f  R_OUT %.1f units' % (R_MID, R_OUT))
    for pid in sorted(holes):
        print('piece', pid, 'holes:', ', '.join(k.split('_')[-1] + '(' + k.split('_')[0] + ')' for k, _ in holes[pid]))

if __name__ == '__main__':
    main()
