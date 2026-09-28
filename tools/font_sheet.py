"""Render numbered glyph sheets from the original 16x16 2bpp font (glyph n)."""
import sys
from PIL import Image, ImageDraw

FONT_BASE = 0x20000


def glyph_offset(n):
    return FONT_BASE + (n // 8) * 0x200 + (n % 8) * 0x20


def glyph_pixels(rom, n):
    o = glyph_offset(n)
    px = [[0] * 16 for _ in range(16)]
    for ty in range(2):
        for tx in range(2):
            t = o + ty * 0x100 + tx * 0x10
            for y in range(8):
                p0, p1 = rom[t + y * 2], rom[t + y * 2 + 1]
                for x in range(8):
                    px[ty * 8 + y][tx * 8 + x] = ((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)
    return px


def sheet(rom, start, count, out, cols=16, scale=3):
    cw, ch = 16 * scale + 6, 16 * scale + 16
    rows = (count + cols - 1) // cols
    im = Image.new('RGB', (cols * cw, rows * ch), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    shade = [(255, 255, 255), (170, 170, 170), (90, 90, 90), (0, 0, 0)]
    for i in range(count):
        n = start + i
        gx, gy = (i % cols) * cw, (i // cols) * ch
        dr.text((gx + 2, gy), str(n), fill=(200, 0, 0))
        px = glyph_pixels(rom, n)
        for y in range(16):
            for x in range(16):
                if px[y][x]:
                    dr.rectangle([gx + 3 + x * scale, gy + 12 + y * scale,
                                  gx + 3 + x * scale + scale - 1, gy + 12 + y * scale + scale - 1], fill=shade[px[y][x]])
    im.save(out)


if __name__ == '__main__':
    rom = open(sys.argv[1], 'rb').read()
    sheet(rom, int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
