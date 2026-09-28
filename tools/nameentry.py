"""Hangul name-entry grid (D-003): code table at $03:A6A2 and BG3 grid graphics
(chars #21, page tilemaps #22/#23)."""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from bgedit import Layer, encode_tile  # noqa: E402
from lz import entry_offset, decompress  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_TABLE = 0x1A6A2          # file offset of $03:A6A2: 2 pages x 6 rows x 16 words
CHARS, PAGES = 21, (22, 23)
GRID_X, GRID_Y = 8, 120       # pixel origin of cell (0, 0) in the BG3 map
ROW_CELLS = [15, 15, 15, 15, 15, 10]
MAX_TILES = 768               # BG3 chars $5000-$67FF (2bpp)


def syllables():
    lines = [l.strip() for l in open(os.path.join(ROOT, 'data', 'name_entry.txt'), encoding='utf-8')
             if l.strip() and not l.startswith('#')]
    s = ''.join(lines)
    if len(s) != 2 * sum(ROW_CELLS):
        raise SystemExit('name_entry.txt must list %d syllables' % (2 * sum(ROW_CELLS)))
    return s


def pages():
    s = syllables()
    per = sum(ROW_CELLS)
    out = []
    for p in range(2):
        cells = {}
        k = p * per
        for r, n in enumerate(ROW_CELLS):
            for c in range(n):
                cells[(r, c)] = s[k]
                k += 1
        out.append(cells)
    return out


def code_table(cmap, code_of):
    data = bytearray()
    for cells in pages():
        for r in range(6):
            for c in range(16):
                ch = cells.get((r, c))
                data += struct.pack('<H', code_of(cmap[ch]) if ch else 0)
    return bytes(data)


def graphics(rom, font):
    from PIL import Image, ImageDraw
    chars = decompress(rom, entry_offset(rom, CHARS))[0]
    layers = []
    for p, idx in enumerate(PAGES):
        L = Layer(chars, decompress(rom, entry_offset(rom, idx))[0], bpp=2)
        for (r, c), ch in pages()[p].items():
            x0, y0 = GRID_X + c * 16, GRID_Y + r * 16
            for y in range(y0, y0 + 16):
                for x in range(x0, x0 + 16):
                    L.set(x, y, 0)
            im = Image.new('1', (16, 16), 0)
            dr = ImageDraw.Draw(im)
            dr.fontmode = '1'
            dr.text((0, 0), ch, font=font, fill=1)
            px = im.load()
            for y in range(16):
                for x in range(16):
                    if px[x, y]:
                        L.set(x0 + x, y0 + y, 3)
            L.touch_box(x0, y0, x0 + 16, y0 + 16)
        layers.append(L)
    # rebuild a compact char set shared by both pages: tile 0 stays blank
    tiles = {bytes(16): 0}
    new_chars = bytearray(16)
    maps = []
    for L in layers:
        words = []
        for cy in range(L.h):
            for cx in range(L.w):
                w = L.map[cy * L.w + cx]
                px = [L.img[cy * 8 + y][cx * 8:cx * 8 + 8] for y in range(8)]
                data = encode_tile(px, 2)
                t = tiles.get(data)
                if t is None:
                    t = len(new_chars) // 16
                    tiles[data] = t
                    new_chars += data
                words.append((w & 0x3C00) | (w & 0x2000) | t)
        maps.append(b''.join(struct.pack('<H', w) for w in words))
    if len(new_chars) // 16 > MAX_TILES:
        raise SystemExit('name entry grid needs %d tiles > %d' % (len(new_chars) // 16, MAX_TILES))
    return {CHARS: bytes(new_chars), PAGES[0]: maps[0], PAGES[1]: maps[1]}, len(new_chars) // 16
