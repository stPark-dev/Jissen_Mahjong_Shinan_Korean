"""Graphics-text jobs: redraw Korean text into LZ graphics assets.

Geometry and color rules live here; the text comes from text/ko/GFX.tsv
(source transcriptions in text/jp/GFX.tsv).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from bgedit import Layer, identity_layer, write_back_identity, replace_text, retile_shared, writeback_inplace  # noqa: E402
from check_ko import read_tsv  # noqa: E402
from lz import entry_offset, decompress  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMALL_FONT = os.path.join(ROOT, '.ext', 'fonts', 'galmuri', 'Galmuri11-Bold.ttf')
TINY_FONT = os.path.join(ROOT, '.ext', 'fonts', 'galmuri', 'Galmuri9.ttf')
TINY_FONT_SHA256 = 'e84e821b18be15b9e3a907ceb83cfba25fabf51c80b7edf0d2921cf8f8e1a11d'
SIGN_FONT = os.path.join(ROOT, '.ext', 'fonts', 'nanum', 'NanumMyeongjoExtraBold.ttf')
SIGN_FONT_SHA256 = 'a03d520bccc43ae1dc0bd5f64d143195a0ffce8318aacb0f3efb6117827eee14'
SMALL_FONT_SHA256 = '45d901e379138dd91873af157640f60aa4cf6beaa885c3efd2a8c279e039a237'

MENU_ORDER = ['GFX.MM.01', 'GFX.MM.02', 'GFX.MM.03', 'GFX.MM.04', 'GFX.MM.05', 'GFX.MM.06', 'GFX.MM.07', 'GFX.MM.08']
# BG1 main menu: 2 columns x 4 rows of buttons (screen pixels), reading order left-right
MM_BG_BOXES = {'GFX.MM.01': (21, 54), 'GFX.MM.02': (132, 54), 'GFX.MM.03': (21, 86), 'GFX.MM.04': (132, 86),
               'GFX.MM.05': (21, 118), 'GFX.MM.06': (132, 118), 'GFX.MM.07': (21, 150), 'GFX.MM.08': (132, 150)}
# OBJ #27: one button per 32 px, in this order
MM_OBJ_ORDER = ['GFX.MM.01', 'GFX.MM.03', 'GFX.MM.05', 'GFX.MM.07', 'GFX.MM.02', 'GFX.MM.04', 'GFX.MM.06', 'GFX.MM.08']
TEXT_IDX = {0xD, 0xE, 0xF}


def load_text():
    return {r['id']: r['ko'] for r in read_tsv(os.path.join(ROOT, 'text', 'ko', 'GFX.tsv'))}


def asset(rom, idx):
    return decompress(rom, entry_offset(rom, idx))[0]


# 1:1 glyph redraws in 16x16 glyph sheets (16 tiles per row; glyph = t, t+1, t+16, t+17).
# {asset: (bpp, ink, {tile: char})}. Mapping is per glyph so every consumer layout
# (horizontal, vertical plaques) keeps working.
S57 = {  # play-data sheet (BG3 $6000): per-glyph Sino-Korean / transliteration (T-004)
    0x000: '퐁', 0x002: ' ', 0x004: '치', 0x006: ' ', 0x008: '깡', 0x00A: '론', 0x00C: '쯔', 0x00E: '모',
    0x020: '회', 0x022: '수', 0x024: '반', 0x026: '장', 0x028: '리', 0x02A: '치', 0x02C: '후', 0x02E: '로',
    0x040: '화', 0x042: '료', 0x044: '방', 0x046: '총', 0x048: '유', 0x04A: '국', 0x04C: '대', 0x04E: '삼',
    0x060: '원', 0x062: '소', 0x064: '사', 0x066: '희', 0x068: '자', 0x06A: '일', 0x06C: '색', 0x06E: '청',
    0x080: '노', 0x082: '두', 0x084: '국', 0x086: '사', 0x088: '무', 0x08A: '쌍', 0x08C: '천', 0x08E: '화',
    0x0A0: '안', 0x0A2: '커', 0x0A4: '희', 0x0A6: '녹', 0x0A8: '깡', 0x0AA: '쯔', 0x0AC: '구', 0x0AE: '련',
    0x0C0: '보', 0x0C2: '등', 0x0C4: '지', 0x0C6: '배', 0x0C8: '초', 0x0CA: '춘', 0x0CC: '여', 0x0CE: '월',
    0x0E0: '앵', 0x0E2: '묘', 0x0E4: '효', 0x0E6: '빙', 0x0E8: '무', 0x0EA: '칠', 0x0EC: '석', 0x0EE: '추',
    0x100: '봉', 0x102: '홍', 0x104: '엽', 0x106: '신', 0x108: '악', 0x10A: '모', 0x10C: '고', 0x10E: '총',
}
S81 = {  # rules sheet (BG3 $6000; also resident in-game): per-glyph mapping (T-004)
    0x000: '룰', 0x002: ' ', 0x004: '설', 0x006: '정', 0x008: '쿠', 0x00A: '이', 0x00C: '탕', 0x00E: ' ',
    0x020: '와', 0x022: '레', 0x024: '메', 0x026: '쯔', 0x028: '모', 0x02A: '핑', 0x02C: '후', 0x02E: '일',
    0x040: '발', 0x042: '파', 0x044: '렌', 0x046: '짱', 0x048: '뒷', 0x04A: '깡', 0x04C: '도', 0x04E: '라',
    0x060: '남', 0x062: '장', 0x064: '노', 0x066: '텐', 0x068: '서', 0x06A: '입', 0x06C: '2', 0x06E: '판',
    0x080: '묶', 0x082: '음', 0x084: '도', 0x086: '본', 0x088: ' ', 0x08A: '야', 0x08C: '키', 0x08E: '토',
    0x0A0: '마', 0x0A2: '종', 0x0A4: '료', 0x0A6: '있', 0x0A8: '음', 0x0AA: '없', 0x0AC: '음', 0x0AE: '본',
    0x0C0: '륜', 0x0C2: '5', 0x0C4: '0',
    0x0C8: '리', 0x0CA: '우',      # spare blank slots used by rewritten strings (0C6 is the 8x16 blank tile)
}
CUP139 = {0x00: '배', 0x02: '초', 0x04: '춘', 0x06: '여', 0x08: '월', 0x0A: '앵', 0x0C: '묘', 0x0E: '효',
          0x20: '빙', 0x22: '무', 0x24: '칠', 0x26: '석', 0x28: '추', 0x2A: '봉', 0x2C: '홍', 0x2E: '엽',
          0x40: '신', 0x42: '악', 0x44: '모', 0x46: '고'}
S13 = {0x00: '계', 0x02: '속', 0x04: '할', 0x06: '까', 0x08: '요', 0x0A: '?', 0x0C: '예', 0x0E: '아',
       0x20: '니', 0x22: '오', 0x48: '반', 0x4A: '장'}   # dialog sheet #13 (asset tile n = BG3 tile $100 + n)
SHEET_REDRAW = {
    13: (2, 3, S13),
    57: (2, 3, S57),
    81: (2, 3, S81),
    183: (2, 3, {0xA6: '반', 0xA8: '장', 0xAA: '회'}),   # bracket: 半荘N回 (優勝 is a 3x3-tile box job)
    66: (2, 3, {0x000: '단', 0x002: '위', 0x004: '없', 0x006: '음', 0x008: '초', 0x00A: '2', 0x00C: '3',
                0x00E: '4', 0x020: '5', 0x022: '사', 0x024: '범', 0x026: '대'}),
}


def redraw_sheet(data, bpp, ink, mapping, font, shadow=None):
    from PIL import Image, ImageDraw
    from bgedit import encode_tile
    out = bytearray(data)
    tsz = 8 * bpp
    for t, ch in mapping.items():
        im = Image.new('1', (16, 16), 0)
        dr = ImageDraw.Draw(im)
        dr.fontmode = '1'
        x = 0 if font.getlength(ch) >= 16 else (16 - int(font.getlength(ch))) // 2
        if ch != ' ':
            dr.text((x, 0), ch, font=font, fill=1)
        px = im.load()
        g = [[ink if px[xx, yy] else 0 for xx in range(16)] for yy in range(16)]
        if shadow is not None:
            for yy in range(15, 0, -1):
                for xx in range(15, 0, -1):
                    if not g[yy][xx] and g[yy - 1][xx - 1] == ink:
                        g[yy][xx] = shadow
        for q, (dx, dy) in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
            tile = [[g[dy * 8 + yy][dx * 8 + xx] for xx in range(8)] for yy in range(8)]
            o = (t + dx + dy * 16) * tsz
            if o + tsz > len(out):
                raise SystemExit('sheet redraw outside asset')
            out[o:o + tsz] = encode_tile(tile, bpp)
    return bytes(out)


NE_BG_BOXES = [('GFX.NE.01', (18, 90, 46, 102), 'small'), ('GFX.NE.02', (82, 90, 110, 102), 'small'),
               ('GFX.NE.06', (208, 88, 242, 104), 'big')]
NE_BG_GENDER = {19: 'GFX.NE.03', 20: 'GFX.NE.04'}   # tilemap asset -> gender label at (146, 90, 174, 102)
NE_OBJ_BOXES = [('GFX.NE.01', (2, 2, 30, 14), 'small'), ('GFX.NE.02', (34, 2, 62, 14), 'small'),
                ('GFX.NE.03', (66, 2, 94, 14), 'small'), ('GFX.NE.05', (98, 2, 126, 14), 'small'),
                ('GFX.NE.04', (2, 18, 30, 30), 'small'), ('GFX.NE.06', (40, 24, 72, 40), 'big')]


def small_font():
    import hashlib
    from PIL import ImageFont
    if hashlib.sha256(open(SMALL_FONT, 'rb').read()).hexdigest() != SMALL_FONT_SHA256:
        raise SystemExit('unexpected font file %s' % SMALL_FONT)
    return ImageFont.truetype(SMALL_FONT, 12)


def tiny_font():
    import hashlib
    from PIL import ImageFont
    if hashlib.sha256(open(TINY_FONT, 'rb').read()).hexdigest() != TINY_FONT_SHA256:
        raise SystemExit('unexpected font file %s' % TINY_FONT)
    return ImageFont.truetype(TINY_FONT, 10)


# CPU name glyph sheet #65 (2bpp, 16x16 glyphs) and its fixed 6-cell name table $03:BB02
NAME_SHEET = 65
NAME_TABLE = 0x1BB02          # file offset of $03:BB02: 15 names x 6 words (0x5000 | tile)
NAME_BLANK = 0x50E8
VERT_TABLE = 0x1DA63          # file offset of $03:DA63: 15 names x 2 columns x 16 words (rank-state plaques)
NAME_SLOTS = [r * 32 + g * 2 for r in range(7) for g in range(8)] + [7 * 32 + g * 2 for g in range(4)]


def name_table_job(rom, font):
    """Return (sheet bytes, table bytes)."""
    import struct
    from PIL import Image, ImageDraw
    from bgedit import encode_tile
    names = []
    rows = {r['id']: r for r in read_tsv(os.path.join(ROOT, 'text', 'jp', 'NAM.tsv'))}
    ko = {r['id']: r['ko'] for r in read_tsv(os.path.join(ROOT, 'text', 'ko', 'NAM.tsv'))}
    by_idx = {}
    for i, r in rows.items():
        for ref in r['refs'].split(';'):
            by_idx[int(ref[1:])] = ko[i]
    for n in range(1, 16):
        names.append(by_idx[n])
    chars = sorted({c for nm in names for c in nm if c != ' '})
    if len(chars) > len(NAME_SLOTS):
        raise SystemExit('name sheet: %d glyphs > %d slots' % (len(chars), len(NAME_SLOTS)))
    slot = dict(zip(chars, NAME_SLOTS))
    data = bytearray(asset(rom, NAME_SHEET))
    for ch, t in slot.items():
        im = Image.new('1', (16, 16), 0)
        dr = ImageDraw.Draw(im)
        dr.fontmode = '1'
        dr.text((0, 0), ch, font=font, fill=1)
        px = im.load()
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            tile = [[3 if px[dx * 8 + xx, dy * 8 + yy] else 0 for xx in range(8)] for yy in range(8)]
            o = (t + dx + dy * 16) * 16
            data[o:o + 16] = encode_tile(tile, 2)
    table = bytearray()
    for nm in names:
        if len(nm) != 6:
            raise SystemExit('name %r is not 6 cells' % nm)
        for c in nm:
            table += struct.pack('<H', NAME_BLANK if c == ' ' else 0x5000 | slot[c])
    old = rom[NAME_TABLE:NAME_TABLE + len(table)]
    for k in range(0, len(old), 2):
        w = old[k] | old[k + 1] << 8
        if w >> 12 != 5:
            raise SystemExit('unexpected name table word %04X' % w)
    vert = bytearray()
    for n, nm in enumerate(names):
        for col in (0, 1):
            off = VERT_TABLE + (n * 2 + col) * 32
            old = [rom[off + 2 * i] | rom[off + 2 * i + 1] << 8 for i in range(16)]
            if old[:3] != [NAME_BLANK] * 3:
                raise SystemExit('unexpected vertical name record at %X' % off)
            words = [NAME_BLANK] * 3
            for c in nm:
                if c == ' ':
                    words += [NAME_BLANK, NAME_BLANK]
                else:
                    t = slot[c] + col
                    words += [0x2000 | t, 0x2000 | (t + 16)]
            words = (words + [NAME_BLANK] * 16)[:16]
            if len([w for w in words if w != NAME_BLANK]) != 2 * len(nm.replace(' ', '')):
                raise SystemExit('vertical name %r does not fit' % nm)
            vert += struct.pack('<16H', *words)
    return bytes(data), bytes(table), bytes(vert)


def draw_cell_rotated(L, x0, y0, ch, font, ink, clear_idx, bgv, rot):
    """Clear text pixels in a 16x16 cell and draw ch rotated by rot degrees clockwise."""
    from PIL import Image, ImageDraw
    for y in range(y0, y0 + 16):
        for x in range(x0, x0 + 16):
            if L.img[y][x] in clear_idx:
                L.set(x, y, bgv)
    im = Image.new('1', (16, 16), 0)
    dr = ImageDraw.Draw(im)
    dr.fontmode = '1'
    w = int(font.getlength(ch))
    dr.text(((16 - w) // 2, 2), ch, font=font, fill=1)
    if rot:
        im = im.rotate(-rot)
    px = im.load()
    for y in range(16):
        for x in range(16):
            if px[x, y] and L.img[y0 + y][x0 + x] == bgv:
                L.set(x0 + x, y0 + y, ink)
    L.touch_box(x0, y0, x0 + 16, y0 + 16)


def redraw_quad(data, bpp, tiles, ch, font, ink, shade=None):
    """Draw ch as a 16x16 glyph into four arbitrary tiles (TL, TR, BL, BR)."""
    from PIL import Image, ImageDraw
    from bgedit import encode_tile
    out = bytearray(data)
    im = Image.new('1', (16, 16), 0)
    dr = ImageDraw.Draw(im)
    dr.fontmode = '1'
    dr.text((0, 0), ch, font=font, fill=1)
    px = im.load()
    g = [[ink if px[x, y] else 0 for x in range(16)] for y in range(16)]
    if shade is not None:
        for y in range(15, 0, -1):
            for x in range(15, 0, -1):
                if not g[y][x] and g[y - 1][x - 1] == ink:
                    g[y][x] = shade
    tsz = 8 * bpp
    for t, (dx, dy) in zip(tiles, ((0, 0), (8, 0), (0, 8), (8, 8))):
        out[t * tsz:(t + 1) * tsz] = encode_tile([row[dx:dx + 8] for row in g[dy:dy + 8]], bpp)
    return bytes(out)


def erase_periodic(L, box, text_idx, period=2):
    x0, y0, x1, y1 = box
    mask = [[L.img[y][x] in text_idx for x in range(x0, x1)] for y in range(y0, y1)]
    for y in range(y0, y1):
        for x in range(x0, x1):
            if mask[y - y0][x - x0]:
                for k in range(1, 60):
                    sx = x - k * period
                    if sx >= 0 and L.img[y][sx] not in text_idx:
                        L.set(x, y, L.img[y][sx])
                        break
    L.touch_box(x0, y0, x1, y1)


def draw_sign(L, box, text, size, levels, text_idx, period=2):
    """Large antialiased sign text: erase text_idx pixels (periodic texture), then draw text
    with levels [(threshold, index), ...] from the strongest coverage down."""
    import hashlib
    from PIL import Image, ImageDraw, ImageFont
    if hashlib.sha256(open(SIGN_FONT, 'rb').read()).hexdigest() != SIGN_FONT_SHA256:
        raise SystemExit('unexpected font file %s' % SIGN_FONT)
    x0, y0, x1, y1 = box
    mask = [[L.img[y][x] in text_idx for x in range(x0, x1)] for y in range(y0, y1)]
    for y in range(y0, y1):
        for x in range(x0, x1):
            if mask[y - y0][x - x0]:
                for k in range(1, 30):
                    for sx in (x + k * period, x - k * period):
                        if x0 <= sx < x1 and not mask[y - y0][sx - x0]:
                            L.set(x, y, L.img[y][sx])
                            break
                    else:
                        continue
                    break
    big = 4
    font = ImageFont.truetype(SIGN_FONT, size * big)
    im = Image.new('L', ((x1 - x0) * big, (y1 - y0) * big), 0)
    dr = ImageDraw.Draw(im)
    l, t, r, b = dr.textbbox((0, 0), text, font=font)
    dr.text((((x1 - x0) * big - (r - l)) // 2 - l, ((y1 - y0) * big - (b - t)) // 2 - t), text, font=font, fill=255)
    im = im.resize((x1 - x0, y1 - y0), Image.BOX)
    px = im.load()
    for y in range(y1 - y0):
        for x in range(x1 - x0):
            v = px[x, y] / 255
            for th, idx in levels:
                if v >= th:
                    L.set(x0 + x, y0 + y, idx)
                    break
    L.touch_box(x0, y0, x1, y1)


def rom_patches(rom):
    """String rewrites in ROM that accompany glyph jobs: [(file_offset, bytes, [allowed ranges], [(ref_slot, new_ptr)])]."""
    import struct
    out = []
    def words_at(off):
        ws = []
        while True:
            w = rom[off] | rom[off + 1] << 8
            off += 2
            if w == 0xFFFF:
                return ws
            ws.append(w)
    def enc(ws):
        return b''.join(struct.pack('<H', w) for w in ws) + b'\xff\xff'
    # rules title $03:CDBC: ル ー ル 設 定 -> [룰][ ][설][정]
    title = 0x1CDBC
    assert words_at(title) == [0x5000, 0x5002, 0x5000, 0x5004, 0x5006]
    out.append((title, enc([0x5000, 0x5002, 0x5004, 0x5006]), [(title, title + 12)], []))
    # rules items 焼き鳥 ($03:CEE2) and 馬 ($03:CEEA) repacked in [CEE2, CEF6)
    yk, um = 0x1CEE2, 0x1CEEA
    assert words_at(yk) == [0x508A, 0x508C, 0x508E] and words_at(um) == [0x10C6, 0x10C6, 0x50A0, 0x10C6, 0x10C6]
    data = enc([0x508A, 0x508C, 0x508E, 0x50C8]) + enc([0x10C6, 0x50CA, 0x50A0, 0x10C6])
    assert len(data) == 0x1CEF6 - yk
    ref_um = 0x1CACB   # operand of LDA #$CEEA
    assert rom[ref_um] | rom[ref_um + 1] << 8 == 0xCEEA
    out.append((yk, data, [(yk, 0x1CEF6)], [(ref_um, 0xCEEC)]))
    # end-of-hanchan dialog $01:D37D: 半荘を続けますか? / はい いいえ  ->  반장 계속할까요? / 예 아니오
    dlg = 0xD37D
    old = [0x5148, 0x514A, 0x5106, 0x512E, 0x510E, 0x510A, 0x510C, 0x5120, 0x5122, 0xFFFE, 0xFFFE, 0xFFFE,
           0x514C, 0x514C, 0x5100, 0x5102, 0x514C, 0x5102, 0x5102, 0x5104]
    assert words_at(dlg) == old
    new = [0x5148, 0x514A, 0x514C, 0x5100, 0x5102, 0x5104, 0x5106, 0x5108, 0x510A, 0xFFFE, 0xFFFE, 0xFFFE,
           0x514C, 0x514C, 0x510C, 0x514C, 0x514C, 0x510E, 0x5120, 0x5122]
    out.append((dlg, enc(new), [(dlg, dlg + 2 * len(old) + 2)], []))
    return out


def jobs(rom, font):
    """Return {asset_index: new_bytes}."""
    ko = load_text()
    out = {}
    sfont = small_font()
    fonts = {'small': sfont, 'big': font}
    # name entry tabs (BG1): chars #18 shared by tilemaps #19 (male) and #20 (female)
    layers = []
    for tm_idx, gender in NE_BG_GENDER.items():
        L = Layer(asset(rom, 18), asset(rom, tm_idx))
        for uid, box, f in NE_BG_BOXES + [(gender, (146, 90, 174, 102), 'small')]:
            replace_text(L, box, ko[uid], fonts[f], 0xE, {0xD, 0xE}, period=1, dy=1 if f == 'small' else 0)
        layers.append(L)
    out[18], (out[19], out[20]) = retile_shared(layers, 512)
    # play data: BG1 chars #53 shared by tilemaps #54 (pages) and #55 (rank graph)
    layers = []
    tab_boxes = [('GFX.PD.02', 24), ('GFX.PD.03', 80), ('GFX.PD.04', 136), ('GFX.PD.05', 192)]
    rank_rows = [('GFX.PD.10', 82), ('GFX.PD.11', 97), ('GFX.PD.12', 113), ('GFX.PD.13', 129),
                 ('GFX.PD.14', 145), ('GFX.PD.15', 161)]
    for tm_idx in (54, 55):
        L = Layer(asset(rom, 53), asset(rom, tm_idx))
        replace_text(L, (112, 16, 208, 32), ko['GFX.PD.01'], font, 0xF, {0xE, 0xF, 0x2}, period=2, shadow=0x2)
        for uid, x in tab_boxes:
            replace_text(L, (x + 2, 194, x + 38, 206), ko[uid], sfont, 0x3, {0x1, 0x2, 0x3}, period=2, dy=1)
        if tm_idx == 55:
            for uid, y in rank_rows:
                replace_text(L, (13, y, 51, y + 14), ko[uid], sfont, 0x3, {0x1, 0x2, 0x3}, period=1, dy=1)
            replace_text(L, (13, 178, 51, 191), ko['GFX.PD.16'], sfont, 0xF, {0xD, 0xE, 0xF}, period=1, dy=1)
        layers.append(L)
    out[53], (out[54], out[55]) = retile_shared(layers, 512)
    # character data: BG1 chars #69 shared by tilemaps #70 / #71
    layers = []
    for tm_idx in (70, 71):
        L = Layer(asset(rom, 69), asset(rom, tm_idx))
        replace_text(L, (100, 16, 238, 32), ko['GFX.CD.01'], font, 0xF, {0xF, 0xE, 0xD, 0x2}, period=2, shadow=0x2)
        for uid, x in (('GFX.PD.06', 18), ('GFX.PD.04', 98), ('GFX.PD.05', 178)):
            replace_text(L, (x, 194, x + 60, 206), ko[uid], sfont, 0x3, {0x1, 0x2, 0x3}, period=2, dy=1)
        layers.append(L)
    out[69], (out[70], out[71]) = retile_shared(layers, 512)
    L = identity_layer(asset(rom, 60), 16)
    for uid, box in [('GFX.PD.02', (2, 2, 38, 14)), ('GFX.PD.03', (42, 2, 78, 14)), ('GFX.PD.04', (2, 18, 38, 30)),
                     ('GFX.PD.05', (42, 18, 78, 30)), ('GFX.PD.06', (2, 34, 62, 46)), ('GFX.PD.04', (2, 50, 62, 62)),
                     ('GFX.PD.05', (2, 66, 62, 78))]:
        replace_text(L, box, ko[uid], sfont, 0x3, {0x1, 0x2, 0x3}, period=2, dy=1)
    out[60] = write_back_identity(L)
    # opponent select "決定" button: BG1 chars #75 + tilemap #76
    L = Layer(asset(rom, 75), asset(rom, 76))
    replace_text(L, (51, 187, 102, 197), ko['GFX.NE.06'], tiny_font(), 0x1, {0x1, 0x2, 0x4}, period=1, dy=0)
    out[75], (out[76],) = retile_shared([L], 256)
    # Shinan intro sign: BG1 chars #189 + tilemap #190
    L = Layer(asset(rom, 189), asset(rom, 190))
    erase_periodic(L, (174, 20, 186, 40), {0x8, 0x9, 0xA, 0xB})
    erase_periodic(L, (174, 40, 178, 45), {0x8, 0x9, 0xA, 0xB})
    draw_sign(L, (68, 20, 175, 45), ko['GFX.SN.01'], 22, [(0.62, 0x8), (0.40, 0x9), (0.22, 0xA)], {0x8, 0x9, 0xA, 0xB})
    out[189], (out[190],) = retile_shared([L], 512)
    # exam header: BG3 chars #126 with the code-built tilemap captured in data/exam_header_bg3map.bin
    hdr_map = open(os.path.join(ROOT, 'data', 'exam_header_bg3map.bin'), 'rb').read()
    L = Layer(asset(rom, 126), hdr_map, bpp=2)
    lv = [(0.6, 0x3), (0.35, 0x2), (0.18, 0x1)]
    for uid, box in (('GFX.EX.01', (32, 16, 72, 40)), ('GFX.EX.02', (96, 16, 128, 40)), ('GFX.EX.03', (184, 16, 224, 40))):
        draw_sign(L, box, ko[uid], 18, lv, {0x1, 0x2, 0x3}, period=1)
    erase_periodic(L, (8, 72, 24, 120), {0x1, 0x2, 0x3}, period=1)
    for k, ch in enumerate(ko['GFX.EX.04']):
        replace_text(L, (8, 80 + 16 * k, 24, 96 + 16 * k), ch, font, 0x3, {0x1, 0x2, 0x3}, period=1, shadow=0x1)
    replace_text(L, (8, 176, 24, 192), ko['GFX.EX.05'], font, 0x3, {0x1, 0x2, 0x3}, period=1, shadow=0x1)
    out[126] = writeback_inplace(L)
    # exam banner "審査N期目": BG1 chars #120 with the code-built tilemap data/exam_banner_bg1map.bin
    L = Layer(asset(rom, 120), open(os.path.join(ROOT, 'data', 'exam_banner_bg1map.bin'), 'rb').read())
    ink = [(0.6, 0xF), (0.38, 0xE), (0.2, 0xD)]
    for uid, box in (('GFX.EX.01', (68, 99, 120, 124)), ('GFX.EX.02', (138, 99, 189, 124))):
        draw_sign(L, box, ko[uid], 20, ink, {0xF, 0xE, 0xD, 0x2}, period=1)
    out[120] = writeback_inplace(L)
    # exam ranking table: BG1 chars #132 with the code-built tilemap data/exam_rank_bg1map.bin
    L = Layer(asset(rom, 132), open(os.path.join(ROOT, 'data', 'exam_rank_bg1map.bin'), 'rb').read())
    txt = {0xF, 0xE, 0xD}
    for blk in range(3):
        oy = 72 * blk
        for (x0, x1) in ((104, 131), (160, 187)):
            for y0 in (9, 41):
                replace_text(L, (x0, y0 + oy, x1, y0 + 15 + oy), ko['GFX.EX.02'], font, 0xF, txt, period=1, shadow=0xD)
        replace_text(L, (9, 41 + oy, 24, 56 + oy), ko['GFX.EX.10'], font, 0xF, txt, period=1, shadow=0xD)
        replace_text(L, (202, 12 + oy, 248, 34 + oy), ko['GFX.EX.11'], font, 0xF, txt, period=1, shadow=0xD)
    out[132] = writeback_inplace(L)
    # exam header digits #128: remove the ornament dots that joined the neighbouring kanji strokes
    L = identity_layer(asset(rom, 128), 16, bpp=2)
    for cell in range(4):
        for y in (11, 12, 19):
            for x in range(4):
                L.set(24 * cell + x, y, 0)
        for y in (6, 7, 8, 14):
            for x in range(20, 24):
                L.set(24 * cell + x, y, 0)
    out[128] = write_back_identity(L)
    # exam judgement title: BG1 chars #136 + tilemap #137
    L = Layer(asset(rom, 136), asset(rom, 137))
    draw_sign(L, (68, 21, 194, 49), ko['GFX.EX.20'], 22, [(0.62, 0x8), (0.40, 0x9), (0.22, 0xA)], {0x8, 0x9, 0xA, 0xB, 0xC}, period=1)
    out[136], (out[137],) = retile_shared([L], 1024)
    # quit dialog: BG3 chars #47 (2bpp, $7000-$73FF: 128 tiles) shared by #48 (question) and #49 (goodbye)
    layers = []
    for tm_idx, boxes in ((48, [('GFX.QT.01', (40, 88, 216, 104)), ('GFX.QT.02', (80, 120, 112, 136)),
                                ('GFX.QT.03', (128, 120, 176, 136))]),
                          (49, [('GFX.QT.04', (56, 88, 200, 104)), ('GFX.QT.05', (56, 120, 200, 136))])):
        L = Layer(asset(rom, 47), asset(rom, tm_idx), bpp=2)
        for uid, box in boxes:
            replace_text(L, box, ko[uid], font, 0x3, {0x1, 0x2, 0x3}, period=1)
        layers.append(L)
    out[47], (out[48], out[49]) = retile_shared(layers, 128)
    L = identity_layer(asset(rom, 24), 16)
    for uid, box, f in NE_OBJ_BOXES:
        replace_text(L, box, ko[uid], fonts[f], 0xE, {0xD, 0xE}, period=1, dy=1 if f == 'small' else 0)
    out[24] = write_back_identity(L)
    # main menu BG1
    L = Layer(asset(rom, 25), asset(rom, 26))
    for uid, (x, y) in MM_BG_BOXES.items():
        replace_text(L, (x, y, x + 103, y + 25), ko[uid], font, 0xF, TEXT_IDX)
    out[25], (out[26],) = retile_shared([L], 512)
    # main menu OBJ (selected button)
    L = identity_layer(asset(rom, 27), 16)
    for k, uid in enumerate(MM_OBJ_ORDER):
        replace_text(L, (5, 5 + 32 * k, 109, 30 + 32 * k), ko[uid], font, 0xF, TEXT_IDX)
    out[27] = write_back_identity(L)
    for idx, (bpp, ink, mapping) in SHEET_REDRAW.items():
        out[idx] = redraw_sheet(asset(rom, idx), bpp, ink, mapping, font)
    # monthly tournament banner sheet #139: cup-name glyphs 1:1, then block labels
    L = identity_layer(redraw_sheet(asset(rom, 139), 4, 0xC, CUP139, font, shadow=0x4), 16)
    replace_text(L, (2, 52, 20, 67), ko['GFX.MT.01'], font, 0xF, {0xF, 0xC, 0xB, 0x8}, period=1, shadow=0x8)
    replace_text(L, (31, 52, 46, 67), ko['GFX.MT.02'], font, 0xF, {0xF, 0xC, 0xB, 0x8}, period=1, shadow=0x8)
    replace_text(L, (3, 102, 61, 123), ko['GFX.MT.03'], font, 0xF, {0xF, 0xC, 0xB, 0xA}, period=1, shadow=0xA)
    out[139] = write_back_identity(L)
    # in-game buttons / round badge (#99) and buttons / wind markers (#100): unique tiles, in place
    L = identity_layer(asset(rom, 99), 16)
    for k, uid in enumerate(['GFX.IG.01', 'GFX.IG.02', 'GFX.IG.03', 'GFX.IG.04', 'GFX.IG.05']):
        replace_text(L, (3, 42 + 16 * k, 37, 54 + 16 * k), ko[uid], sfont, 0xC, {0xC, 0xD, 0xE}, period=1, dy=1)
    for k, uid in enumerate(['GFX.IG.06', 'GFX.IG.07', 'GFX.IG.08', 'GFX.IG.09', 'GFX.IG.10']):
        replace_text(L, (44, 42 + 16 * k, 114, 54 + 16 * k), ko[uid], sfont, 0xC, {0xC, 0xD, 0xE}, period=1, dy=1)
    for uid, (a, b) in [('GFX.IG.11', (2, 17)), ('GFX.IG.12', (16, 31)), ('GFX.IG.13', (38, 54)),
                        ('GFX.IG.14', (57, 74)), ('GFX.IG.15', (73, 89)), ('GFX.IG.16', (90, 111))]:
        replace_text(L, (a, 20, b, 36), ko[uid], font, 0xF, {0xF, 0xE, 0xD, 0x8, 0xB}, period=1, shadow=0x8)
    out[99] = write_back_identity(L)
    L = identity_layer(asset(rom, 100), 16)
    for uid, box in [('GFX.IG.20', (4, 2, 36, 14)), ('GFX.IG.21', (44, 2, 109, 14)), ('GFX.IG.22', (4, 18, 36, 30)),
                     ('GFX.IG.23', (44, 18, 109, 30)), ('GFX.IG.24', (3, 34, 69, 46)), ('GFX.IG.25', (3, 50, 69, 62))]:
        replace_text(L, box, ko[uid], sfont, 0xC, {0xC, 0xD, 0xE}, period=1, dy=1)
    for k, ch in enumerate('동남서북'):
        replace_text(L, (24 * k + 3, 67, 24 * k + 21, 85), ch, font, 0x3, {0x1, 0x2, 0x3}, period=1)
        for r, (rx, ry, rot) in enumerate(((0, 96, 0), (64, 96, 180), (0, 112, 90), (64, 112, 270))):
            draw_cell_rotated(L, rx + 16 * k, ry, ch, sfont, 0xF, {0xD, 0xE, 0xF}, 0x9, rot)
    out[100] = write_back_identity(L)
    L = identity_layer(asset(rom, 102), 16)
    dark = {0x1, 0x2, 0x3}
    for uid, box, f in [('GFX.IG.30', (3, 3, 85, 22), font), ('GFX.IG.31', (3, 27, 70, 46), font),
                        ('GFX.IG.32', (3, 51, 54, 70), font), ('GFX.IG.33', (3, 75, 54, 94), sfont),
                        ('GFX.IG.36', (83, 75, 117, 92), font)]:
        replace_text(L, box, ko[uid], f, 0x1, dark, period=1)
    for uid, box, f in [('GFX.IG.34', (83, 27, 117, 44), sfont), ('GFX.IG.35', (83, 51, 117, 68), font)]:
        replace_text(L, box, ko[uid], f, 0xB, {0xB, 0x2, 0x9, 0xA}, period=1)
    replace_text(L, (64, 96, 96, 112), ko['GFX.IG.37'], font, 0xF, {0xF, 0x9, 0x8, 0xA}, period=1, shadow=0x8)
    out[102] = write_back_identity(L)
    L = identity_layer(asset(rom, 96), 16)
    for k, ch in enumerate(ko['GFX.IG.40']):
        replace_text(L, (16 * k, 0, 16 * k + 16, 16), ch, font, 0xF, {0xF, 0x1, 0x2, 0x3}, period=1, shadow=0x1)
    out[96] = write_back_identity(L)
    L = identity_layer(asset(rom, 86), 16)
    replace_text(L, (0, 16, 32, 31), ko['GFX.IG.37'], font, 0xF, {0xF, 0x5, 0x8, 0x9, 0xA}, period=1, shadow=0x8)
    out[86] = write_back_identity(L)
    out[109] = redraw_quad(asset(rom, 109), 2, (0x19, 0x1A, 0x1B, 0x1C), ko['GFX.IG.41'], font, 0x2, 0x1)
    L = identity_layer(out[183], 16, bpp=2)
    for k, ch in enumerate(ko['GFX.MT.04']):
        replace_text(L, (24 * k, 80, 24 * k + 24, 104), ch, font, 0x3, {0x1, 0x2, 0x3}, period=1)
    out[183] = write_back_identity(L)
    return out
