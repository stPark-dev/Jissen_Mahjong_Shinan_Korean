"""Decode original 16-bit text words using data/charmap_jp.tsv."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTRL = {0xFFFC: '<FC>', 0xFFFD: '<FD>', 0xFFFE: '<BR>', 0xFFFF: '<END>'}


def load_charmap(path=os.path.join(ROOT, 'data', 'charmap_jp.tsv')):
    code2ch = {}
    for line in open(path, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        n, code, ch = line.rstrip('\n').split('\t')[:3]
        code2ch[int(code, 16)] = ch
    return code2ch


def decode_word(w, cmap):
    if w in CTRL:
        return CTRL[w]
    return cmap.get(w, '<%04X>' % w)


def read_string(rom, off, cmap):
    """Return (text, words, end_offset) for a FFFF-terminated string."""
    words = []
    while True:
        w = rom[off] | rom[off + 1] << 8
        off += 2
        words.append(w)
        if w == 0xFFFF:
            break
    return ''.join(decode_word(w, cmap) for w in words[:-1]), words, off
