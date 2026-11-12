#!/usr/bin/env python3
"""make_icon.py - draws the program icon (a hex nut on a dark tile; own drawing, no game art).
Writes icon.ico (for the .exe) and icon.png (64 px, for the window).  Needs Pillow."""
import math, os, sys
from PIL import Image, ImageDraw

S = 1024; DARK, YELLOW = (19, 21, 24, 255), (255, 233, 0, 255)
im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.rounded_rectangle((32, 32, S - 32, S - 32), radius=190, fill=DARK)
c = S / 2; r = 330
d.polygon([(c + r * math.cos(math.radians(a)), c + r * math.sin(math.radians(a))) for a in range(0, 360, 60)], fill=YELLOW)
d.ellipse((c - 140, c - 140, c + 140, c + 140), fill=DARK)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
im.save(os.path.join(out, 'icon.ico'), sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
im.resize((64, 64), Image.LANCZOS).save(os.path.join(out, 'icon.png'))
