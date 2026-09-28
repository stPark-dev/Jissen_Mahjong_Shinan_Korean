"""Reconstruct the OBJ layer from OAM/VRAM/CGRAM (for analysis and logo replacement)."""
import ctypes as C
from PIL import Image


def oam_bytes(emu):
    return C.string_at(emu.lib.retro_kr_oam(), 544)


def sprites(emu):
    f = emu.fillram()
    obsel = f[0x2101]
    oam = oam_bytes(emu)
    sizes = [(8, 16), (8, 32), (8, 64), (16, 32), (16, 64), (32, 64), (16, 32), (16, 32)][obsel >> 5]
    base = (obsel & 7) << 13          # words
    gap = ((obsel >> 3) & 3) + 1 << 12
    out = []
    for i in range(128):
        x, y, t, a = oam[i * 4:i * 4 + 4]
        hi = (oam[512 + i // 4] >> ((i % 4) * 2)) & 3
        x |= (hi & 1) << 8
        if x >= 256:
            x -= 512
        size = sizes[(hi >> 1) & 1]
        tile = t | ((a & 1) << 8)
        out.append(dict(i=i, x=x, y=y, tile=tile, pal=(a >> 1) & 7, pri=(a >> 4) & 3,
                        hf=(a >> 6) & 1, vf=a >> 7, size=size))
    return out, base, gap


def tile_addr(base, gap, tile):
    w = base + tile * 16
    if tile >= 256:
        w += gap - 256 * 16 + 0  # second table
        w = base + gap + (tile - 256) * 16
    return w & 0x7FFF


def render(emu, path=None, only=None):
    vram = emu.vram()
    cg = emu.cgram()
    spr, base, gap = sprites(emu)
    im = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    px = im.load()
    for s in reversed(spr):
        if only and s['i'] not in only:
            continue
        n = s['size'] // 8
        for ty in range(n):
            for tx in range(n):
                tt = ((s['tile'] & 0x10F) + tx) & 0x10F | ((((s['tile'] >> 4) & 0xF) + ty) & 0xF) << 4 | (s['tile'] & 0x100)
                tt = (s['tile'] & 0x100) | ((((s['tile'] >> 4) + ty) & 0xF) << 4) | ((s['tile'] + tx) & 0xF)
                w = tile_addr(base, gap, tt)
                for y in range(8):
                    for x in range(8):
                        v = 0
                        for p in range(4):
                            byte = vram[(w * 2 + (p // 2) * 16 + y * 2 + (p & 1)) & 0xFFFF]
                            v |= ((byte >> (7 - x)) & 1) << p
                        if not v:
                            continue
                        c = cg[(128 + s['pal'] * 16 + v) * 2] | cg[(128 + s['pal'] * 16 + v) * 2 + 1] << 8
                        rx = tx * 8 + x
                        ry = ty * 8 + y
                        if s['hf']:
                            rx = s['size'] - 1 - rx
                        if s['vf']:
                            ry = s['size'] - 1 - ry
                        X, Y = s['x'] + rx, (s['y'] + ry) & 0xFF
                        if 0 <= X < 256 and Y < 240:
                            px[X, Y] = ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3, 255)
    if path:
        im.save(path)
    return im
