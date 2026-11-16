# Williams Lady Luck (1968) - playfield restoration

Artwork, measurements and reference material for repainting the playfield of a
Williams **Lady Luck** electromechanical pinball machine (1968).

The playfield art is being redrawn piece by piece as clean, true-scale vector files.
Those files are used to cut paint-mask stencils on a Silhouette Cameo, so each colour
can be airbrushed back onto the wood, and to print black-only waterslide decals for
the fine line art and lettering.

![The Lady Luck playfield, lit](illuminated%20PF.webp)

## What's in here

| Folder / file | What it is |
|---|---|
| `stencils/` | **The source artwork.** One SVG per playfield element (pop bumpers, lanes, slingshots, saucers, the card fan, the girls ...). This is the heart of the project. |
| `images/` | Photos of the original playfield (straightened and scaled) and the GIMP working files the artwork was drawn from. |
| `Lady Luck playfield.svg` | Every piece assembled at its true position on the 20-5/16 x 42 in board. For checking fit - not for cutting. |
| `playfield background.svg` | The background colour areas (rays, green rings, keylines), drawn in board coordinates. |
| `playfield placements.csv` | Where each piece sits on the board (position and rotation). |
| `playfield controls.csv` | Tape-measured control points used to line everything up. |
| `Playfield coordinates and hole IDs.md` | The coordinate system and how holes are numbered. |
| `playfield.json` | Game settings read by the scripts (board size, special cases). |
| `game_scripts/` | Scripts that only apply to Lady Luck (the green ring stencils). |
| `silhouette/` | Silhouette Studio files for a few pieces. |
| `fonts/` | The open fonts used to rebuild the lettering (Archivo Black, Oswald, League Gothic and others). |
| `Lady Luck project notes.md` | The detailed working log: every piece, sizes, line widths, decisions and lessons learned. |
| `Williams_*.pdf`, `*certificate*` | Instruction manual, schematics, instruction cards and a reproduction manufacturer's certificate. |
| `scripts` | A link to the shared scripts - see "Scripts" below. |

## How the artwork is organised

The playfield is divided into a 3 x 3 grid, and each file name starts with the cell it
belongs to:

|  | Left | Center | Right |
|---|---|---|---|
| **Upper** | UL | UC | UR |
| **Center** | CL | CC | CR |
| **Lower** | LL | LC | LR |

So `UL queen lane.svg` is the queen lane in the upper left, and `LC card fan.svg` is
the fan of cards in the lower centre. Reusable parts (`suits.svg`, `lane card.svg`)
have no grid code.

Every source SVG follows the same rules:

- **True scale:** 300 units = 1 inch.
- **One layer per paint colour** (red, blue, yellow, green, black). There is no cream
  layer - cream is the base coat, so cream areas and bare wood are simply left open.
- **Few nodes.** Geometric parts are rebuilt from measured lines, arcs and circles, and
  lettering from real font outlines. Only the freehand art (the girls) is traced. This
  keeps the files easy to edit and clean to cut.
- **A `holes` layer** with the playfield's posts, holes and slots, used to register
  each stencil on the board.
- **A `centerline` layer** on pieces with a painted border, which the scripts use to
  work out the border and mask shapes.

Approximate palette: red `#bf2c10`, blue `#1a5470`, black `#12160d`,
yellow `#f8d344`, green `#16a050`, over a cream base.

## From source file to painted playfield

1. Photograph the original art over graph paper, then straighten and scale the photo.
2. Redraw the element as a layered SVG in `stencils/`.
3. Run the scripts to generate the cut files: a stencil for each colour, cover masks
   for areas already painted, and border stencils for the outlines.
4. Cut them on the Silhouette Cameo, then paint: white base, cream areas, mask those
   off, background colours, each element's colours, and the black outlines last.
5. Print black-only waterslide decals for detail too fine to paint.

The cut files are **not stored in this repository**. They are written to a
`_generated/` folder and can always be remade from the sources.

## Scripts

The scripts are shared between games and live in their own repository,
[playfield-tools](https://github.com/NunjoBiznezz/playfield-tools). The `scripts`
entry here is a link that expects that repository two folders up:

```
Pinball/
  playfield-tools/         the shared scripts
  Williams/Lady Luck/      this repository
```

With both in place, run these from the Lady Luck folder:

```bash
bash scripts/stencils.sh                               # make every stencil
bash scripts/stencils.sh "stencils/UL pop bumper.svg"  # just one piece
bash scripts/decals.sh                                 # black-only decal files
python3 scripts/build_playfield.py                     # rebuild "Lady Luck playfield.svg"
```

See the playfield-tools README for setup and for what each script does.

You don't need the scripts to use the artwork: the SVGs in `stencils/` open directly
in Inkscape or Silhouette Studio.

## Tools used

Inkscape and GIMP for drawing, Silhouette Studio with a Silhouette Cameo 5 for
cutting, Python for the scripts, and an airbrush for the paint.

## Status

A work in progress. Pieces are added and refined as the restoration goes on;
`Lady Luck project notes.md` has the current state of each one.
