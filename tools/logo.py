"""Title logo replacement: user artwork -> OBJ tiles of LZ asset #5 using the
existing sprite layout (data/title_obj.tsv) and OBJ palette."""
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = os.path.join(ROOT, 'title_logo.png')
LOGO_ASSET = 5


def load_layout():
    sprites, pal = [], None
    for line in open(os.path.join(ROOT, 'data', 'title_obj.tsv')):
        if line.startswith('# ') and len(line.split()) == 17:
            pal = [int(x, 16) for x in line.split()[1:]]
        if line.startswith('#') or not line.strip():
            continue
        x, y, t, p = map(int, line.split())
        sprites.append((x, y, t, p))
    return sprites, pal


def bgr555_to_rgb(c):
    return ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)


def coverage(sprites):
    cov = set()
    for x, y, t, p in sprites:
        for yy in range(16):
            for xx in range(16):
                if 0 <= x + xx < 256:
                    cov.add((x + xx, y + yy))
    return cov


def fit_logo(sprites, scale_w=244, dx=8, dy=0):
    src = Image.open(LOGO).convert('RGBA')
    bbox = src.getchannel('A').point(lambda v: 255 if v > 128 else 0).getbbox()
    src = src.crop(bbox)
    h = round(src.height * scale_w / src.width)
    img = src.resize((scale_w, h), Image.LANCZOS)
    return img, dx, dy


def quantize(img, pal):
    cols = [bgr555_to_rgb(c) for c in pal]
    px = img.load()
    out = {}
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a < 128:
                continue
            best = min(range(1, 16), key=lambda i: (cols[i][0] - r) ** 2 * 3 + (cols[i][1] - g) ** 2 * 4 + (cols[i][2] - b) ** 2 * 2)
            out[(x, y)] = best
    return out


def best_fit(sprites, pal):
    cov = coverage(sprites)
    best = None
    for w in (236, 240, 244, 248):
        for dy in range(0, 8):
            img, dx, _ = fit_logo(sprites, w, 8 + (248 - w) // 2, dy)
            a = img.getchannel('A').load()
            clipped = sum(1 for y in range(img.height) for x in range(img.width)
                          if a[x, y] >= 128 and (x + dx, y + dy) not in cov)
            if img.height + dy > 128:
                continue
            if best is None or clipped < best[0]:
                best = (clipped, w, dx, dy)
    return best


def apply_logo(asset):
    """asset: bytearray (decompressed #5, OBJ 4bpp tiles from VRAM $0000)."""
    sprites, pal = load_layout()
    clipped, w, dx, dy = best_fit(sprites, pal)
    img, _, _ = fit_logo(sprites, w, dx, dy)
    q = quantize(img, pal)
    for x, y, t, p in sprites:
        for sub in (t, t + 1, t + 16, t + 17):
            asset[sub * 32:sub * 32 + 32] = bytes(32)
    for x, y, t, p in sprites:
        for yy in range(16):
            for xx in range(16):
                v = q.get((x + xx - dx, y + yy - dy))
                if not v:
                    continue
                sub = t + (yy // 8) * 16 + (xx // 8)
                o = sub * 32
                r, c = yy % 8, xx % 8
                for pl in range(4):
                    if (v >> pl) & 1:
                        asset[o + (pl // 2) * 16 + r * 2 + (pl & 1)] |= 0x80 >> c
    return clipped, w, dx, dy


def preview(path):
    sprites, pal = load_layout()
    clipped, w, dx, dy = best_fit(sprites, pal)
    img, _, _ = fit_logo(sprites, w, dx, dy)
    q = quantize(img, pal)
    cols = [bgr555_to_rgb(c) for c in pal]
    cov = coverage(sprites)
    out = Image.new('RGB', (256, 128), (230, 230, 220))
    for (x, y), v in q.items():
        if (x + dx, y + dy) in cov and x + dx < 256 and y + dy < 128:
            out.putpixel((x + dx, y + dy), cols[v])
    out.resize((512, 256), Image.NEAREST).save(path)
    return clipped, w, dx, dy
