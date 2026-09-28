"""Extract TilePrint ($00:9A14) string populations into text/jp/TP*.tsv.

Each group is tied to one glyph sheet (data/sheets/<sheet>.tsv) and enumerated
from contiguous string runs established by sequential decoding and by the
reference tables listed in the spec. Tokens: <BR> <FC> <FD>, and <XXXX> for
non-text words (blanks, digits, icons) which are kept verbatim.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tiletext import load_sheet, words, decode  # noqa: E402
from dis65816 import lorom_to_file  # noqa: E402
from extract import SRC_SHA1, file_to_lorom  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# group -> (sheet, [(first_string_file_offset, end_file_offset)], extra singles)
SPEC = {
    'TPG': ('game_bg3', [
        (0x0C4BC, 0x0C530),   # call labels (horizontal + vertical)
        (0x0C6D4, 0x0C6E4),   # small winds
        (0x0C788, 0x0CA74),   # yaku records ($01:C6E4 table)
        (0x0CA8C, 0x0CB24),   # han / limit labels, 符 翻 点 ($01:CA74 table)
        (0x0CB44, 0x0CBE4),   # round names ($01:CB24 table)
    ], [0x0B39F]),            # 残り牌
    'TPC': ('config_bg3', [
        (0x1C3FF, 0x1C4C3),   # config labels and values ($03:C3FF..)
    ], []),
}


def is_text(tok, sheet):
    return tok in sheet.values()


def extract_group(rom, g):
    sheet_name, runs, singles = SPEC[g]
    sheet = load_sheet(sheet_name)
    rows = []
    offs = []
    for lo, hi in runs:
        o = lo
        while o < hi:
            ws = words(rom, o)
            offs.append((o, ws))
            o += 2 * len(ws) + 2
        if o != hi:
            raise SystemExit('%s run %X-%X does not end on a string boundary (%X)' % (g, lo, hi, o))
    for o in singles:
        offs.append((o, words(rom, o)))
    for n, (o, ws) in enumerate(offs):
        rows.append(('%s.%04d' % (g, n), file_to_lorom(o), decode(ws, sheet)))
    return sheet_name, rows


def main():
    import hashlib
    rom = open(os.path.join(ROOT, 'Jissen! Mahjong Shinan (Japan).sfc'), 'rb').read()
    if hashlib.sha1(rom).hexdigest() != SRC_SHA1:
        sys.exit('unsupported source revision')
    for g in SPEC:
        sheet_name, rows = extract_group(rom, g)
        with open(os.path.join(ROOT, 'text', 'jp', g + '.tsv'), 'w', encoding='utf-8') as f:
            f.write('id\taddr\tsheet\tjp\n')
            for i, cpu, text in rows:
                f.write('%s\t%06X\t%s\t%s\n' % (i, cpu, sheet_name, text))
        print('%s: %d strings (sheet %s)' % (g, len(rows), sheet_name))


if __name__ == '__main__':
    main()
