"""Product build: source ROM + text/ko + data -> build/*.sfc and build/*.ips.

Every change is planned from the immutable source image. Each write is recorded
with an owner; overlapping writers, writes outside declared regions, and any
final byte difference not covered by a record stop the build.
"""
import argparse
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from check_ko import check_group, read_tsv, LAYOUT  # noqa: E402
from dis65816 import lorom_to_file  # noqa: E402
from extract import (SRC_SHA1, ADV_BANK_TABLE, ADV_SLOT_TABLE, ADV_INSTRUCTORS, ADV_SITUATIONS,  # noqa: E402
                     INS_HEADER, PRO_TABLE, NAM_TABLE, FIXED_GLYPHS, file_to_lorom, words_at, w16)
from kfont import encode_glyph  # noqa: E402
from sheets import build_sheets, FreeSpace, LZ_FREE, write_asset  # noqa: E402
from lz import entry_offset, decompress  # noqa: E402
import logo  # noqa: E402
import gfxjobs  # noqa: E402
import nameentry  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'Jissen! Mahjong Shinan (Japan).sfc')
OUT_DIR = os.path.join(ROOT, 'build')
FONT_PATH = os.path.join(ROOT, '.ext', 'fonts', 'neodgm.ttf')
FONT_SHA256 = '77305267996073aae07bad9313dad2e306a4128e55bfafbed4c41558fee57b4d'

FONT_BASE = 0x20000
FONT_END = 0x30000
GLYPH_CAPACITY = 1024
# Original glyphs kept at their slots with their original meaning, and the
# characters they stand for in Korean text.
FIXED_MAP = {' ': 0, '0': 162, '1': 163, '2': 164, '3': 165, '4': 166, '5': 167, '6': 168,
             '7': 169, '8': 170, '9': 171, '?': 172, '!': 173, ',': 174, '.': 175, '…': 176, '/': 177}
# fixed slots whose original artwork is kept (not redrawn): ')' and month glyphs 10/11/12
KEEP_ART = {178, 179, 180, 181}
GROUPS = ['ADV', 'INS', 'PRO', 'NAM', 'MNU', 'SYS']

# Code immediates that point at relocatable bank-$00 strings: file offset of the
# 16-bit operand of `LDA #addr` -> original target CPU address.
CODE_IMMEDIATES = {
    lorom_to_file(0x00DD69): 0x00E344,
    lorom_to_file(0x00E173): 0x00E3A6,
    lorom_to_file(0x00E163): 0x00E418,
}
# String regions whose every reference is known (tables + CODE_IMMEDIATES): they are
# repacked sequentially and all references rewritten. Unreferenced members are listed.
REPACK_REGIONS = [(0x021DA, 0x02A5A), (0x06330, 0x07848)]
UNREFERENCED = {0x00E330}  # test string, no reference found
# Free space usable for relocation (file offsets, [lo, hi)), per LoROM bank.
FREE_TAILS = {0x08: [(0x46694, 0x48000)], 0x09: [(0x4D6FE, 0x50000)]}


