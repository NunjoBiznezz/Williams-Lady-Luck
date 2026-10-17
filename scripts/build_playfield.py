#!/usr/bin/env python3
"""
build_playfield.py - assemble the whole Lady Luck playfield from the piece SVGs
==============================================================================

Reads  "playfield placements.csv"  (in the Lady Luck folder) and writes
       "Lady Luck playfield.svg"   - the whole board at true scale (300 units/in).

The piece files stay the source of truth. Change a piece, then rerun this script:

    python3 scripts/build_playfield.py

No extra packages needed (plain Python 3).

placements.csv columns
----------------------
  file            piece SVG in the Lady Luck folder
  origin_x_in     X of the piece's top-left corner (its 0,0) on the board, inches
  origin_y_in     Y of that corner, inches (board coordinates: origin = lower-left
                  corner of the wood, Y up toward the arch)
  rotation_deg    rotation of the piece about that corner, degrees, clockwise as
                  seen from above (small: the source photos were slightly tilted)
  include         yes / no
  (other columns are notes and are ignored)

Output layers (bottom to top)
-----------------------------
  photo (underlay)        straightened photo, linked (images/playfield aligned 150ppi.jpg)
  grid (reference)        board outline, 3x3 grid, artwork centre line X 9.20
  background <colour>     the background file's colours (rays, rings), below all pieces
  cream (preview - no cut) the base coat where the pieces leave it showing, from
                          "playfield cream preview.svg" (locked; for looking only)
  yellow, green, teal, blue, red, black   one layer per paint colour; each piece is a
                          group named after its file
  inserts (preview - no cut)  insert / rollover plastics, from the cream preview file
  holes (registration)    every piece's holes/posts, one group per piece
  centerlines (reference) centre lines of the pieces that have them (hidden)
  controls (reference)    control points from "playfield controls.csv" (+ the hole list if
                          "Lady Luck hole list.csv" is in the folder)

Pieces are copied in as plain paths with their coordinates moved/rotated into place
(no clones, no transforms), so the file opens cleanly in Inkscape and Silhouette.
Node counts are unchanged: lines stay lines, curves stay curves, arcs stay arcs.
"""
import csv, math, os, re, sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.dirname(HERE)
PLACEMENTS = os.path.join(FOLDER, "playfield placements.csv")
OUT = os.path.join(FOLDER, "Lady Luck playfield.svg")
HOLE_LIST = os.path.join(FOLDER, "Lady Luck hole list.csv")
CONTROLS_CSV = os.path.join(FOLDER, "playfield controls.csv")
PIECE_DIRS = ["", "stencils"]   # where pieces are looked for, in order (main folder, then stencils/)

def find_piece(fn):
    """path of a piece named in placements.csv: main folder first, then stencils/"""
    for d in PIECE_DIRS:
        p = os.path.join(FOLDER, d, fn)
        if os.path.exists(p): return p
    return os.path.join(FOLDER, fn)
UNDERLAY = "images/playfield aligned 150ppi.jpg"

U = 300.0                     # units per inch
BOARD_W, BOARD_H = 20.3125, 42.0
SVG = "http://www.w3.org/2000/svg"
INK = "http://www.inkscape.org/namespaces/inkscape"
SOD = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
XL = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG); ET.register_namespace("inkscape", INK)
ET.register_namespace("sodipodi", SOD); ET.register_namespace("xlink", XL)

COLOUR_ORDER = ["yellow", "green", "teal", "blue", "red", "black"]

# fallback control points if "playfield controls.csv" is missing (board inches)
CONTROLS = [
    ("UC bumper", 9.1875, 32.9375), ("CL red bumper", 4.8125, 26.9375),
    ("CC bumper", 9.25, 25.9375), ("CR red bumper", 13.625, 26.9375),
    ("left saucer", 1.34375, 21.25), ("right saucer", 17.0, 21.25),
    ("left advance rollover", 3.125, 23.3125), ("right advance rollover", 15.375, 23.3125),
    ("hex rollover", 9.21875, 13.9375), ("top rollover", 9.1875, 38.125),
    ("SPSA", 9.1875, 8.0), ("left outlane slot", 1.1875, 11.0), ("right outlane slot", 17.15625, 11.0),
    ("LL corner", 0.15625, 3.5625), ("LR corner", 20.125, 5.0625), ("UL corner", 0.25, 40.8125),
    ("LL-W2", 6.625, 3.5), ("LR-W2", 15.09375, 0.53125), ("UL-W2", 0.3125, 31.8125), ("UR-W9", 18.8125, 36.53125),
]

# ---------------------------------------------------------------- path transform
TOK = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
NARGS = dict(M=2, L=2, H=1, V=1, C=6, S=4, Q=4, T=2, A=7, Z=0)

def fmt(v):
    s = "%.2f" % v
    return "0.00" if s == "-0.00" else s

