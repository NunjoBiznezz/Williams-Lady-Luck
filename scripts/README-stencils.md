# Stencil scripts (Lady Luck)

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
The first run sets up its own small Python environment in `~/.venvs/stencils`
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
bash scripts/layer_stencils.sh "stencils/CL dancing girl.svg"
```
(uses the same `~/.venvs/stencils` environment as stencils.sh)

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
Straight cut-only lines for trimming the film where a piece meets a neighbour (first use: UL/UR pop bumpers where they meet the CC pop bumper). Draw them in the source SVG in a layer whose label starts with "trim" - one straight path per line (only its first and last points are used; absolute or relative coordinates both work). make_layer_stencils.py runs each line out to the sheet edges, adds it to the "cut" layer of every sheet as `trim-line-N` (blue stroke, never painted), reports whether it crosses any artwork, and picks the 3 registration marks from the 4 corners so they all stay on the artwork side. build_playfield.py ignores the trim layer. If you move a trim line in Inkscape, keep it free of transforms (no transform on the layer or path).
