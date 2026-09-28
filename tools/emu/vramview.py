"""Render VRAM as 2bpp/4bpp tile sheets (grayscale) for graphics-text cataloging."""
from PIL import Image


def vram_sheet(vram, word_start, word_len, bpp, out, cols=32, scale=2):
    data = vram[word_start * 2:(word_start + word_len) * 2]
    tsz = 8 * bpp
    n = len(data) // tsz
    rows = (n + cols - 1) // cols
    im = Image.new('L', (cols * 8, rows * 8))
    px = im.load()
    mx = (1 << bpp) - 1
    for t in range(n):
        b = t * tsz
        for y in range(8):
            for x in range(8):
                v = 0
                for p in range(bpp):
                    byte = data[b + (p // 2) * 16 + y * 2 + (p & 1)]
                    v |= ((byte >> (7 - x)) & 1) << p
                px[(t % cols) * 8 + x, (t // cols) * 8 + y] = v * 255 // mx
    im.resize((im.width * scale, im.height * scale), Image.NEAREST).save(out)