def transform_d(d, ox, oy, deg):
    """Move/rotate a path: p' = R(deg) p + (ox, oy). Output absolute commands."""
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    def P(x, y): return (c * x - s * y + ox, s * x + c * y + oy)
    toks = TOK.findall(d); i = 0; out = []
    cx = cy = sx = sy = 0.0; cmd = None
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t; i += 1
            if cmd in "Zz":
                out.append("Z"); cx, cy = sx, sy; continue
        n = NARGS[cmd.upper()]
        v = [float(x) for x in toks[i:i + n]]; i += n
        rel = cmd.islower(); C = cmd.upper()
        if C == "M":
            x, y = (cx + v[0], cy + v[1]) if rel else (v[0], v[1])
            out.append("M%s,%s" % tuple(map(fmt, P(x, y)))); cx, cy = sx, sy = x, y
            cmd = "l" if rel else "L"; continue
        if C == "L" or C == "T":
            x, y = (cx + v[0], cy + v[1]) if rel else (v[0], v[1])
            out.append("%s%s,%s" % ((C,) + tuple(map(fmt, P(x, y))))); cx, cy = x, y
        elif C == "H":
            x = cx + v[0] if rel else v[0]
            out.append("L%s,%s" % tuple(map(fmt, P(x, cy)))); cx = x
        elif C == "V":
            y = cy + v[0] if rel else v[0]
            out.append("L%s,%s" % tuple(map(fmt, P(cx, y)))); cy = y
        elif C in "CSQ":
            pts = [(v[k] + (cx if rel else 0), v[k + 1] + (cy if rel else 0)) for k in range(0, n, 2)]
            out.append(C + " ".join("%s,%s" % tuple(map(fmt, P(*p))) for p in pts)); cx, cy = pts[-1]
        elif C == "A":
            rx, ry, rot, laf, sf, x, y = v
            if rel: x, y = cx + x, cy + y
            X, Y = P(x, y)
            out.append("A%s,%s %s %d,%d %s,%s" % (fmt(rx), fmt(ry), fmt(rot + deg), int(laf), int(sf), fmt(X), fmt(Y)))
            cx, cy = x, y
    return "".join(out)

# ---------------------------------------------------------------- piece reading
def label(e): return e.get("{%s}label" % INK) or e.get("id") or ""
def is_layer(e): return e.tag == "{%s}g" % SVG and e.get("{%s}groupmode" % INK) == "layer"

def layer_kind(lab):
    l = lab.lower()
    if "hole" in l: return "holes"
    if "centerline" in l or "centre" in l: return "centerlines"
    if l.startswith("cream"): return "cream"
    if l.startswith("inserts"): return "inserts"
    for c in COLOUR_ORDER:
        if l.startswith(c): return c
    return None

def copy_moved(e, ox, oy, deg, prefix):
    """Deep-copy an element, transforming every path; ids get a prefix."""
    n = ET.Element(e.tag, dict(e.attrib))
    if n.get("id"): n.set("id", prefix + n.get("id"))
    if n.tag == "{%s}path" % SVG:
        n.set("d", transform_d(n.get("d"), ox, oy, deg))
    for k in e: n.append(copy_moved(k, ox, oy, deg, prefix))
    return n

def read_piece(path):
    root = ET.parse(path).getroot()
    layers = {}
    for lay in [e for e in root.iter() if is_layer(e)]:
        k = layer_kind(label(lay))
        if k: layers.setdefault(k, []).append(lay)
    return layers

# ---------------------------------------------------------------- build
def layer(parent, lid, lab, **kw):
    g = ET.SubElement(parent, "{%s}g" % SVG, {"id": lid, "{%s}groupmode" % INK: "layer", "{%s}label" % INK: lab})
    for k, v in kw.items(): g.set(k, v)
    return g

def path(parent, d, style, **kw):
    p = ET.SubElement(parent, "{%s}path" % SVG, {"d": d, "style": style}); [p.set(k, v) for k, v in kw.items()]; return p

def slug(s): return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")

