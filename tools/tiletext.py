"""Decode TilePrint ($00:9A14) word strings with a sheet map (data/sheets/*.tsv)."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHAPES = {0x0: '1', 0x1: '8x16', 0x4: '16x8', 0x5: '16', 0x8: 'dn'}


def load_sheet(name):
    m = {}
    for line in open(os.path.join(ROOT, 'data', 'sheets', name + '.tsv'), encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        t, ch, shape = line.rstrip('\n').split('\t')[:3]
        m[int(t, 16)] = ch
    return m


def words(rom, off):
    ws = []
    while True:
        w = rom[off] | rom[off + 1] << 8
        off += 2
        if w == 0xFFFF:
            return ws
        ws.append(w)
        if len(ws) > 256:
            raise ValueError('unterminated')


def decode(ws, sheet):
    out = []
    for w in ws:
        if w == 0xFFFE:
            out.append('<BR>')
        elif w == 0xFFFC:
            out.append('<FC>')
        elif w == 0xFFFD:
            out.append('<FD>')
        else:
            shape, tile = w >> 12, w & 0xFFF
            ch = sheet.get(tile)
            out.append(ch if ch and shape in (0x5, 0x1) else '<%04X>' % w)
    return ''.join(out)
