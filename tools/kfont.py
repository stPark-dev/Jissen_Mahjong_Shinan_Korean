"""Render Korean glyphs to the game's 16x16 2bpp (4-level) font format."""
from PIL import Image, ImageDraw, ImageFont

LEVELS = (0.22, 0.48, 0.74)  # grayscale thresholds -> 1, 2, 3


def render_levels(ch, font_path, size, index=0, dx=0, dy=0):
    """Return a 16x16 list of 0..3 values for one character."""
    big = 4
    font = ImageFont.truetype(font_path, size * big, index=index)
    im = Image.new('L', (16 * big, 16 * big), 0)
    dr = ImageDraw.Draw(im)
    l, t, r, b = dr.textbbox((0, 0), ch, font=font)
    x = (16 * big - (r - l)) // 2 - l + dx * big
    y = (16 * big - (b - t)) // 2 - t + dy * big
    dr.text((x, y), ch, fill=255, font=font)
    im = im.resize((16, 16), Image.BOX)
    px = im.load()
    out = []
    for yy in range(16):
        row = []
        for xx in range(16):
            v = px[xx, yy] / 255
            row.append(3 if v >= LEVELS[2] else 2 if v >= LEVELS[1] else 1 if v >= LEVELS[0] else 0)
        out.append(row)
    return out


def encode_glyph(levels):
    """16x16 levels -> 4 SNES 2bpp tiles (TL, TR, BL, BR), 16 bytes each."""
    tiles = []
    for ty in range(2):
        for tx in range(2):
            t = bytearray()
            for y in range(8):
                p0 = p1 = 0
                for x in range(8):
                    v = levels[ty * 8 + y][tx * 8 + x]
                    p0 |= (v & 1) << (7 - x)
                    p1 |= ((v >> 1) & 1) << (7 - x)
                t += bytes((p0, p1))
            tiles.append(bytes(t))
    return tiles


def write_glyph(rom, base, n, levels):
    """Store glyph n in the 8-glyphs-per-row, 16-tiles-per-row VRAM-style layout."""
    o = base + (n // 8) * 0x200 + (n % 8) * 0x20
    tl, tr, bl, br = encode_glyph(levels)
    rom[o:o + 16] = tl
    rom[o + 16:o + 32] = tr
    rom[o + 0x100:o + 0x110] = bl
    rom[o + 0x110:o + 0x120] = br


def render_pixel(ch, font_path, size, dx=0, dy=0, shadow=False, align_bbox=False):
    """Render a bitmap-design font 1:1 without antialiasing; optional 1px shadow as level 1."""
    font = ImageFont.truetype(font_path, size)
    im = Image.new('1', (16, 16), 0)
    dr = ImageDraw.Draw(im)
    dr.fontmode = '1'
    if align_bbox:
        l, t, r, b = dr.textbbox((0, 0), ch, font=font)
        x = (16 - (r - l)) // 2 - l + dx
        y = (16 - (b - t)) // 2 - t + dy
    else:
        x, y = dx, dy
    dr.text((x, y), ch, fill=1, font=font)
    px = im.load()
    out = [[3 if px[xx, yy] else 0 for xx in range(16)] for yy in range(16)]
    if shadow:
        for yy in range(15, -1, -1):
            for xx in range(15, -1, -1):
                if out[yy][xx] == 0 and xx > 0 and yy > 0 and out[yy - 1][xx - 1] == 3:
                    out[yy][xx] = 1
    return out