def code_of(n):
    return ((n // 512) << 11) | (((n % 512) // 8) * 32 + (n % 8) * 2)


def glyph_offset(n):
    return FONT_BASE + (n // 8) * 0x200 + (n % 8) * 0x20


class Plan:
    """Byte-level write plan with owner tracking."""

    def __init__(self, src):
        self.src = bytes(src)
        self.img = bytearray(src)
        self.owner = {}

    def write(self, off, data, owner, allowed):
        if not any(lo <= off and off + len(data) <= hi for lo, hi in allowed):
            raise SystemExit('write outside declared region: %s @%X+%d' % (owner, off, len(data)))
        for i in range(off, off + len(data)):
            prev = self.owner.get(i)
            if prev is not None and prev != owner:
                raise SystemExit('overlapping writers at %X: %s vs %s' % (i, prev, owner))
            self.owner[i] = owner
        self.img[off:off + len(data)] = data

    def verify(self):
        for i, (a, b) in enumerate(zip(self.src, self.img)):
            if a != b and i not in self.owner:
                raise SystemExit('unexplained difference at %X' % i)


# ------------------------------------------------------------------ text model
def split_lines(jp):
    """Return the list of separators (lists of control words) between source lines."""
    seps, cur, out = [], [], []
    i = 0
    while i < len(jp):
        if jp.startswith('<BR>', i):
            cur.append(0xFFFE)
            i += 4
        else:
            if cur:
                seps.append(cur)
                cur = []
            i += 1
    if cur:
        seps.append(cur)
    return seps


def load_units():
    units = []
    for g in GROUPS:
        src = {r['id']: r for r in read_tsv(os.path.join(ROOT, 'text', 'jp', g + '.tsv'))}
        ko = {r['id']: r for r in read_tsv(os.path.join(ROOT, 'text', 'ko', g + '.tsv'))}
        for i, s in src.items():
            k = ko[i]
            units.append({'id': i, 'group': g, 'cpu': int(s['addr'], 16), 'refs': s['refs'],
                          'jp': s['jp'], 'ko': k['ko'], 'status': k['status']})
    return units


def allocate_glyphs(units, extra_chars=''):
    chars = set(extra_chars)
    for u in units:
        chars.update(u['ko'].replace('|', ''))
    fixed = {c for c in chars if c in FIXED_MAP}
    free_chars = sorted(chars - fixed)
    slots = [n for n in range(1, GLYPH_CAPACITY) if n not in FIXED_GLYPHS]
    if len(free_chars) > len(slots):
        raise SystemExit('glyph capacity exceeded: %d chars > %d slots' % (len(free_chars), len(slots)))
    cmap = dict(FIXED_MAP)
    for c, n in zip(free_chars, slots):
        cmap[c] = n
    return cmap, len(free_chars), len(slots)


def encode_unit(u, cmap):
    lines = u['ko'].split('|')
    seps = split_lines(u['jp'])
    if u['group'] in ('ADV', 'INS', 'PRO'):
        seps = [[0xFFFE, 0xFFFE]] * (len(lines) - 1)
    words = []
    for n, line in enumerate(lines):
        for ch in line:
            if ch not in cmap:
                raise SystemExit('%s: unmapped character %r' % (u['id'], ch))
            words.append(code_of(cmap[ch]))
        if n < len(lines) - 1:
            words += seps[n] if n < len(seps) else [0xFFFE, 0xFFFE]
    return b''.join(struct.pack('<H', w) for w in words) + b'\xff\xff'


# ------------------------------------------------------------------ font
def render_font(plan, cmap):
    from PIL import Image, ImageDraw, ImageFont
    if hashlib.sha256(open(FONT_PATH, 'rb').read()).hexdigest() != FONT_SHA256:
        raise SystemExit('unexpected font file %s' % FONT_PATH)
    font = ImageFont.truetype(FONT_PATH, 16)
    region = [(FONT_BASE, FONT_END)]
    for ch, n in sorted(cmap.items(), key=lambda kv: kv[1]):
        if n in KEEP_ART or ch == ' ':
            continue
        im = Image.new('1', (16, 16), 0)
        dr = ImageDraw.Draw(im)
        dr.fontmode = '1'
        x = 0 if font.getlength(ch) >= 16 else (16 - int(font.getlength(ch))) // 2
        dr.text((x, 0), ch, font=font, fill=1)
        px = im.load()
        levels = [[3 if px[xx, yy] else 0 for xx in range(16)] for yy in range(16)]
        if not any(any(r) for r in levels):
            raise SystemExit('font has no glyph for %r' % ch)
        tl, tr, bl, br = encode_glyph(levels)
        o = glyph_offset(n)
        plan.write(o, tl + tr, 'font', region)
        plan.write(o + 0x100, bl + br, 'font', region)


# ------------------------------------------------------------------ references
def reference_slots(rom):
    """Map original string CPU address -> list of file offsets of 16-bit pointers to it."""
    refs = {}

    def add(target, slot):
        refs.setdefault(target, []).append(slot)

    for ins in range(ADV_INSTRUCTORS):
        bank = w16(rom, ADV_BANK_TABLE + ins * 2)
        slot_addr = w16(rom, ADV_SLOT_TABLE + ins * 2)
        sub = w16(rom, lorom_to_file(bank << 16 | slot_addr))
        for s in range(ADV_SITUATIONS):
            p = lorom_to_file(bank << 16 | sub) + s * 2
            add(bank << 16 | w16(rom, p), p)
    for k in range(3):
        sub = w16(rom, INS_HEADER + k * 2)
        for i in range(16):
            p = lorom_to_file(sub) + i * 2
            add(w16(rom, p), p)
    for i in range(16):
        add(w16(rom, PRO_TABLE + i * 2), PRO_TABLE + i * 2)
        add(w16(rom, NAM_TABLE + i * 2), NAM_TABLE + i * 2)
    for slot, target in CODE_IMMEDIATES.items():
        assert w16(rom, slot) == target & 0xFFFF
        add(target, slot)
    return {t: sorted(set(v)) for t, v in refs.items()}


def place_strings(plan, units, cmap):
    rom = plan.src
    refs = reference_slots(rom)
    extents = {}
    for u in units:
        off = lorom_to_file(u['cpu'])
        n = 2 * len(words_at(rom, off)) + 2
        extents[u['id']] = (off, off + n)
    string_regions = list(extents.values())
    # declared tails start after the last source string of the bank (the terminator
    # FFFF of the last string is indistinguishable from FF padding)
    tails = {}
    for b, v in FREE_TAILS.items():
        end = max([e for s, e in string_regions if s // 0x8000 == b] + [0])
        tails[b] = [(max(lo, end), hi) for lo, hi in v]
    free = {b: list(v) for b, v in tails.items()}
    pending = []
    stats = {'inplace': 0, 'moved': 0, 'repacked': 0}
    for rlo, rhi in REPACK_REGIONS:
        members = sorted((extents[u['id']][0], u) for u in units if rlo <= extents[u['id']][0] < rhi)
        covered = sum(extents[u['id']][1] - extents[u['id']][0] for _, u in members)
        if covered != rhi - rlo:
            raise SystemExit('repack region %X-%X is not fully owned by text units' % (rlo, rhi))
        pos = rlo
        for _, u in members:
            data = encode_unit(u, cmap)
            if pos + len(data) > rhi:
                raise SystemExit('repack region %X-%X overflow at %s' % (rlo, rhi, u['id']))
            plan.write(pos, data, 'str:' + u['id'], [(rlo, rhi)])
            if pos != extents[u['id']][0]:
                if u['cpu'] in UNREFERENCED:
                    pass
                elif u['cpu'] not in refs:
                    raise SystemExit('%s moved but has no known references' % u['id'])
                else:
                    for slot in refs[u['cpu']]:
                        plan.write(slot, struct.pack('<H', file_to_lorom(pos) & 0xFFFF), 'ptr:' + u['id'], [(slot, slot + 2)])
            pos += len(data)
            u['_done'] = True
            stats['repacked'] += 1
    for u in units:
        if u.get('_done'):
            continue
        data = encode_unit(u, cmap)
        lo, hi = extents[u['id']]
        if len(data) <= hi - lo:
            plan.write(lo, data, 'str:' + u['id'], string_regions)
            if hi - lo - len(data) >= 4:
                free.setdefault(lo // 0x8000, []).append((lo + len(data), hi))
            stats['inplace'] += 1
        else:
            pending.append((u, data, lo, hi))
            free.setdefault(lo // 0x8000, []).append((lo, hi))
    for u, data, lo, hi in pending:
        bank = lo // 0x8000
        if u['cpu'] not in refs:
            raise SystemExit('%s grew (%d > %d bytes) but has no known references' % (u['id'], len(data), hi - lo))
        frags = sorted(free.get(bank, []), key=lambda r: r[1] - r[0])
        for k, (a, b) in enumerate(frags):
            if b - a >= len(data):
                break
        else:
            raise SystemExit('%s: no space in bank %02X for %d bytes' % (u['id'], bank, len(data)))
        free[bank].remove((a, b))
        if b - a - len(data) >= 4:
            free[bank].append((a + len(data), b))
        allowed = string_regions + tails.get(bank, [])
        plan.write(a, data, 'str:' + u['id'], allowed)
        new_cpu = file_to_lorom(a) & 0xFFFF
        for slot in refs[u['cpu']]:
            plan.write(slot, struct.pack('<H', new_cpu), 'ptr:' + u['id'], [(slot, slot + 2)])
        stats['moved'] += 1
    return stats


def fix_checksum(img):
    img[0x7FDC:0x7FE0] = b'\xff\xff\x00\x00'
    s = sum(img) & 0xFFFF
    img[0x7FDC:0x7FE0] = struct.pack('<HH', s ^ 0xFFFF, s)


def make_ips(src, dst):
    """IPS records for each run of differing bytes (source <= 16MB, same size)."""
    assert len(src) == len(dst) and len(dst) < 0x1000000
    out = bytearray(b'PATCH')
    i, n = 0, len(dst)
    while i < n:
        if src[i] == dst[i]:
            i += 1
            continue
        j = i
        while j < n and src[j] != dst[j] and j - i < 0xFFFF:
            j += 1
        start = i - 1 if i == 0x454F46 else i  # offset 'EOF' cannot start a record
        out += struct.pack('>I', start)[1:] + struct.pack('>H', j - start) + dst[start:j]
        i = j
    return bytes(out + b'EOF')


def apply_ips(src, ips):
    img = bytearray(src)
    assert ips[:5] == b'PATCH'
    p = 5
    while ips[p:p + 3] != b'EOF':
        off = int.from_bytes(ips[p:p + 3], 'big')
        size = int.from_bytes(ips[p + 3:p + 5], 'big')
        p += 5
        if size == 0:
            rle = int.from_bytes(ips[p:p + 2], 'big')
            img[off:off + rle] = bytes([ips[p + 2]]) * rle
            p += 3
        else:
            img[off:off + size] = ips[p:p + size]
            p += size
    return bytes(img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(OUT_DIR, 'Jissen_Mahjong_Shinan_KR.sfc'))
    args = ap.parse_args()
    src = open(SRC, 'rb').read()
    if hashlib.sha1(src).hexdigest() != SRC_SHA1:
        raise SystemExit('unsupported source ROM (sha1 mismatch)')
    errs = []
    for g in GROUPS:
        errs += check_group(g)
    if errs:
        for e in errs[:20]:
            print(e)
        raise SystemExit('translation check failed (%d problems)' % len(errs))
    units = load_units()
    cmap, used, cap = allocate_glyphs(units, nameentry.syllables())
    plan = Plan(src)
    render_font(plan, cmap)
    stats = place_strings(plan, units, cmap)
    from PIL import ImageFont
    free = FreeSpace(LZ_FREE)
    sheet_stats = build_sheets(plan, ImageFont.truetype(FONT_PATH, 16), free)
    title = bytearray(decompress(src, entry_offset(src, logo.LOGO_ASSET))[0])
    clipped = logo.apply_logo(title)[0]
    if clipped:
        raise SystemExit('title logo clipped by %d pixels' % clipped)
    write_asset(plan, src, logo.LOGO_ASSET, bytes(title), free)
    for idx, data in sorted(gfxjobs.jobs(src, ImageFont.truetype(FONT_PATH, 16)).items()):
        write_asset(plan, src, idx, data, free)
    nsheet, ntable, nvert = gfxjobs.name_table_job(src, ImageFont.truetype(FONT_PATH, 16))
    plan.write(gfxjobs.VERT_TABLE, nvert, 'name_vert', [(gfxjobs.VERT_TABLE, gfxjobs.VERT_TABLE + len(nvert))])
    write_asset(plan, src, gfxjobs.NAME_SHEET, nsheet, free)
    plan.write(gfxjobs.NAME_TABLE, ntable, 'name_table', [(gfxjobs.NAME_TABLE, gfxjobs.NAME_TABLE + len(ntable))])
    for off, data, allowed, refs in gfxjobs.rom_patches(src):
        plan.write(off, data, 'gfxstr:%X' % off, allowed)
        for slot, ptr in refs:
            plan.write(slot, struct.pack('<H', ptr), 'gfxptr:%X' % slot, [(slot, slot + 2)])
    ct = nameentry.code_table(cmap, code_of)
    plan.write(nameentry.CODE_TABLE, ct, 'name_codes', [(nameentry.CODE_TABLE, nameentry.CODE_TABLE + len(ct))])
    ne_assets, ne_tiles = nameentry.graphics(src, ImageFont.truetype(FONT_PATH, 16))
    for idx, data in sorted(ne_assets.items()):
        write_asset(plan, src, idx, data, free)
    print('name entry grid: %d tiles' % ne_tiles)
    plan.verify()
    img = plan.img
    fix_checksum(img)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    open(args.out, 'wb').write(img)
    ips = make_ips(src, img)
    if apply_ips(src, ips) != bytes(img):
        raise SystemExit('IPS round trip failed')
    open(os.path.splitext(args.out)[0] + '.ips', 'wb').write(ips)
    with open(os.path.join(os.path.dirname(args.out), 'charmap_ko.tsv'), 'w', encoding='utf-8') as f:
        f.write('glyph\tcode\tchar\n')
        for ch, n in sorted(cmap.items(), key=lambda kv: kv[1]):
            f.write('%d\t%04X\t%s\n' % (n, code_of(n), ch))
    reviewed = sum(1 for u in units if u['status'] == 'reviewed')
    print('glyphs: %d/%d free slots used; strings: %d in place, %d moved; reviewed %d/%d' %
          (used, cap, stats['inplace'], stats['moved'], reviewed, len(units)))
    for name, (u, c) in sheet_stats.items():
        print('sheet %s: %d/%d glyph slots' % (name, u, c))
    print('wrote', args.out, 'sha1', hashlib.sha1(img).hexdigest())


if __name__ == '__main__':
    main()