def main():
    W, H = BOARD_W * U, BOARD_H * U
    svg = ET.Element("{%s}svg" % SVG, {"width": "%.4fin" % BOARD_W, "height": "%.4fin" % BOARD_H,
                                       "viewBox": "0 0 %s %s" % (fmt(W), fmt(H)), "version": "1.1"})
    ET.SubElement(svg, "{%s}title" % SVG).text = "Lady Luck playfield (assembled - do not cut)"

    under = layer(svg, "photo", "photo (underlay)", style="opacity:0.6")
    under.set("{%s}insensitive" % SOD, "true")
    if os.path.exists(os.path.join(FOLDER, UNDERLAY)):
        ET.SubElement(under, "{%s}image" % SVG, {"x": "0", "y": "0", "width": fmt(W), "height": fmt(H),
                      "preserveAspectRatio": "none", "{%s}href" % XL: UNDERLAY})

    grid = layer(svg, "grid", "grid (reference)")
    grid.set("{%s}insensitive" % SOD, "true")
    gs = "fill:none;stroke:#7a7a7a;stroke-width:3"
    path(grid, "M0,0H%sV%sH0Z" % (fmt(W), fmt(H)), "fill:none;stroke:#000000;stroke-width:4", id="board-outline")
    for x in (6.771, 13.542):
        path(grid, "M%s,0V%s" % (fmt(x * U), fmt(H)), gs + ";stroke-dasharray:30,20")
    for y in (14, 28):
        path(grid, "M0,%sH%s" % (fmt((BOARD_H - y) * U), fmt(W)), gs + ";stroke-dasharray:30,20")
    path(grid, "M%s,0V%s" % (fmt(9.20 * U), fmt(H)), "fill:none;stroke:#3060c0;stroke-width:2;stroke-dasharray:8,12", id="art-centre-line")

    bg_layers = {c: layer(svg, "bg-" + c, "background " + c) for c in COLOUR_ORDER}
    cream = layer(svg, "cream", "cream (preview - no cut)")
    cream.set("{%s}insensitive" % SOD, "true")
    colour_layers = {c: layer(svg, c, c) for c in COLOUR_ORDER}
    inserts = layer(svg, "inserts", "inserts (preview - no cut)")
    inserts.set("{%s}insensitive" % SOD, "true")
    holes = layer(svg, "holes", "holes (registration)")
    cl = layer(svg, "centerlines", "centerlines (reference)", style="display:none")

    rows = list(csv.DictReader(open(PLACEMENTS, newline="")))
    placed = 0
    for r in rows:
        if r.get("include", "yes").strip().lower() not in ("yes", "y", "1", "true"): continue
        fn = r["file"].strip(); src = find_piece(fn)
        if not os.path.exists(src): print("  missing:", fn); continue
        ox = float(r["origin_x_in"]) * U
        oy = (BOARD_H - float(r["origin_y_in"])) * U
        deg = float(r["rotation_deg"])
        name = fn[:-4] if fn.lower().endswith(".svg") else fn
        pre = slug(name) + "_"
        for kind, lays in read_piece(src).items():
            dest = holes if kind == "holes" else cl if kind == "centerlines" else cream if kind == "cream" else inserts if kind == "inserts" else \
                (bg_layers if "background" in name.lower() else colour_layers)[kind]
            g = ET.SubElement(dest, "{%s}g" % SVG, {"id": pre + kind, "{%s}label" % INK: name})
            for lay in lays:
                for k in lay: g.append(copy_moved(k, ox, oy, deg, pre))
        placed += 1
        print("  placed: %s" % name)

    ctl = layer(svg, "controls", "controls (reference)")
    def cross(g, x, y, name, colour, size=0.12):
        X, Y = x * U, (BOARD_H - y) * U; s = size * U
        path(g, "M%s,%sH%sM%s,%sV%s" % (fmt(X - s), fmt(Y), fmt(X + s), fmt(X), fmt(Y - s), fmt(Y + s)),
             "fill:none;stroke:%s;stroke-width:2" % colour, **{"{%s}label" % INK: name})
    tape = ET.SubElement(ctl, "{%s}g" % SVG, {"id": "tape-controls", "{%s}label" % INK: "tape controls"})
    controls = CONTROLS
    if os.path.exists(CONTROLS_CSV):
        controls = [(r["name"], float(r["x_in"]), float(r["y_in"])) for r in csv.DictReader(open(CONTROLS_CSV, newline=""))
                    if r.get("x_in") and r.get("y_in")]
    for n, x, y in controls: cross(tape, x, y, n, "#00b000", 0.15)
    if os.path.exists(HOLE_LIST):
        hl = ET.SubElement(ctl, "{%s}g" % SVG, {"id": "hole-list", "{%s}label" % INK: "hole list"})
        k = 0
        for r in csv.DictReader(open(HOLE_LIST, newline="")):
            low = {kk.lower().strip(): vv for kk, vv in r.items()}
            hid = low.get("id") or low.get("hole id") or low.get("hole") or ""
            xs = low.get("x") or low.get("x_in") or low.get("x (in)")
            ys = low.get("y") or low.get("y_in") or low.get("y (in)")
            try: cross(hl, float(xs), float(ys), hid, "#d000d0", 0.06); k += 1
            except (TypeError, ValueError): pass
        print("  hole list: %d points" % k)

    ET.ElementTree(svg).write(OUT, encoding="utf-8", xml_declaration=True)
    for g in list(bg_layers.values()) + list(colour_layers.values()) + [cream, inserts]:
        if len(g) == 0: svg.remove(g)
    print("wrote %s (%d pieces)" % (os.path.basename(OUT), placed))

if __name__ == "__main__":
    main()
