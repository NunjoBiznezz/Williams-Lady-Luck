import sys, json
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import pytesseract

SRC = "/sessions/kind-amazing-hopper/multiorient/page-1.png"
DPI = 300

im = Image.open(SRC).convert("RGB")
W, H = im.size
print("orig size", W, H)

rotations = {
    0: im,
    90: im.transpose(Image.ROTATE_90),
    180: im.transpose(Image.ROTATE_180),
    270: im.transpose(Image.ROTATE_270),
}

all_words = []  # each: dict(text, conf, r, x0,y0,x1,y1 in ORIGINAL 0-deg pixel space, orientation r)

for r, rim in rotations.items():
    rw, rh = rim.size
    print("running tesseract on rotation", r, "size", rw, rh)
    data = pytesseract.image_to_data(rim, output_type=pytesseract.Output.DICT, config="--psm 11")
    n = len(data["text"])
    kept = 0
    for i in range(n):
        txt = data["text"][i].strip()
        try:
            conf = float(data["conf"][i])
        except Exception:
            conf = -1
        if not txt or conf < 55 or len(txt) < 2:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        # corners in rotated-image pixel space
        rx0, ry0, rx1, ry1 = x, y, x + w, y + h
        # map corners back to original 0-degree pixel space using inverse formulas
        def inv(px, py):
            if r == 0:
                return px, py
            elif r == 90:
                # forward: x'=y, y'=W-1-x  => inverse: y=x', x=W-1-y'
                return W - 1 - py, px
            elif r == 180:
                return W - 1 - px, H - 1 - py
            elif r == 270:
                # forward: x'=H-1-y, y'=x => inverse: y=H-1-x', x=y'
                return py, H - 1 - px
        p0 = inv(rx0, ry0)
        p1 = inv(rx1, ry0)
        p2 = inv(rx1, ry1)
        p3 = inv(rx0, ry1)
        xs = [p0[0], p1[0], p2[0], p3[0]]
        ys = [p0[1], p1[1], p2[1], p3[1]]
        ox0, ox1 = min(xs), max(xs)
        oy0, oy1 = min(ys), max(ys)
        all_words.append({
            "text": txt, "conf": conf, "r": r,
            "x0": ox0, "y0": oy0, "x1": ox1, "y1": oy1,
            "rw": (rx1 - rx0), "rh": (ry1 - ry0),
        })
        kept += 1
    print("  kept", kept, "of", n)

print("total words kept:", len(all_words))
with open("/sessions/kind-amazing-hopper/multiorient/words.json", "w") as f:
    json.dump({"W": W, "H": H, "dpi": DPI, "words": all_words}, f)
print("done")
