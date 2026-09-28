"""Extract PrintString ($00:9BE8) text populations into text/jp/*.tsv.

Every population is enumerated from its consumer's reference structure
(docs/survey.md). The extractor fails if a reference does not decode or if the
decoded text does not re-encode to the original words.

Output columns: id, refs (physical references, ';'-separated), jp
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from jptext import load_charmap, decode_word, ROOT  # noqa: E402
from dis65816 import lorom_to_file  # noqa: E402

SRC_SHA1 = '0b7785d0a778f48556d272001010e732b044b396'


def w16(rom, off):
    return rom[off] | rom[off + 1] << 8


def words_at(rom, off):
    ws = []
    while True:
        w = w16(rom, off)
        off += 2
        if w == 0xFFFF:
            return ws
        ws.append(w)
        if len(ws) > 512:
            raise ValueError('unterminated string at %x' % off)


def encode_tokens(text, ch2code):
    """Inverse of decode for round-trip checks: tokens <BR> <FC> <FD> <XXXX>."""
    out = []
    i = 0
    toks = {'<BR>': 0xFFFE, '<FC>': 0xFFFC, '<FD>': 0xFFFD}
    while i < len(text):
        if text[i] == '<':
            j = text.index('>', i)
            t = text[i:j + 1]
            out.append(toks[t] if t in toks else int(t[1:-1], 16))
            i = j + 1
        elif text[i] == '{':
            j = text.index('}', i)
            out.append(ch2code[text[i:j + 1]])
            i = j + 1
        else:
            out.append(ch2code[text[i]])
            i += 1
    return out


# ---------------------------------------------------------------- populations
# ADV: $01:B960 bank table / $01:B980 header-slot table (instructor 0..15),
#      header slot -> subtable of 100 situations ($8DC0).
ADV_BANK_TABLE = 0x00B960   # file offset of $01:B960
ADV_SLOT_TABLE = 0x00B980
ADV_INSTRUCTORS = 16
ADV_SITUATIONS = 100

INS_HEADER = 0x62C8          # $00:E2C8 -> 3 subtables x 16
PRO_TABLE = 0x1FEE2          # $03:FEE2 -> 16 pointers (bank $00)
NAM_TABLE = 0x4FDF           # $00:CFDF -> 16 pointers (bank $00)

# Direct code references `LDA #addr / STA $23 / LDX #bank / STX $25` (bank $00/$03)
# and table-free singletons, as CPU addresses.
MENU_REFS = [
    0x0383DD, 0x0383F1, 0x0381E1, 0x0383FF, 0x038413, 0x038421, 0x00E344, 0x038053,
    0x038099, 0x0380AD, 0x038047, 0x03802F, 0x03803B,
]


# Contiguous string regions (file offsets, [lo, hi)) established by sequential decoding.
SYS_REGIONS = [(0x18005, 0x1844F), (0x06330, 0x07848)]
# Glyph codes kept at their original slots (space, digits, symbols 162-181).
FIXED_GLYPHS = [0] + list(range(162, 182))
FIXED_CODES = {((n // 512) << 11) | (((n % 512) // 8) * 32 + (n % 8) * 2) for n in FIXED_GLYPHS} | {0xFFFC, 0xFFFD, 0xFFFE}


def file_to_lorom(off):
    return ((off // 0x8000) << 16) | 0x8000 | (off & 0x7FFF)


def collect(rom, cmap):
    units = {}   # cpu_addr -> {'group', 'refs': []}
    order = []

    def add(group, cpu, ref):
        if cpu not in units:
            units[cpu] = {'group': group, 'refs': [], 'first': ref}
            order.append(cpu)
        units[cpu]['refs'].append(ref)

    # ADV
    for ins in range(ADV_INSTRUCTORS):
        bank = w16(rom, ADV_BANK_TABLE + ins * 2)
        slot_addr = w16(rom, ADV_SLOT_TABLE + ins * 2)
        sub = w16(rom, lorom_to_file(bank << 16 | slot_addr))
        slot = (slot_addr - 0x8000) // 2 + (0 if bank == 8 else 8)
        for s in range(ADV_SITUATIONS):
            p = w16(rom, lorom_to_file(bank << 16 | sub) + s * 2)
            add('ADV', bank << 16 | p, 'i%02d.s%03d' % (ins, s))
    # INS
    for k in range(3):
        sub = w16(rom, INS_HEADER + k * 2)
        for i in range(16):
            p = w16(rom, lorom_to_file(sub) + i * 2)
            add('INS', p, '%s.i%02d' % ('intro win lose'.split()[k], i))
    for i in range(16):
        add('PRO', w16(rom, PRO_TABLE + i * 2), 'i%02d' % i)
        add('NAM', w16(rom, NAM_TABLE + i * 2), 'i%02d' % i)
    for cpu in MENU_REFS:
        add('MNU', cpu, 'code')
    # SYS: every remaining string of the contiguous string regions, enumerated sequentially
    for lo, hi in SYS_REGIONS:
        off = lo
        while off < hi:
            ws = words_at(rom, off)
            cpu = file_to_lorom(off)
            if any(w not in FIXED_CODES for w in ws):
                add('SYS', cpu, 'region')
            off += 2 * len(ws) + 2
        if off != hi:
            raise ValueError('region %x-%x does not end on a string boundary' % (lo, hi))
    return units, order


def main():
    rom = open(os.path.join(ROOT, 'Jissen! Mahjong Shinan (Japan).sfc'), 'rb').read()
    import hashlib
    if hashlib.sha1(rom).hexdigest() != SRC_SHA1:
        sys.exit('unsupported source revision')
    cmap = load_charmap()
    ch2code = {}
    for code, ch in cmap.items():
        ch2code.setdefault(ch, code)
    units, order = collect(rom, cmap)
    out_dir = os.path.join(ROOT, 'text', 'jp')
    os.makedirs(out_dir, exist_ok=True)
    groups = {}
    for cpu in order:
        u = units[cpu]
        ws = words_at(rom, lorom_to_file(cpu))
        text = ''.join(decode_word(w, cmap) for w in ws)
        if encode_tokens(text, ch2code) != ws:
            # duplicate glyphs (same char at two codes) keep raw code
            text = ''.join(decode_word(w, cmap) if encode_tokens(decode_word(w, cmap), ch2code) == [w]
                           else '<%04X>' % w for w in ws)
            assert encode_tokens(text, ch2code) == ws
        groups.setdefault(u['group'], []).append((cpu, u, text))
    total = 0
    for g, rows in groups.items():
        with open(os.path.join(out_dir, g + '.tsv'), 'w', encoding='utf-8') as f:
            f.write('id\taddr\trefs\tjp\n')
            for n, (cpu, u, text) in enumerate(rows):
                f.write('%s.%04d\t%06X\t%s\t%s\n' % (g, n, cpu, ';'.join(u['refs']), text))
        chars = sum(len(t.replace('<BR>', '')) for _, _, t in rows)
        total += len(rows)
        print('%s: %d strings, %d chars' % (g, len(rows), chars))
    print('total', total)


if __name__ == '__main__':
    main()
