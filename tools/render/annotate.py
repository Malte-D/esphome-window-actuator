"""Draw callout labels onto a render from stills.py.

    python annotate.py build/stills/handle_exploded.png docs/images/handle-exploded.png

The label positions come from the .json next to the render. Its "layout" decides where
the texts go: "sides" (default, two columns left and right) or "topbottom" (one row
above and one below the picture, for wide exploded views).
"""

import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/SFNS.ttf"
LINE = (130, 130, 130, 255)
DOT = (228, 87, 46, 255)
TEXT = (34, 34, 34, 255)


SS = 3   # lines, dots and texts are drawn at 3x and scaled down, so diagonal lines are smooth


class Pen:
    """Overlay drawn at SS times the resolution of the canvas."""

    def __init__(self, size):
        self.img = Image.new("RGBA", (size[0] * SS, size[1] * SS), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.img)
        self.fonts = {}

    def line(self, pts, width=2):
        self.draw.line([(x * SS, y * SS) for x, y in pts], fill=LINE, width=width * SS, joint="curve")

    def dot(self, x, y, r=6):
        self.draw.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=DOT)

    def text(self, xy, text, font, anchor):
        big = self.fonts.setdefault(font.size, ImageFont.truetype(FONT, font.size * SS))
        self.draw.text((xy[0] * SS, xy[1] * SS), text, font=big, fill=TEXT, anchor=anchor)

    def onto(self, canvas):
        small = self.img.convert("RGBa").resize(canvas.size, Image.LANCZOS).convert("RGBA")
        canvas.alpha_composite(small)
        return canvas


def sides(img, labels, font, margin=360):
    w0, h = img.size
    w = w0 + 2 * margin
    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    canvas.alpha_composite(img, (margin, 0))
    draw = ImageDraw.Draw(canvas)
    pen = Pen(canvas.size)
    line_h = int(font.size * 1.6)
    pad = 40
    groups = {"left": [], "right": []}
    for lab in labels:
        lab = dict(lab, x=lab["x"] + margin)
        groups["left" if lab["x"] < w / 2 else "right"].append(lab)
    for side, labs in groups.items():
        if not labs:
            continue
        labs.sort(key=lambda l: l["y"])
        # keep the order of the anchors, spread the text rows so they do not overlap
        for i, lab in enumerate(labs):
            lab["ty"] = max(lab["y"], labs[i - 1]["ty"] + line_h if i else pad)
        overflow = labs[-1]["ty"] - (h - pad)
        if overflow > 0:
            for lab in labs:
                lab["ty"] -= overflow
            for i in range(1, len(labs)):
                labs[i]["ty"] = max(labs[i]["ty"], labs[i - 1]["ty"] + line_h)
        for lab in labs:
            tw = draw.textlength(lab["text"], font=font)
            if side == "left":
                tx, elbow = pad, pad + tw + 14
            else:
                tx, elbow = w - pad - tw, w - pad - tw - 14
            ty = lab["ty"]
            knee = max(elbow, margin - 20) if side == "left" else min(elbow, w - margin + 20)
            pen.line([(elbow, ty), (knee, ty), (lab["x"], lab["y"])])
            pen.dot(lab["x"], lab["y"])
            pen.text((tx, ty), lab["text"], font, "lm")
    return pen.onto(canvas)


def wrap(draw, text, font, max_w):
    # keep counts with their part ("2× M3×10") on one line
    words, lines = text.replace("× ", "×\u00a0").split(" "), []
    for word in words:
        if lines and draw.textlength(lines[-1] + " " + word, font=font) <= max_w:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


def topbottom(img, labels, font, max_w=220, gap=22, pad=30):
    # crop the empty space above and below the parts
    bbox = img.getchannel("A").getbbox() or (0, 0, *img.size)
    top_crop = max(0, bbox[1] - 50)
    img = img.crop((0, top_crop, img.width, min(img.height, bbox[3] + 50)))
    labels = [dict(l, y=l["y"] - top_crop) for l in labels]
    w, h0 = img.size
    measure = ImageDraw.Draw(img)
    line_h = int(font.size * 1.3)
    for lab in labels:
        lab["lines"] = wrap(measure, lab["text"], font, max_w)
        lab["w"] = max(measure.textlength(t, font=font) for t in lab["lines"])
    # the upper half of the anchors gets its text above the picture, the rest below
    labels.sort(key=lambda l: l["y"])
    half = (len(labels) + 1) // 2
    rows = {"top": labels[:half], "bottom": labels[half:]}
    band = {k: max([len(l["lines"]) for l in v] or [0]) * line_h + pad + 30 for k, v in rows.items()}
    h = band["top"] + h0 + band["bottom"]
    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    canvas.alpha_composite(img, (0, band["top"]))
    pen = Pen(canvas.size)
    for side, labs in rows.items():
        labs.sort(key=lambda l: l["x"])
        # texts centred over their anchors; overlapping neighbours are pushed apart equally
        for lab in labs:
            lab["left"] = lab["x"] - lab["w"] / 2
        for _ in range(500):
            moved = False
            for a, b in zip(labs, labs[1:]):
                overlap = a["left"] + a["w"] + gap - b["left"]
                if overlap > 0.5:
                    a["left"] -= overlap / 2
                    b["left"] += overlap / 2
                    moved = True
            if labs:
                labs[0]["left"] = max(labs[0]["left"], pad)
                labs[-1]["left"] = min(labs[-1]["left"], w - pad - labs[-1]["w"])
            if not moved:
                break
        for lab in labs:
            ax, ay = lab["x"], lab["y"] + band["top"]
            cx = lab["left"] + lab["w"] / 2
            n = len(lab["lines"])
            if side == "top":
                ty0 = band["top"] - 30 - n * line_h
                start, knee = (cx, band["top"] - 22), (cx, band["top"] + 10)
            else:
                ty0 = band["top"] + h0 + 30
                start, knee = (cx, band["top"] + h0 + 22), (cx, band["top"] + h0 - 10)
            pen.line([start, knee, (ax, ay)])
            pen.dot(ax, ay)
            for j, t in enumerate(lab["lines"]):
                pen.text((cx, ty0 + j * line_h), t, font, "ma")
    return pen.onto(canvas)


def main(src, dst, font_size=27):
    meta = json.load(open(os.path.splitext(src)[0] + ".json"))
    img = Image.open(src).convert("RGBA")
    font = ImageFont.truetype(FONT, font_size)
    layout = meta.get("layout", "sides")
    canvas = topbottom(img, meta["labels"], font) if layout == "topbottom" else sides(img, meta["labels"], font)
    canvas.convert("RGB").save(dst, optimize=True)
    print("wrote", dst)


if __name__ == "__main__":
    main(*sys.argv[1:3])
