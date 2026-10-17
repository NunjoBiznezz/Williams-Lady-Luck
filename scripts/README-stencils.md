# Stencil scripts (Lady Luck)

## make_stencils.py
Makes the three cut files for a painted area with a keyline (border) around it:

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
bash scripts/stencils.sh "UL slingshot.svg"
```
The first run sets up its own small Python environment in `~/.venvs/stencils`
(needs internet once, takes a minute). After that it runs offline. Each Mac gets its
own copy, so it doesn't matter that the project folder syncs between them.
(The project's `.venv` folder was made on the Mac mini and points at that Mac's paths,
so it isn't used for this.)


Options go after the file name, e.g. `bash scripts/stencils.sh "UL slingshot.svg" --overlap 0.01`

### Useful options (inches)
- `--overlap 0.01`     border stencil goes 0.01in past each side of the line (default 0.005)
- `--area-grow 0.01`   area stencil reaches 0.01in past the centre line (default 0)
- `--mask-grow -0.005` make the mask a hair smaller
- `--width 0.052`      override the keyline width
- `--windows none`     no alignment windows; or `--windows hole1,hole3`
- `--only border`      make just one file (area | mask | border)

Each run prints the node count of every file so you can see it stayed simple.
In Silhouette: cut the "cut" layer only; the "holes (reference - no cut)" layer is for lining up.

In the output files every registration mark is its own group ("post N" = outline + screw, "hole N" = the hole outline),
so each one can be selected and shown/hidden on its own in Silhouette Studio. The source SVG is never changed.
