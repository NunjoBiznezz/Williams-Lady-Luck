import json, time
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
from reportlab.pdfgen import canvas as canvaslib
from reportlab.lib.utils import ImageReader

OUTDIR = "/sessions/kind-amazing-hopper/multiorient"
DPI = 300

t0 = time.time()

all_words = []
W = H = None
for r in (0, 90, 180, 270):
    with open(f"{OUTDIR}/words_r{r}.json") as f:
        d = json.load(f)
    W, H = d["W"], d["H"]
    all_words.extend(d["words"])

print("total candidate words:", len(all_words))

# sort by confidence desc for greedy NMS-style de-dup
all_words.sort(key=lambda w: -w["conf"])

def iou(a, b):
    ax0, ay0, ax1, ay1 = a["x0"], a["y0"], a["x1"], a["y1"]
    bx0, by0, bx1, by1 = b["x0"], b["y0"], b["x1"], b["y1"]
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (ax1 - ax0) * (ay1 - ay0)
    area_b = (bx1 - bx0) * (by1 - by0)
    return inter / min(area_a, area_b)

accepted = []
for w in all_words:
    dup = False
    for a in accepted:
        if iou(w, a) > 0.25:
            dup = True
            break
    if not dup:
        accepted.append(w)

print("accepted after de-dup:", len(accepted), "elapsed", time.time() - t0)

# prepare background jpeg
print("converting background image...", flush=True)
im = Image.open(f"{OUTDIR}/page-1.png").convert("RGB")
bg_path = f"{OUTDIR}/background.jpg"
im.save(bg_path, "JPEG", quality=82)
print("background saved, elapsed", time.time() - t0, flush=True)

page_w_pt = W / DPI * 72.0
page_h_pt = H / DPI * 72.0
print("page size pt:", page_w_pt, page_h_pt)

c = canvaslib.Canvas(f"{OUTDIR}/final.pdf", pagesize=(page_w_pt, page_h_pt))
c.setTitle("Williams 1973 Gulfstream Schematic Diagram")
c.drawImage(ImageReader(bg_path), 0, 0, width=page_w_pt, height=page_h_pt)

ANGLE = {0: 0, 90: 270, 180: 180, 270: 90}
ANCHOR = {
    0: lambda w: (w["x0"], w["y1"]),
    90: lambda w: (w["x0"], w["y0"]),
    180: lambda w: (w["x1"], w["y0"]),
    270: lambda w: (w["x1"], w["y1"]),
}

placed = 0
for w in accepted:
    text = w["text"]
    r = w["r"]
    px, py = ANCHOR[r](w)
    x_pt = px / DPI * 72.0
    y_pt = page_h_pt - (py / DPI * 72.0)
    fontsize = max(3.0, (w["rh"] / DPI * 72.0) * 0.85)
    target_width_pt = (w["rw"] / DPI * 72.0)

    c.saveState()
    c.translate(x_pt, y_pt)
    c.rotate(ANGLE[r])
    try:
        natural_width = c.stringWidth(text, "Helvetica", fontsize)
    except Exception:
        natural_width = 0
    scale = 100.0
    if natural_width > 0.01:
        scale = 100.0 * target_width_pt / natural_width
        scale = max(20.0, min(400.0, scale))

    to = c.beginText(0, 0)
    to.setTextRenderMode(3)  # invisible
    to.setFont("Helvetica", fontsize)
    to.setHorizScale(scale)
    to.textOut(text)
    c.drawText(to)
    c.restoreState()
    placed += 1

c.showPage()
c.save()
print("placed", placed, "words. Total elapsed", time.time() - t0)
print("DONE")
