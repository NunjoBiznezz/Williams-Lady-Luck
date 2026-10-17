# Lady Luck Playfield - project notes

Context for future sessions (Williams Lady Luck playfield restoration, stencils cut on a Silhouette Cameo 5 Plus, painted over a cream base).

## Naming convention (playfield grid)
The playfield is divided into a 3 x 3 grid. Each playfield piece's file name starts with its grid code:

|  | Left | Center | Right |
|---|---|---|---|
| **Upper** | UL | UC | UR |
| **Center** | CL | CC | CR |
| **Lower** | LL | LC | LR |

Format: `<grid code> <short description>.svg` (e.g. `UL queen lane.svg`). When a section has several pieces, the description tells them apart. Reusable assets (suits, fonts, scripts) have no grid code.

## Files (Documents/Pinball/Williams/Lady Luck - synced to both Macs via iCloud)
| File | What it is |
|---|---|
| UL card value when lit.svg / .png | Left CARD VALUE / WHEN LIT insert (red flags + funnel, blue body, 100 circle) |
| UR card value when lit.svg / .png | Right version (mirror-ish, same card/text/circle sizes) |
| UL queen lane.svg | Blue lane, QUEEN card (red Q/diamond), 10 CARD POINTS, 100, slot, holes layer. Rebuilt 2026-10-15: all lettering from real font outlines (QUEEN + corner Qs Oswald SemiBold stretched 1.17 wide; 10 CARD POINTS Archivo Black thinned 0.005in; 100 League Gothic thinned 0.007in), one path per word; lane/card/slot from measured lines + arcs, symmetric about x=309.72 (black 4,400 -> ~370 nodes total). Old version in _previous/ |
| UR king lane.svg | Yellow lane, KING card (black K/spade), same layout |
| UC pop bumper with 100 rollover.svg | Green/yellow/red bumper with 12 red suits + overlapping 100 rollover star; holes layer |
| CC pop bumper.svg | Blue ring with 11 cream suits (6 o'clock suit hidden by slot), black rings, holes layer |
| LC lady luck girl.svg | Traced girl artwork; layers blue, red, black (no cream) |
| LC card fan.svg | Ace-10 cards fanned around the green circle (15.78deg apart), black shadows offset up/right, red/black indices (Oswald + suits), ACE in Oswald SemiBold; insert holes on holes layer. Each higher card overlaps the previous card and its shadow. Built from two stitched photos. |
| CR saucer joker.svg | CARD VALUE AND 50 POINTS banner (yellow) wrapped around the right saucer, swallowtail behind a JOKER card with 3/4in insert; built from measured lines/circles + fonts |
| CL saucer joker.svg | Mirror of CR with a teal banner (text not mirrored) |
| CL advance card rollover.svg / CR advance card rollover.svg | ADVANCE CARD V-banner (cream, black outline) over a blue ring around the rollover button; both sections use the same design |
| UL slingshot.svg / UR slingshot.svg | Cream sling areas: just an even 0.06in blue border (measured straight edges + the UR arc, rounded corners) and a holes layer with posts (+ centre dots), rubber/switch holes and screw holes |
| UL lamp strip.svg / UR lamp strip.svg | Small cream strips over the lamps: even 0.045in blue stadium border (two posts as round ends); holes layer with posts + screw dots, lamp hole and large hole. UL is in the teal area, UR in the yellow/teal area |
| UL pop bumper.svg / UR pop bumper.svg | Red-ring pop bumpers, same ring sizes as CC: wood centre, yellow ring, black line, wood ring, black line, red ring with 12 cream suits (UL starts spade at top, UR starts heart; spade/heart/diamond turned 270, club 90), black outline. CC bumper and ADVANCE CARD banner sit on top, so they are cut out. Holes layer = centre holes |
| CL lamp strip.svg | Long cream strip running above and below the left (teal) saucer, built from two stitched photos (CL lamp strip stitched.png): even 0.052in blue border - straight right line, round cap at the top post, bend around the second post, straight left line below the saucer, rounded bottom corners; border stops where the saucer ring sits on top. Holes layer = posts, lamp holes, screw, saucer |
| CR lamp strip.svg | Mirror-type strip at the right (yellow) saucer: straight left line, round top cap, pointed corner by the second post then a concave curve into the saucer ring, straight lower right line, rounded bottom corners; even 0.052in blue border. Holes layer = posts, lamp holes, screw, saucer |
| insert masks letter.svg | 8.5x11 sheet of insert masks: 12 x 1-3/16in (4 on playfield) and 72 x 3/4in (14 on playfield), 4-node circles, exact insert size, 1/8in apart, 3/8in margins; one layer per size |
| lane card.svg | Card on both lanes (UL QUEEN / UR KING - same size and position): centerline layer (0.028in outline centre, 1.285 x 1.788in, corner r 0.109in) + reference outline. Outputs "lane card - area stencil.svg" (paint the card face) and "lane card - area mask.svg" (cover the face while painting the lane colours), both cut on the centre line, 8 nodes |
| suits.svg | Reusable diamond / club / spade / heart, true size (~0.5in wide) |

Doug's own source files (GIMP .xcf files, card value 100.svg, etc.) keep their original names for now.
| fonts/ | Archivo Black, Oswald (200-700), League Gothic, Archivo Narrow, Francois One + README |
| scripts/ | stencil_rectify.py, rectify_cleanup.py, crop_paper.py, rescale_images.py, png2stencil.py ... |

## SVG conversion rules (agreed)
- Simple paths, few nodes: straight edges = single straight segments, curves only where needed; does not need to match perfectly.
- True scale: 300 units = 1 inch.
- One layer per paint colour (red, blue, black, yellow, green as needed). **No cream layer** - cream is the painted base coat; card faces, cream lines/chevrons and suits on blue are left open. Wood areas are left open (transparent).
- Colours run under the black line art (trap ~0.013-0.027in); colour is solid under black lettering.
- Extra layer "holes (registration)" = outlines of playfield holes/slots/posts; hide or delete before cutting. **Round holes are written as 4-node circles (4 cubic curves), never as polylines or many-node paths - they must be easy to edit in Silhouette.** Non-round holes get as few curves as possible. Each mark is its own path; a **post** (circle with a centre screw hole) is a group "post N" = 11/32in outline (measured post base) + screw circle. Some photo holes look bigger because damaged holes were repaired with dowels - ignore that. Applied to all files.
- Geometric parts are rebuilt from measured shapes (circles, rounded rects, straight lines) and real font outlines; only freehand art (girl, rollover star) is traced.
- Circles and rings are written as true SVG arcs (a full circle = 2 arc commands); where something overlaps a ring, the cut edge is an arc of the overlapping circle. Suits are written as their smooth library paths, not polygons.
- Rounded corners are ONE arc each (written as 1-2 cubic curves), never a run of tiny segments; straight edges are single lines. Slings fixed this way (UL blue 80->24 nodes, UR 146->26).
- Cards are key elements: rounded rectangle with a uniform outline width all the way round.
- Lines that pass behind another element (e.g. flag edges behind a card) stay straight and full width.
- **Line art**: colour areas are enclosed by thick black lines of one constant width that curve smoothly, all bending the same way. First work out what the artwork is made of (e.g. the UC star = a back 4-point star of nested bands blue/red/cream/green under a front 4-point star blue/yellow) and rebuild those shapes: each side one circular arc, nested bands as parallel offsets, the front shape simply covers the back one. Fit the few parameters to the photo (scripts/twostar_model.py) rather than tracing pixel boundaries. Sharp tips stay sharp.

## Fonts
- CARD VALUE / 10 CARD POINTS: Archivo Black (slightly thinned on the lanes)
- WHEN LIT, QUEEN, KING, card corner letters: Oswald SemiBold (WHEN LIT ~6% letter spacing)
- "100": League Gothic (slightly thinned)

## Palette (approx)
red #bf2c10, blue #1a5470, black #12160d, yellow #f8d344, green #16a050; cream base (246,227,156).

## Line widths (px @300dpi)
Main outlines ~15.5 (0.052in); card outlines 8.5-14; lane slot outline 10.5; pop bumper rings measured individually.

## Masks for painted base areas
For a base colour that is already painted (e.g. white on the upper third), a mask file covers that area, enlarged 0.03in into the surrounding keyline (keylines are painted last). Clear stencil film can't be printed, so the mask has alignment windows cut 0.02in smaller than real through-holes inside the area; line the windows up over the holes. Example: UL slingshot white mask.svg.

## Plain outlined areas (e.g. slings)
Only the border colour is a stencil; the inside is base coat. Border = one even-width band built from fitted straight lines/arcs; registration from the holes inside the border (posts with centre dots, larger holes, screw holes).

## Lessons / gotchas
- Check photos for scale/tilt before measuring (one photo was squashed 7% vertically, the Queen photo tilted 1.3deg, the star photo rotated 3.6deg vs the bumper photo).
- Pop bumper suit orientation: hearts/spades/diamonds turned one way, clubs the other.
- After saving to the folder, verify the copy (an early save silently wrote a stale file).

- Thinning lettering: offset the font outline with a node-preserving offset (Tiller-Hanson: offset each control-polygon edge, intersect neighbours) so the glyph keeps the font's nodes and sharp corners; a polygon offset rounds the corners and adds hundreds of nodes.
- UR king lane.svg still has the old traced/offset lettering - same rebuild applies.
- make_stencils.py samples and refits the outline, so a perfect rounded rectangle comes back up to ~0.001in off (lines not quite square, corners slightly shifted). For the lane card the cut path was replaced with the exact centre line afterwards.

## Possible next steps
- Split top center bumper into separate bumper / star files if wanted.
- Registration marks common to all colour layers; minimum-feature check (thin slivers < 0.02in).
- Stencil-ready script (PNG -> simplified layered SVG) in scripts/.
- Playfield background colour areas (yellow, teal, green) as their own stencils.

## Whole-playfield assembly (pilot 2026-10-16)
- **Lady Luck playfield.svg** = all pieces at true position, 20.3125 x 42in, 300 units/in, y down from the top edge. For checking and for drawing the background colour stencils, **not for cutting**. Layers: photo (underlay, linked, locked), grid (reference), yellow, green, teal, blue, red, black, holes (registration), centerlines (reference, hidden), controls (reference: tape controls; the hole list too if "Lady Luck hole list.csv" is in the folder).
- Regenerate it after any piece changes: `python3 scripts/build_playfield.py` (plain Python, no packages). Pieces are copied in as plain paths moved/rotated into place (no clones or transforms); node counts are unchanged (checked: 7,093 drawing commands in = out).
- **playfield placements.csv**: one row per piece: origin_x_in / origin_y_in = the piece's top-left corner in board coordinates (origin lower-left, Y up), rotation_deg clockwise about that corner, include yes/no. Add a row to bring in another piece.
- **images/playfield aligned 150ppi.jpg**: the straightened photo resampled to exactly 150 px/in, board-aligned (0,0 = top-left of the wood). Fit to the four primary reference holes: 149.87 px/in, -0.07deg, 0.020in rms.
- Placement method: each piece rendered and matched to the photo by its paint colours (position + rotation), then checked against the photo's holes. Hole check rms 0.02-0.07in. Several pieces needed up to ~1.9deg rotation (source photos were tilted): UC bumper -1.85, CL lamp strip +1.70.
- Saucer files renamed by Doug 2026-10-16: "CL saucer joker" (yellow) = left saucer, "CR saucer joker" (teal) = right. The lamp strips still fit the other way round: "CR lamp strip" sits at the LEFT saucer, "CL lamp strip" at the RIGHT (not renamed - Doug's call).
- **playfield controls.csv**: control points (name, x_in, y_in, source) drawn on the controls layer; edit it to correct a point. Left saucer re-measured on the aligned photo (outer rim circle fit): X 1.466, Y 21.330 (tape had 1.344, 21.25). The photo puts the right saucer at about X 17.06, Y 21.33 (tape 17.0, 21.25), not changed.
- Also placed: LL / LR card value when lit (no holes layers, so no hole check; the left one is faded on the board). LC lady luck girl.svg was missing for a while on 2026-10-16 evening (restored).
- 2026-10-16: also placed UL queen lane, UR king lane, LC card fan and LC lady luck girl (20 pieces). The whole-board photo (150 px/in, slightly soft) is good for geometry, positions and the background colour areas; small lettering (~0.1in card corners) and fine face detail are blurry at that resolution, so those still come from fonts or close-up photos.
- 2026-10-16 evening: five pieces drawn directly from the aligned whole-board photo, in board coordinates (placements rotation 0):
  - **LR slingshot.svg**: cream area with an even 0.06in blue border (5 measured straight lines, 5 one-arc corners, 26 nodes) + centerline layer (data-width 0.06in) + holes layer (5 posts, three 15/32in holes, 2 screw holes, 1in x 1/2in slot). Ready for scripts/stencils.sh.
  - **LL slingshot.svg**: the upper half is faded on the board, so it is the mirror of LR, fitted (position + 0.7deg) to the visible lower border; its holes are measured on its own side. The left sling is not an exact mirror of the right (edges centre on X 9.257, posts on ~9.21).
  - **LC same player shoots again.svg**: red area (lettering + 1in insert left open), 0.04in black outline; sides, top and bottom are single circle arcs (sides r 2.013, mirrored about X 9.215). Lettering Oswald Regular (400), fitted to the measured line boxes.
  - **CC advance card hex.svg**: 0.04in black outline (hexagon symmetric about X 9.242) + ADVANCE / CARD in Archivo Black; holes layer = rollover ring (1.19in, centre 9.239, 14.056). Named CC because the rollover centre is just above Y 14.
  - **CC ace 1 card point.svg**: arrow with 0.04in black outline, symmetric about X 9.278; its bottom edge is the green-ring circle (centre 9.244, 14.056, r 6.123 - same centre as the ADVANCE CARD rollover). ACE card 0.03in outline, corner r 0.07; 100 = League Gothic, ACE = Oswald SemiBold, 1 CARD POINT = Archivo Black, red A = Oswald Medium + library heart.
- Photo vs tape: the photo puts the hex rollover at Y 14.056 (tape 13.94) and the SPSA insert at 9.216, 8.119 (tape 9.1875, 8.0). With the saucers (+0.08), the tape Y values look ~0.1in low; worth re-checking the tape origin.
- 2026-10-16 night: the four girls in the centre and the background (master now 30 files):
  - **LC red girl.svg** / **LC blue girl.svg**: traced from Doug's close-ups (red girl.xcf / blue girl.xcf, 300 ppi) registered to the board by feature matching (scale 1.00, rms ~0.006in). **CL dancing girl.svg** (green hair) and **CC standing girl.svg** (red trousers): traced from the aligned whole-board photo (150 ppi upsampled) - softer; faces/fingers are approximate. Layers green/blue/red/black (skin and cards = cream base, left open), colours run 0.013in under the black, plus a hidden "area (reference - no cut)" outline for making masks. Traced freehand art: black ~400-1060 nodes per girl.
  - **playfield background.svg** (whole board, origin 0,42): yellow + teal = 12 ray sectors from one centre (X 9.300, Y 14.141; boundaries at 29.9, 60.15, 89.9, 116.8, 150.3, 178.75 deg and the same +180). Outside the outer green ring only the upper rays continue: lower-left teal, lower-right yellow, split at the horizontal 178.75/358.75 ray. Field outline: top arch circle (centre 10.295, 31.522, r 8.008, rms 0.010in), sides X 0.32 and 17.92 up to Y 32.3, bottom = wood lobes (the SPSA side circles, r 2.013) and the lower sling bottoms. Green rings: outer between keylines r 6.182 / 6.575, inner r 3.766 / 4.091 (black keylines 0.04-0.05in). Black keylines also along the wood lobes from the slings to SPSA. All edges are straight lines or true arcs (yellow ~90, teal ~95, green 17, black 51 nodes). The pieces are NOT cut out of it: paint background colours with each piece covered by its area mask. Still needs splitting into Cameo-size sections.
  - build_playfield.py: a file with "background" in its name goes to separate "background <colour>" layers at the bottom; empty layers are dropped.
  - Not included: the small "LADY LUCK" signature on the wood near the right flipper.
- **playfield cream preview.svg** (PREVIEW ONLY, never cut): the cream base where the pieces leave it showing (piece footprints, large wood centres left open), traced from the assembled pieces. build_playfield.py puts it in a locked "cream (preview - no cut)" layer between the background and the piece colours, so the master looks like the finished board. No piece file was changed. Remake it after adding pieces (ask Claude); untick it in placements.csv to drop it.
- Cream preview updated: the big lady (LC lady luck girl) is now cream-filled (her footprint = her ink plus the cream seen in the photo around it); the four smaller girls use their own hidden "area" outline layers.
- Cream preview v3: also shows bare wood/hardware (pop bumper wood rings and centres, lane slots, rollovers, saucers) and the 15 inserts (14 x 3/4in: 10 card fan, 2 jokers, 2 CARD VALUE WHEN LIT; SAME PLAYER 1in). Wood rings = enclosed gaps in a piece whose photo colour is wood. Still preview only.
- Rollover button plastics measured on the photo: CL/CR ADVANCE CARD 1.16in, centre hex 1.19, top 1.21 = the 4 x 1-3/16in inserts on the insert sheet. Shown in a new "inserts (preview - no cut)" layer above the paint (build_playfield.py). Note: CL/CR advance card rollover.svg holes layer has the opening at 1.079in, smaller than the 1-3/16 plastic - check before using it for registration.
- 2026-10-16: all four rollovers are the same size (Doug): holes set to 1-3/16in (4-node circles, same centres) in CL/CR advance card rollover.svg, CC advance card hex.svg and UC pop bumper with 100 rollover.svg (hole 7); originals in _previous/"... (before rollover 1-3-16).svg". The CL/CR ring black inner edge sits at 1.158in, i.e. right at the plastic edge. In the UC file the star paint layers run across the top rollover hole (fine for spraying; could be knocked out).
- 2026-10-16: playfield background.svg now leaves the bare wood/hardware unpainted (Doug): cut out of yellow + teal = the 4 pop bumpers' wood centre discs and wood rings (true circles fitted to the bumper files), the 4 lane slots (QUEEN, KING, LL/LR CARD VALUE; stadium shapes), the 4 rollovers (1-3/16in) and both saucers (1.48in). Inserts are not cut out (insert masks cover them). Previous version in _previous/.
- Cream preview v7: inside the traced girls, areas the photo shows as yellow/teal stay background (big lady under her raised arm and between the fingers, red girl between the legs); lamp strips filled using the saucer ring as part of their outline. Girls rebuild still to do: current node counts black 535-1094 per girl; an automatic clean-up only saves ~10-30%, so the plan is a per-girl rebuild from straight-edged shapes with constant-width black outlines.
- 2026-10-17: **LC blue girl.svg legs rebuilt** (Doug: too many nodes, lower legs chopped where the big girl's fingers cross them). Each leg is now two straight constant-width black lines (0.030in = the dress outline width) with one sharp knee each, fitted to the black lines in blue girl.xcf (svg = xcf px - (41, 39)). The lines run continuously under the big girl: her left leg (viewer's left) down under the big girl's card, ~0.1in past the card outline; her right leg under the big girl's hair, ending inside the black hair. The straight dress sides above the hem were merged into the same lines. Legs below the hem 220 -> 28 nodes; black layer 801 -> ~660 nodes. Canvas extended downward to 5.9in tall (origin unchanged, so placements.csv unchanged); the hidden area layer follows the new legs. Old version: _previous/LC blue girl (before leg rebuild).svg. Master regenerated.
- 2026-10-17 (later): the big girl is in front, so the blue girl's leg lines are now cut where the big girl covers them: they show only outside her, in the teal gap between her thumb and fingers, in the small gap between her finger and card (left leg), and between her fingertips and her hair (right leg). Each visible piece ends at the middle of the big girl's black outline (tucked 0.008in under it), so nothing shows on her hand, card or hair. The cut used the big girl's outlines plus the photo to tell skin/card (hidden) from background gaps (visible). Legs below the hem ~60 nodes in 12 straight pieces.
- 2026-10-17: **LC lady luck girl.svg - raised (right) hand rebuilt** (Doug: finger lines got too thin; the hand is drawn with straight lines). Skin outline = straight-line polygon taken from the old trace (matches lady luck girl.png and the board photo); black = one constant 0.040in (12 unit) band outside it, so no line is thinner than the blue girl's legs (0.030in minimum, Doug). Finger tips stay sharp: each skin tip was pulled back until the band's mitre point lands on the black tip, so the end of each finger is solid black instead of thinning lines. The line between the two overlapping lower fingers widened to 12. The held card's top edge, top-right corner (one arc) and right edge rebuilt at 0.042in. Joins the old arm outline at x=760 (tapered). Only the hand area changed (rest of the black untouched, verified); black 1050 -> ~1040 nodes. Old version: _previous/LC lady luck girl (before hand rebuild).svg. LC blue girl.svg re-clipped to the new outlines.
- Method note: skia-pathops booleans split every curve at its extrema (~10% more nodes). Scripts now put the original curves back after each boolean (restore step), so untouched art keeps its node count.
- Other old lines still thinner than 0.030in: e.g. the held card's left edge (~0.029in), some hair/face strokes. Not changed.

- 2026-10-17: **LC red girl.svg fixed** (the green-shirt / red-trousers girl; file now in stencils/), using images/green shirt girl.jpg (registered to the SVG locally, ~1 unit). Raised (right) hand: outline rebuilt as one 0.030in band (wrist corner, knuckle apex, down to the card's top-left corner - the right side was missing), finger/nail strokes redrawn as 6 tapered strokes with sharp tips (max 0.030in), card left edge made continuous at 0.030in; thumb triangle and cuff kept. Left elbow: both arm lines carried down to a sharp elbow point (0.030in, 5 straight segments). Lower legs + feet (below Y 1290 units) rebuilt from straight lines: leg outlines fitted to the existing lines (0.040in outer, 0.030in between the legs), green-ring keyline stubs/blobs removed (and the stray ring fragment at 156-188, 1250-1295). Upper foot: toe point, cream sole highlight, long sharp heel spike. Lower foot: blue ankle, black shoe with a proper heel (heel block + cream highlight strip), toe runs to the bottom edge (Y 2006) to tuck under the wood-lobe keyline. Red/blue trapped 0.013in under black; hidden area layer updated (hand, elbow, legs). Nodes black 1129 -> 942, red 337 -> 275, blue 180 -> 163. Old version: _previous/LC red girl (before hand-elbow-feet fix).svg.
- Note: compared with the whole-board photo, this girl's lower legs/feet sit ~0.06in right and ~0.09in high (the close-up she was traced from has perspective); the upper body matches. Not changed yet - worth a placement/warp check before cutting.
- 2026-10-17: pieces now live in stencils/. build_playfield.py looks for each file named in playfield placements.csv first in the main folder, then in stencils/ (PIECE_DIRS near the top), so the CSV keeps plain file names. placements.csv, controls, the master, background and cream preview stay in the main folder. Master regenerated: 31 of 31 included pieces placed, none missing. Old script: _previous/build_playfield (before stencils folder).py.
