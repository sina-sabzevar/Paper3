# -*- coding: utf-8 -*-
"""Cut the icons out of the prepaid credit slide so this deck can use the
same ones.

That slide is a single flat bitmap, so the icons are pixels, not shapes.
Each one is lifted with an alpha channel built from its distance to the
local background, which drops the navy or the pale-blue medallion behind
it and leaves the glyph alone on any ground.

    python3 tools/extract_ref_icons.py <reference.pptx>
"""
import os, sys, zipfile, io
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(os.path.dirname(HERE), "assets", "icons")

# name, box, which way the glyph reads against its ground
BOXES = [("users",   1460, 429, 1499, 469, "light"),
         ("people",  1185, 429, 1225, 469, "light"),
         ("bag",      925, 429,  958, 467, "light"),
         ("percent",  712, 432,  751, 471, "light"),
         ("coins",    526, 429,  563, 466, "light"),
         ("repeat",   338, 429,  374, 469, "light"),
         ("calc",     132, 430,  163, 467, "light"),
         ("net",      603, 338,  658, 400, "light"),
         ("screen",  1566, 148, 1628, 210, "dark"),
         ("brain",   1050, 146, 1111, 207, "dark"),
         ("card",     463, 177,  533, 243, "dark"),
         ("person",  1599, 533, 1623, 562, "dark")]


def cut(im, x0, y0, x1, y1, polarity, scale=4):
    sub = im[y0:y1, x0:x1].astype(float)
    h, w, _ = sub.shape
    edge = np.concatenate([sub[0], sub[-1], sub[:, 0], sub[:, -1]])
    bg = np.median(edge, axis=0)
    d = np.linalg.norm(sub - bg, axis=2)
    # the glyph colour: the pixels furthest from the ground
    fg = sub[d >= np.percentile(d, 99.3)].mean(axis=0)
    span = np.linalg.norm(fg - bg) or 1.0
    a = np.clip(d / span, 0, 1)
    a = np.clip((a - 0.10) / 0.80, 0, 1)         # clean the halo off the edges
    rgb = np.broadcast_to(fg, sub.shape).copy()
    out = np.dstack([rgb, a * 255]).astype(np.uint8)
    img = Image.fromarray(out, "RGBA")
    return img.resize((w * scale, h * scale), Image.LANCZOS)


def main():
    src = sys.argv[1]
    with zipfile.ZipFile(src) as z:
        name = [n for n in z.namelist() if n.startswith("ppt/media/")][0]
        im = np.array(Image.open(io.BytesIO(z.read(name))).convert("RGB"))
    os.makedirs(DEST, exist_ok=True)
    # each glyph is kept in its own colour and recoloured white and blue, so
    # the same icon can sit on a navy header and on a pale card
    for nm, x0, y0, x1, y1, pol in BOXES:
        g = cut(im, x0, y0, x1, y1, pol)
        g.save(os.path.join(DEST, nm + ".png"))
        a = np.array(g)
        for suffix, rgb in (("_w", (255, 255, 255)), ("_b", (0x0D, 0x67, 0xC1))):
            b = a.copy(); b[:, :, 0:3] = rgb
            Image.fromarray(b, "RGBA").save(os.path.join(DEST, nm + suffix + ".png"))
        print("wrote", nm, "(+ _w, _b)")


if __name__ == "__main__":
    main()
