# Stencil scripts (Lady Luck)

## One command: make_all_stencils.py (run with stencils.sh)
```
cd ~/Documents/Pinball/Williams/Lady\ Luck
bash scripts/stencils.sh                               # every source SVG in stencils/
bash scripts/stencils.sh "stencils/UL pop bumper.svg"  # just this one
bash scripts/stencils.sh --dry-run                     # list what would be made, make nothing
```
It looks at the layers of each source SVG and calls the right generator. Each kind of
stencil keeps its own script (below); make_all_stencils.py only decides and calls them:

| The SVG has | Generator | Makes |
|---|---|---|
| a `centerline` layer | make_stencils.py | area stencil, area mask, border stencil |
| paint layers (red, blue, black ...) | make_layer_stencils.py | one stencil per paint layer (black last); `1 area mask` if there is an `area` layer; trim lines from a `trim` layer |
| both | both | the bordered set **and** a numbered stencil for each colour (see below) |
| (whole folder only) | make_green_rings.py | LC green rings sheets, from Lady Luck playfield.svg |

**Pieces with a centerline and colours** (e.g. UC pop bumper with 100 rollover, UL queen lane, the
saucer jokers, card fan): the colour stencils are run with `--except-keyline`. Any filled piece of a
paint layer that lies inside the keyline band (centre line +/- half its width) is left out, with the
subpaths that outline it, because the border stencil paints it; a layer that is only keyline (the
blue on the lamp strips and slingshots) gets no colour stencil. Colour areas whose edges run under a
keyline are kept whole. Subpaths are kept or dropped whole, never booleaned, so the nodes stay as
drawn. Where black outlines are joined to other black shapes (e.g. card outlines and their shadows
in the card fan) they stay in the black stencil too - same colour, so painting them twice is harmless.
Suggested order: area stencil (base colour), colour stencils 1, 2, 3 ..., border stencil last.

Layers that are never stencils: anything labelled reference / no cut, holes, centerline,
photo, grid, pen; `area` only makes the mask; `trim` only adds cut lines.
Not sources (skipped, list at the top of make_all_stencils.py): the old `* suits.svg` copies,
`insert masks letter.svg` and `UL slingshot white mask.svg` (already cut sheets), and the green
rings pieces file (made by make_green_rings.py). A file with neither a centerline nor paint
layers is reported as skipped.

Before a piece is made, its old sheets in `_generated` (`<name> - *.svg`) are removed, so
nothing stale is left from an earlier numbering (`--keep-old` keeps them).
Generator options can go on the same line; each generator only gets the ones it knows
(`--overlap` -> make_stencils.py, `--mark-offset` -> make_layer_stencils.py, `--mask-grow` -> both).
At the end it prints what was made, what was skipped and why, and anything that failed.
`layer_stencils.sh` still works (same as stencils.sh). The individual scripts can still be run
on their own, e.g. `python3 scripts/make_stencils.py "stencils/UL slingshot.svg"`.

### Covers (area masks) with alignment windows
A piece with a hidden `area (reference - no cut)` layer gets `<name> - 1 area mask.svg`: the
cover you stick on the element while you spray the background. If the piece has a
`holes (registration)` layer, every hole inside the cover (posts never, holes at least 0.15in
across) is cut out of it as a window 0.02in smaller all round, same shape (the pop bumpers get
their saturn centre hole and the two big round holes): centre each window over its hole.
The mask sheet carries no trim lines. Options: `--window-margin 0.02`, `--min-window 0.15`,
`--windows none`. The UL/UR/CC pop bumper covers end on the middle of the outer black line.

## make_stencils.py
Makes the three cut files for a painted area with a keyline (border) around it.
They are written to a `_generated` folder in the directory you run the script from
(run it from the project root, so they land in `_generated/` beside `scripts/`),
which is in `.gitignore`: they are outputs, not assets - remake them from the source SVG
rather than editing them.

| Output | Use |
|---|---|
| `<name> - area stencil.svg` | Paint the area colour (e.g. cream). Keep the piece that drops out: it is the area mask. |
| `<name> - area mask.svg` | A separate copy of the mask, if you need to recut it. |
| `<name> - border stencil.svg` | Paint the keyline (border) colour last. |

The source SVG needs a layer with id `centerline` (one closed path along the middle
of the keyline, `data-width="0.06in"` = line width) and, optionally, a `holes` layer
with the registration marks (`postN` groups and `holeN` paths).

