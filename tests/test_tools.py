"""Unit and product-build tests. Run: python3 -m pytest -q tests

Tests needing the source ROM are skipped when it is absent (it is never committed).
"""
import hashlib
import os
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

SRC = os.path.join(ROOT, 'Jissen! Mahjong Shinan (Japan).sfc')
need_rom = pytest.mark.skipif(not os.path.exists(SRC), reason='source ROM not present')


def rom():
    return open(SRC, 'rb').read()


# ---------------------------------------------------------------- LZ codec
def test_lz_roundtrip_synthetic():
    from lz import compress, decompress
    for data in (b'', b'A', b'ABABABABABAB' * 50, bytes(range(256)) * 9, os.urandom(3000)):
        c = compress(data)
        assert decompress(c + b'\0' * 4, 0)[0] == data


@need_rom
def test_lz_all_assets_roundtrip():
    from lz import entry_count, entry_offset, decompress, compress
    r = rom()
    for i in range(entry_count(r) - 1):
        d, _ = decompress(r, entry_offset(r, i))
        assert decompress(compress(d) + b'\0' * 4, 0)[0] == d


# ---------------------------------------------------------------- glyph / text
def test_code_of_layout():
    from build import code_of, glyph_offset
    assert code_of(0) == 0 and code_of(1) == 2 and code_of(8) == 0x20
    assert code_of(512) == 0x800
    assert glyph_offset(200) == 0x23200
    assert glyph_offset(512) == 0x28000


def test_encode_glyph_roundtrip():
    from kfont import encode_glyph
    from font_sheet import glyph_pixels
    lv = [[(x * y) % 4 for x in range(16)] for y in range(16)]
    tl, tr, bl, br = encode_glyph(lv)
    buf = bytearray(0x400)
    buf[0:16], buf[16:32], buf[0x100:0x110], buf[0x110:0x120] = tl, tr, bl, br
    import font_sheet
    old = font_sheet.FONT_BASE
    try:
        font_sheet.FONT_BASE = 0
        assert glyph_pixels(bytes(buf), 0) == lv
    finally:
        font_sheet.FONT_BASE = old


def test_check_ko_rejects_overflow(tmp_path):
    from check_ko import check_group
    p = tmp_path / 'ADV.x.tsv'
    p.write_text('id\tko\tstatus\tnote\nADV.0000\t가가가가가가가가가가가가가가가가|나\tdraft\t\n', encoding='utf-8')
    errs = check_group('ADV', True, str(p))
    assert any('16 cells' in e for e in errs)


def test_check_ko_rejects_unsupported_chars(tmp_path):
    from check_ko import check_group
    p = tmp_path / 'ADV.x.tsv'
    p.write_text('id\tko\tstatus\tnote\nADV.0000\tabc|나\tdraft\t\n', encoding='utf-8')
    assert any('unsupported' in e for e in check_group('ADV', True, str(p)))


def test_translations_pass_checker():
    from check_ko import check_group, LAYOUT
    for g in LAYOUT:
        assert check_group(g) == [], g


def test_ips_roundtrip():
    from build import make_ips, apply_ips
    a = bytes(1000)
    b = bytearray(a)
    b[10:20] = b'x' * 10
    b[500] = 7
    assert apply_ips(a, make_ips(a, bytes(b))) == bytes(b)


def test_bgedit_retile_shared_reuses_slots():
    from bgedit import Layer, encode_tile, retile_shared
    blank = bytes(32)
    ink = encode_tile([[1] * 8 for _ in range(8)], 4)
    chars = blank + ink
    tm = struct.pack('<H', 1) + bytes(2 * 1023)
    L = Layer(chars, tm)
    for y in range(8):
        for x in range(8):
            L.set(x, y, 2)
    new_chars, (new_tm,) = retile_shared([L], 2)
    assert len(new_chars) == len(chars)          # old slot 1 reused, nothing appended
    assert struct.unpack_from('<H', new_tm, 0)[0] == 1


# ---------------------------------------------------------------- product build
@need_rom
def test_product_build_invariants(tmp_path):
    import subprocess
    out = tmp_path / 'kr.sfc'
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'build.py'), '--out', str(out)], check=True,
                   capture_output=True)
    img = out.read_bytes()
    src = rom()
    assert len(img) == len(src)
    from build import apply_ips
    assert apply_ips(src, (tmp_path / 'kr.ips').read_bytes()) == img
    # header checksum valid
    s = sum(img[:0x7FDC]) + sum(img[0x7FE0:]) + 0x1FE
    assert struct.unpack_from('<HH', img, 0x7FDC) == ((s & 0xFFFF) ^ 0xFFFF, s & 0xFFFF)
    # deterministic
    out2 = tmp_path / 'kr2.sfc'
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'build.py'), '--out', str(out2)], check=True,
                   capture_output=True)
    assert hashlib.sha1(out2.read_bytes()).digest() == hashlib.sha1(img).digest()


@need_rom
def test_extractors_reproduce_committed_sources(tmp_path):
    import subprocess
    before = {g: open(os.path.join(ROOT, 'text', 'jp', g + '.tsv'), encoding='utf-8').read()
              for g in ('ADV', 'INS', 'PRO', 'NAM', 'MNU', 'SYS', 'TPG', 'TPC')}
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'extract.py')], check=True, capture_output=True)
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'tiletext_extract.py')], check=True, capture_output=True)
    for g, t in before.items():
        assert open(os.path.join(ROOT, 'text', 'jp', g + '.tsv'), encoding='utf-8').read() == t, g
