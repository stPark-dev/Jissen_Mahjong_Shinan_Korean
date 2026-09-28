"""Glyph-sheet text (TilePrint) build: Korean glyph allocation per sheet, asset
redraw, LZ recompression/relocation and in-place string re-encoding."""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from check_ko import read_tsv  # noqa: E402
from dis65816 import lorom_to_file  # noqa: E402
from kfont import encode_glyph  # noqa: E402
from lz import TABLE, entry_offset, decompress, compress  # noqa: E402
from tiletext import load_sheet, words  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# sheet -> assets [(lz index, first tile)], tiles kept verbatim, tiles redrawn in place {tile: char}
SHEETS = {
    'game_bg3': {
        'assets': [(106, 0x000), (101, 0x100)],
        'keep': {0x100, 0x18E, 0x1AE, 0x1C0, 0x1C2} | set(range(0x1A0, 0x1AC)),
        'narrow': range(0x1A0, 0x1AC),
        'redraw': {0x1C4: '동', 0x1C6: '남', 0x1C8: '서', 0x1CA: '북'},
        'groups': ['TPG'],
        # During normal play only #101 (tiles 0x100+) is resident; #106 is loaded
        # for the yaku result screen only. Strings shown during play must use
        # glyphs from the resident range.
        'resident_tiles': range(0x100, 0x1DC),
        'resident_ids': {'TPG.%04d' % n for n in list(range(0, 15)) + list(range(82, 99))},
    },
    'config_bg3': {
        'assets': [(40, 0x000)],
        'keep': {0x06A, 0x06C, 0x06E, 0x08A, 0x08C, 0x08E, 0x0A8, 0x0AA, 0x0AC, 0x0AE},  # B G M O N F 1-4
        'redraw': {},
        'groups': ['TPC'],
    },
}
LZ_FREE = [(0xCE000, 0xE8000)]


def token_list(text):
    return re.findall(r'<BR>|<FC>|<FD>|<[0-9A-F]{4}>|\{[^}]+\}|.', text)


class SheetBuild:
    def __init__(self, name, rom):
        self.name = name
        self.spec = SHEETS[name]
        self.jp = load_sheet(name)            # tile -> char
        self.fixed = {}                       # char -> word for kept glyphs
        for t, ch in self.jp.items():
            if t in self.spec['keep']:
                shape = 0x1000 if t in self.spec.get('narrow', ()) else 0x5000
                self.fixed.setdefault(ch, shape | t)
        for t, ch in self.spec['redraw'].items():
            self.fixed[ch] = 0x5000 | t
        self.assets = {}
        for idx, base in self.spec['assets']:
            data, end = decompress(rom, entry_offset(rom, idx))
            self.assets[idx] = (base, bytearray(data), entry_offset(rom, idx), end)
        self.free_slots = [t for t in sorted(self.jp) if t not in self.spec['keep'] and t not in self.spec['redraw']
                           and self._slot_ok(t)]

    def _slot_ok(self, t):
        return all(self._locate(x) is not None for x in (t, t + 1, t + 16, t + 17))

    def _locate(self, tile):
        for idx, (base, data, _, _) in self.assets.items():
            o = (tile - base) * 16
            if 0 <= o and o + 16 <= len(data):
                return idx, o
        return None

    def allocate(self, units):
        """units: [(id, ko)]. Resident-string glyphs go to resident slots first."""
        res_ids = self.spec.get('resident_ids', set())
        res_tiles = self.spec.get('resident_tiles', range(0))
        need_res, need_any = set(), set()
        for uid, t in units:
            for tok in token_list(t):
                if len(tok) == 1 and tok not in self.fixed:
                    (need_res if uid in res_ids else need_any).add(tok)
        need_any -= need_res
        res_slots = [t for t in self.free_slots if t in res_tiles]
        other_slots = [t for t in self.free_slots if t not in res_tiles]
        if len(need_res) > len(res_slots):
            raise SystemExit('sheet %s: %d resident glyphs > %d resident slots' % (self.name, len(need_res), len(res_slots)))
        self.cmap = dict(zip(sorted(need_res), res_slots))
        rest = other_slots + res_slots[len(need_res):]
        if len(need_any) > len(rest):
            raise SystemExit('sheet %s: %d glyphs > %d slots' % (self.name, len(need_res) + len(need_any), len(self.free_slots)))
        self.cmap.update(zip(sorted(need_any), rest))
        return len(self.cmap), len(self.free_slots)

    def encode(self, text, uid):
        out = []
        for tok in token_list(text):
            if tok == '<BR>':
                out.append(0xFFFE)
            elif tok == '<FC>':
                out.append(0xFFFC)
            elif tok == '<FD>':
                out.append(0xFFFD)
            elif tok.startswith('<'):
                out.append(int(tok[1:5], 16))
            elif tok in self.fixed:
                out.append(self.fixed[tok])
            elif tok in self.cmap:
                out.append(0x5000 | self.cmap[tok])
            else:
                raise SystemExit('%s: unmapped %r' % (uid, tok))
        return b''.join(struct.pack('<H', w) for w in out) + b'\xff\xff'

    def draw(self, font):
        from PIL import Image, ImageDraw
        todo = [(t, ch) for ch, t in self.cmap.items()] + list(self.spec['redraw'].items())
        for t, ch in todo:
            im = Image.new('1', (16, 16), 0)
            dr = ImageDraw.Draw(im)
            dr.fontmode = '1'
            x = 0 if font.getlength(ch) >= 16 else (16 - int(font.getlength(ch))) // 2
            dr.text((x, 0), ch, font=font, fill=1)
            px = im.load()
            lv = [[3 if px[xx, yy] else 0 for xx in range(16)] for yy in range(16)]
            tl, tr, bl, br = encode_glyph(lv)
            for tile, data in ((t, tl), (t + 1, tr), (t + 16, bl), (t + 17, br)):
                idx, o = self._locate(tile)
                self.assets[idx][1][o:o + 16] = data


