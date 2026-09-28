"""Screen-space editing of a 4bpp BG layer given as (char data, 32x32 tilemap).

compose() -> Layer with an index image (per-pixel color index 0..15) and per-cell
attributes; edits are made on the index image; retile() rebuilds tiles for the
modified cells (deduplicating against existing tiles) and returns new char data
and tilemap bytes.
"""
import struct


def tile_pixels(chars, t, bpp=4):
    b = t * 8 * bpp
    px = []
    for y in range(8):
        row = []
        for x in range(8):
            v = 0
            for p in range(bpp):
                byte = chars[b + (p // 2) * 16 + y * 2 + (p & 1)] if b + 32 <= len(chars) or bpp != 4 else 0
                v |= ((byte >> (7 - x)) & 1) << p
            row.append(v)
        px.append(row)
    return px


def encode_tile(px, bpp=4):
    out = bytearray(8 * bpp)
    for y in range(8):
        for x in range(8):
            v = px[y][x]
            for p in range(bpp):
                if (v >> p) & 1:
                    out[(p // 2) * 16 + y * 2 + (p & 1)] |= 0x80 >> x
    return bytes(out)


class Layer:
    def __init__(self, chars, tilemap, bpp=4, width=32, height=32):
        self.chars = bytearray(chars)
        self.bpp = bpp
        self.w, self.h = width, height
        self.map = [struct.unpack_from('<H', tilemap, i * 2)[0] for i in range(width * height)]
        self.img = [[0] * (width * 8) for _ in range(height * 8)]
        self.touched = set()
        ntiles = len(self.chars) // (8 * bpp)
        for cy in range(height):
            for cx in range(width):
                w = self.map[cy * width + cx]
                t = w & 0x3FF
                px = tile_pixels(self.chars, t, bpp) if t < ntiles else [[0] * 8 for _ in range(8)]
                hf, vf = (w >> 14) & 1, (w >> 15) & 1
                for y in range(8):
                    for x in range(8):
                        sx = 7 - x if hf else x
                        sy = 7 - y if vf else y
                        self.img[cy * 8 + y][cx * 8 + x] = px[sy][sx]

    def pal(self, cx, cy):
        return (self.map[cy * self.w + cx] >> 10) & 7

    def set(self, x, y, v):
        if self.img[y][x] != v:
            self.img[y][x] = v
            self.touched.add((x // 8, y // 8))

    def touch_box(self, x0, y0, x1, y1):
        for cy in range(y0 // 8, (y1 + 7) // 8):
            for cx in range(x0 // 8, (x1 + 7) // 8):
                self.touched.add((cx, cy))

    def retile(self, max_tiles):
        tsz = 8 * self.bpp
        existing = {}
        n = len(self.chars) // tsz
        for t in range(n):
            existing.setdefault(bytes(self.chars[t * tsz:(t + 1) * tsz]), t)
        for (cx, cy) in sorted(self.touched):
            px = [self.img[cy * 8 + y][cx * 8:cx * 8 + 8] for y in range(8)]
            data = encode_tile(px, self.bpp)
            t = existing.get(data)
            if t is None:
                t = len(self.chars) // tsz
                if t >= max_tiles:
                    raise SystemExit('BG layer needs more than %d tiles' % max_tiles)
                self.chars += data
                existing[data] = t
            w = self.map[cy * self.w + cx]
            self.map[cy * self.w + cx] = (w & 0x1C00) | (w & 0x2000) | t
        return bytes(self.chars), b''.join(struct.pack('<H', w) for w in self.map)

    def to_image(self, cgram_words, pal_base=0):
        from PIL import Image
        im = Image.new('RGB', (self.w * 8, self.h * 8))
        px = im.load()
        for y in range(self.h * 8):
            for x in range(self.w * 8):
                v = self.img[y][x]
                c = cgram_words[pal_base + self.pal(x // 8, y // 8) * (1 << self.bpp) + v] if v else cgram_words[0]
                px[x, y] = ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)
        return im


def identity_layer(chars, cols=16, bpp=4):
    """Treat an asset whose tiles form an image cols tiles wide (sprite sheets)."""
    n = len(chars) // (8 * bpp)
    rows = (n + cols - 1) // cols
    tm = b''.join(struct.pack('<H', i if i < n else 0) for i in range(rows * cols))
    L = Layer(chars, tm, bpp, cols, rows)
    L.identity_tiles = n
    return L


def write_back_identity(L):
    tsz = 8 * L.bpp
    out = bytearray(L.chars)
    for t in range(L.identity_tiles):
        cx, cy = t % L.w, t // L.w
        px = [L.img[cy * 8 + y][cx * 8:cx * 8 + 8] for y in range(8)]
        out[t * tsz:(t + 1) * tsz] = encode_tile(px, L.bpp)
    return bytes(out)


def replace_text(L, box, text, font, ink, text_idx, period=16, shadow=None, dy=0, align='center'):
    """Erase pixels with indices in text_idx inside box (x0, y0, x1, y1) by copying the
    periodic background texture, then draw `text` with color index `ink`."""
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = box
    mask = [[L.img[y][x] in text_idx for x in range(x0, x1)] for y in range(y0, y1)]
    for y in range(y0, y1):
        for x in range(x0, x1):
            if not mask[y - y0][x - x0]:
                continue
            for k in range(1, 16):
                for sx in (x + k * period, x - k * period):
                    if x0 <= sx < x1 and not mask[y - y0][sx - x0]:
                        L.set(x, y, L.img[y][sx])
                        break
                else:
                    continue
                break
    w = int(font.getlength(text))
    im = Image.new('1', (w + 2, 18), 0)
    dr = ImageDraw.Draw(im)
    dr.fontmode = '1'
    dr.text((0, 0), text, font=font, fill=1)
    tx = x0 + ((x1 - x0) - w) // 2 if align == 'center' else x0
    ty = y0 + ((y1 - y0) - 14) // 2 - 1 + dy
    px = im.load()
    for yy in range(18):
        for xx in range(w + 2):
            if px[xx, yy]:
                if shadow is not None:
                    sx, sy = tx + xx + 1, ty + yy + 1
                    if x0 <= sx < x1 and y0 <= sy < y1 and not px[min(xx + 1, w + 1), min(yy + 1, 17)]:
                        L.set(sx, sy, shadow)
    for yy in range(18):
        for xx in range(w + 2):
            if px[xx, yy]:
                X, Y = tx + xx, ty + yy
                if x0 <= X < x1 and y0 <= Y < y1:
                    L.set(X, Y, ink)
    L.touch_box(x0, y0, x1, y1)


def retile_shared(layers, max_tiles):
    """Retile several layers that share one char set (layers[0].chars).

    Tiles referenced only by touched cells become reusable; new tiles fill those
    slots first and are appended only when needed. Returns (chars, [tilemaps]).
    """
    bpp = layers[0].bpp
    tsz = 8 * bpp
    chars = bytearray(layers[0].chars)
    n = len(chars) // tsz
    used_untouched, used_touched = set(), set()
    for L in layers:
        for cy in range(L.h):
            for cx in range(L.w):
                t = L.map[cy * L.w + cx] & 0x3FF
                (used_touched if (cx, cy) in L.touched else used_untouched).add(t)
    free = sorted(t for t in used_touched - used_untouched if 0 < t < n)
    existing = {}
    for t in range(n):
        if t not in free:
            existing.setdefault(bytes(chars[t * tsz:(t + 1) * tsz]), t)
    maps = []
    for L in layers:
        for (cx, cy) in sorted(L.touched):
            px = [L.img[cy * 8 + y][cx * 8:cx * 8 + 8] for y in range(8)]
            data = encode_tile(px, bpp)
            t = existing.get(data)
            if t is None:
                if free:
                    t = free.pop(0)
                    chars[t * tsz:(t + 1) * tsz] = data
                else:
                    t = len(chars) // tsz
                    if t >= max_tiles:
                        raise SystemExit('shared layer needs more than %d tiles' % max_tiles)
                    chars += data
                existing[data] = t
            w = L.map[cy * L.w + cx]
            L.map[cy * L.w + cx] = (w & 0xFC00) & ~0xC000 | t
        maps.append(b''.join(struct.pack('<H', w) for w in L.map))
    return bytes(chars), maps


def writeback_inplace(L, tile_base=0):
    """Encode touched cells back into the tiles they already reference (no tilemap change).
    Fails if one tile is referenced by cells that now differ."""
    tsz = 8 * L.bpp
    out = bytearray(L.chars)
    seen = {}
    for (cx, cy) in sorted(L.touched):
        t = (L.map[cy * L.w + cx] & 0x3FF) - tile_base
        w = L.map[cy * L.w + cx]
        px = [L.img[cy * 8 + y][cx * 8:cx * 8 + 8] for y in range(8)]
        hf, vf = (w >> 14) & 1, (w >> 15) & 1
        if hf:
            px = [r[::-1] for r in px]
        if vf:
            px = px[::-1]
        data = encode_tile(px, L.bpp)
        if not (0 <= t < len(out) // tsz):
            raise SystemExit('touched cell (%d,%d) references tile %X outside the asset' % (cx, cy, t + tile_base))
        if t in seen and seen[t] != data:
            raise SystemExit('tile %X shared by cells with different content' % (t + tile_base))
        seen[t] = data
        out[t * tsz:(t + 1) * tsz] = data
    return bytes(out)
