#!/usr/bin/env python3
"""compose_parts_sheet.py - lays render_parts_sheet.py's cells into vanilla_parts_sheet.png with text labels (Pillow).
  ~/upy/bin/python -I compose_parts_sheet.py [cells.json out.png]"""
import json, os, sys, textwrap
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
CJ = sys.argv[1] if len(sys.argv) > 2 else os.path.join(HERE, "_cells", "cells.json")
OUTP = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "vanilla_parts_sheet.png")
d = json.load(open(CJ))
cells, labels = d["cells"], d["labels"]
W, H, LH, COLS = 500, 560, 70, 5
rows = (len(cells) + COLS - 1) // COLS
sheet = Image.new("RGB", (W * COLS, (H + LH) * rows), (12, 12, 14))
try:
    font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 17)
except Exception:
    font = ImageFont.load_default()
dr = ImageDraw.Draw(sheet)
for i, (c, l) in enumerate(zip(cells, labels)):
    x, y = (i % COLS) * W, (i // COLS) * (H + LH)
    sheet.paste(Image.open(c).convert("RGB"), (x, y))
    dr.text((x + 8, y + H + 4), "\n".join(textwrap.wrap(f"{i + 1}. {l}", 52)[:3]), fill=(225, 225, 225), font=font)
sheet.save(OUTP)
print("sheet", sheet.size)
