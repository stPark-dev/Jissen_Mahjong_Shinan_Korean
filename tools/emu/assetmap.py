"""Find which decompressed LZ assets are resident in VRAM (by 32-byte block matching)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from lz import entry_count, entry_offset, decompress


def all_assets(rom):
    out = {}
    for i in range(entry_count(rom) - 1):
        out[i] = decompress(rom, entry_offset(rom, i))[0]
    return out


def resident(vram, assets, block=32, min_hits=4):
    idx = {}
    for w in range(0, len(vram) - block + 1, 16):
        b = vram[w:w + block]
        if b.count(0) == block:
            continue
        idx.setdefault(b, []).append(w // 2)
    res = []
    for i, d in assets.items():
        hits = []
        for o in range(0, len(d) - block + 1, block):
            b = d[o:o + block]
            if b.count(0) >= block - 2:
                continue
            if b in idx:
                hits.append((o, idx[b][0]))
        if len(hits) >= min_hits:
            res.append((i, len(d), len(hits), hits[0]))
    return res
