"""Report which BG layer / tile draws the screen pixel (x, y) (mode 1, no scroll assumed unless given)."""
import struct


def layer_info(emu):
    f = emu.fillram()
    info = {}
    for n, (sc, nba_shift) in enumerate(((0x2107, 0), (0x2108, 4), (0x2109, 0))):
        base = (f[sc] >> 2) << 10
        size = f[sc] & 3
        nba = f[0x210B] if n < 2 else f[0x210C]
        cbase = ((nba >> nba_shift) & 0xF) << 12
        info['BG%d' % (n + 1)] = (base, size, cbase, 4 if n < 2 else 2)
    return info


def tile_at(emu, layer, x, y, scroll=(0, 0)):
    v = emu.vram()
    base, size, cbase, bpp = layer_info(emu)[layer]
    X, Y = (x + scroll[0]) & 0x1FF, (y + scroll[1]) & 0x1FF
    cx, cy = X // 8, Y // 8
    addr = base
    if cx >= 32 and size & 1:
        addr += 0x400
    if cy >= 32 and size & 2:
        addr += 0x400 * (2 if size == 3 else 1)
    w = struct.unpack_from('<H', v, ((addr + (cy % 32) * 32 + (cx % 32)) * 2) & 0xFFFF)[0]
    return w, (cbase + (w & 0x3FF) * 4 * bpp) & 0x7FFF