### Run it (Terminal, on either Mac)
```
cd ~/Documents/Pinball/Williams/Lady\ Luck
bash scripts/stencils.sh "stencils/UL slingshot.svg"
```
(stencils.sh runs make_all_stencils.py, which sends a centerline file here.) The first run sets up its own small Python environment in `~/.venvs/stencils`
(needs internet once, takes a minute). After that it runs offline. Each Mac gets its
own copy, so it doesn't matter that the project folder syncs between them.
(The project's `.venv` folder was made on the Mac mini and points at that Mac's paths,
so it isn't used for this.)

Output: `_generated/UL slingshot - border stencil.svg` etc. (`--outdir` to put them elsewhere).


Options go after the file name, e.g. `bash scripts/stencils.sh "UL slingshot.svg" --overlap 0.01`

### Useful options (inches)
- `--overlap 0.01`     border stencil goes 0.01in past each side of the line (default 0.005)
- `--area-grow 0.01`   area stencil reaches 0.01in past the centre line (default 0)
- `--mask-grow -0.005` make the mask a hair smaller
- `--width 0.052`      override the keyline width
- `--windows none`     no alignment windows; or `--windows hole1,hole3`
- `--only border`      make just one file (area | mask | border)

Each run prints the node count of every file so you can see it stayed simple.
### Keyline that stops under something (noborder)
If the keyline must stop where another piece sits on top (e.g. the saucer ring on the CL/CR
lamp strips), add a closed path to the centerline layer with an id starting `noborder`
(e.g. `noborder-saucer`, a 4-node circle). It is not an area: the border stencil band is
simply left out inside it. The area outlines are closed with an arc just inside it, so their
band disappears completely.

In Silhouette: cut the "cut" layer only; the "holes (reference - no cut)" layer is for lining up.

In the output files every registration mark is its own group ("post N" = outline + screw, "hole N" = the hole outline),
so each one can be selected and shown/hidden on its own in Silhouette Studio. The source SVG is never changed.

### Several keylines in one piece (per-line widths)
Every closed path in the centerline layer gets its own border band, so nested keylines
(a card outline inside an arrow, a ring inside a banner) all appear in the border stencil.
A path can have its own `data-width="0.03in"`; otherwise it uses the layer's data-width.
`--width` on the command line overrides all of them.

### Sharp tips
Border bands are offset with mitre joins, so a sharp tip (banner swallowtail, arrow wing)
stays sharp and covers the painted point. Rounded corners come out the same as before.

### Banner behind a card / line ending at a ring (saucer jokers)
`noborder` paths are used for: the card face (the banner line runs behind the card), the
saucer face inside the ring, and two small caps where the banner line meets the ring with a
square end (so no round bump sticks out past the ring).

## make_layer_stencils.py - flat-colour artwork (the girls)
For art drawn with one layer per paint colour (e.g. `stencils/CL dancing girl.svg`: green, blue,
red, black + the hidden "area (reference - no cut)" outline). No centerline layer needed.

```
cd ~/Documents/Pinball/Williams/Lady\ Luck
bash scripts/stencils.sh "stencils/CL dancing girl.svg"
```
(stencils.sh sends a file with paint layers and no centerline here)

Writes to `_generated/`, numbered in paint order:

| File | Use |
|---|---|
| `<name> - 1 area mask.svg` | Cut out the figure outline; the piece that drops out is the mask. Stick it on the figure (over the cream base), paint the background, peel it off. Shrunk 0.005in so the background tucks under the black outline. |
| `<name> - 2 green stencil.svg` ... | One per colour layer, in the file's layer order. Openings copied exactly from the source (same nodes). |
| `<name> - N black stencil.svg` | Black is always last. |

Every file has the same 3 registration marks outside the art (top-left, top-right, bottom-left -
not symmetric, so a sheet can't go on flipped):
- layer **cut**: the openings + a small round window (1/16in) at each mark
- layer **pen (Tool 2) - registration**: a cross at each mark, for the pen in Tool 2
- layer **outline (reference - no cut)**: the figure outline, just for orientation

Lining up: put a small piece of masking tape under each mark, lay the first sheet (area mask) in
place, dot each tape through its window with a fine pencil. Every later sheet goes on with its
windows over the dots. The script reports "loose film islands" (e.g. the face inside the black
stencil): those pieces of film are inside an opening, so lift the stencil with transfer tape to
keep them in place.

Options (inches): `--mask-grow -0.005`, `--mark-offset 0.20`, `--mark-size 0.25`,
`--window 0.0625` (0 = no window), `--outdir DIR`. The source SVG is never changed.

## Trim lines (layer "trim (cut only)" in the source)
Cut-only lines for trimming the film where a piece meets a neighbour. Draw them in the source SVG in a layer whose label starts with "trim", one path per line. A trim line can be straight, a polyline (e.g. the two edges of the ADVANCE CARD banner notch on the UL/UR pop bumpers) or curved (e.g. the arc of the CC pop bumper circle on UL/UR); lines, curves and arcs, absolute or relative coordinates, as Inkscape writes them. make_layer_stencils.py cuts each path exactly as drawn, runs its two open ends on to the sheet edges in the same shape (a straight end carries on straight; a curved end carries on round the circle it lies on, so the CC bumper arc becomes one smooth circle edge to edge), adds it to the "cut" layer of every sheet as `trim-line-N` (blue stroke, never painted), and reports whether it crosses any artwork (running along an art edge is fine). The 3 registration marks stay on the artwork side of every trim line: the corners are used when they are clear, otherwise the marks move along the sheet edges (as far apart as possible, triangle kept lopsided so a sheet can't go on flipped) and the script prints where they went. build_playfield.py ignores the trim layer. If you move a trim line in Inkscape, keep it free of transforms (no transform on the layer or path).
