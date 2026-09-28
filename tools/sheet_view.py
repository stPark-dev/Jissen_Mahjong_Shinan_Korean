"""Numbered view of a 2bpp glyph sheet laid out as 16 tiles per row (glyph = t, t+1, t+16, t+17)."""
from PIL import Image, ImageDraw


def tile2(data, t):
    b = t * 16
    return [[((data[b + y * 2] >> (7 - x)) & 1) | (((data[b + y * 2 + 1] >> (7 - x)) & 1) << 1) for x in range(8)]
            for y in range(8)]


def sheet(data, out, tiles_total, scale=3):
    rows = tiles_total // 32
    cw = 16 * scale + 8
    ch = 16 * scale + 14
    im = Image.new('RGB', (8 * cw, rows * ch * 1), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    shade = [(255, 255, 255), (150, 150, 150), (80, 80, 80), (0, 0, 0)]
    for r in range(rows):
        for g in range(8):
            t = r * 32 + g * 2
            X, Y = g * cw, r * ch
            dr.text((X + 2, Y), '%03X' % t, fill=(200, 0, 0))
            for q, (dx, dy) in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
                tt = t + dx + dy * 16
                if tt * 16 + 16 > len(data):
                    continue
                px = tile2(data, tt)
                for y in range(8):
                    for x in range(8):
                        if px[y][x]:
                            xx, yy = X + 4 + (dx * 8 + x) * scale, Y + 12 + (dy * 8 + y) * scale
                            dr.rectangle([xx, yy, xx + scale - 1, yy + scale - 1], fill=shade[px[y][x]])
    im.save(out)
