import sys, json, gc, time, traceback
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import pytesseract

SRC = "/sessions/kind-amazing-hopper/multiorient/page-1.png"
OUTDIR = "/sessions/kind-amazing-hopper/multiorient"

r = int(sys.argv[1])  # 0, 90, 180, 270

t0 = time.time()
im = Image.open(SRC).convert("L")  # grayscale, lighter memory than RGB
W, H = im.size
print("orig size", W, H, "rotation", r, flush=True)

if r == 0:
    rim = im
elif r == 90:
    rim = im.transpose(Image.ROTATE_90)
elif r == 180:
    rim = im.transpose(Image.ROTATE_180)
elif r == 270:
    rim = im.transpose(Image.ROTATE_270)
else:
    raise ValueError(r)

rw, rh = rim.size
print("rotated size", rw, rh, "elapsed", time.time()-t0, flush=True)

try:
    data = pytesseract.image_to_data(rim, output_type=pytesseract.Output.DICT, config="--psm 11", timeout=140)
except Exception as e:
    print("TESSERACT ERROR:", e, flush=True)
    traceback.print_exc()
    data = {"text": []}

print("tesseract done, elapsed", time.time()-t0, "words raw:", len(data["text"]), flush=True)

words = []
n = len(data["text"])
for i in range(n):
    txt = data["text"][i].strip()
    try:
        conf = float(data["conf"][i])
    except Exception:
        conf = -1
    if not txt or conf < 55 or len(txt) < 2:
        continue
    x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
    rx0, ry0, rx1, ry1 = x, y, x + w, y + h

    def inv(px, py):
        if r == 0:
            return px, py
        elif r == 90:
            return W - 1 - py, px
        elif r == 180:
            return W - 1 - px, H - 1 - py
        elif r == 270:
            return py, H - 1 - px

    p0 = inv(rx0, ry0)
    p1 = inv(rx1, ry0)
    p2 = inv(rx1, ry1)
    p3 = inv(rx0, ry1)
    xs = [p0[0], p1[0], p2[0], p3[0]]
    ys = [p0[1], p1[1], p2[1], p3[1]]
    words.append({
        "text": txt, "conf": conf, "r": r,
        "x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys),
        "rw": (rx1 - rx0), "rh": (ry1 - ry0),
    })

print("kept", len(words), "of", n, "elapsed", time.time()-t0, flush=True)

with open(f"{OUTDIR}/words_r{r}.json", "w") as f:
    json.dump({"W": W, "H": H, "r": r, "words": words}, f)

print("saved words_r%d.json" % r, flush=True)