def build_sheets(plan, font, lz_free_state):
    """Apply all sheet groups to the plan. Returns stats."""
    rom = plan.src
    stats = {}
    for name, spec in SHEETS.items():
        sb = SheetBuild(name, rom)
        units = []
        for g in spec['groups']:
            src = {r['id']: r for r in read_tsv(os.path.join(ROOT, 'text', 'jp', g + '.tsv'))}
            ko = {r['id']: r for r in read_tsv(os.path.join(ROOT, 'text', 'ko', g + '.tsv'))}
            for i, s in src.items():
                units.append((i, int(s['addr'], 16), s['jp'], ko[i]['ko']))
        used, cap = sb.allocate([(u[0], u[3]) for u in units])
        for uid, cpu, jp, ko in units:
            off = lorom_to_file(cpu)
            n = 2 * len(words(rom, off)) + 2
            data = sb.encode(ko, uid)
            if len(data) > n:
                raise SystemExit('%s: %d bytes > %d (tile strings are rewritten in place)' % (uid, len(data), n))
            plan.write(off, data, 'tstr:' + uid, [(off, off + n)])
        sb.draw(font)
        for idx, (base, data, off, end) in sb.assets.items():
            write_asset(plan, rom, idx, bytes(data), lz_free_state)
        stats[name] = (used, cap)
    return stats


LZ_REGION = [(0x50000, 0xCD6C2)]


def write_asset(plan, rom, idx, data, free):
    """Recompress asset `idx`; rewrite in place when it fits, else relocate and repoint."""
    off = entry_offset(rom, idx)
    _, end = decompress(rom, off)
    comp = compress(data, rom[off + 2:off + 4])
    if decompress(comp + b'\0' * 4, 0)[0] != data:
        raise SystemExit('LZ round trip failed for asset %d' % idx)
    if len(comp) <= end - off:
        plan.write(off, comp, 'lz:%d' % idx, LZ_REGION)
    else:
        a = free.alloc(len(comp))
        plan.write(a, comp, 'lz:%d' % idx, LZ_FREE)
        plan.write(TABLE + idx * 4, struct.pack('>I', a - TABLE), 'lztab:%d' % idx,
                   [(TABLE + idx * 4, TABLE + idx * 4 + 4)])


class FreeSpace:
    def __init__(self, regions):
        self.regions = [list(r) for r in regions]

    def alloc(self, n):
        for r in self.regions:
            if r[1] - r[0] >= n:
                a = r[0]
                r[0] += n
                return a
        raise SystemExit('out of free space for %d bytes' % n)
