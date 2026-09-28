"""LZ codec used by $00:9691 (asset table at $0A:8000 / file 0x50000).

Stream: u16le size, u16 (ignored), then commands until `size` bytes are produced:
  c < 0x80           literal: copy c+1 bytes
  c >= 0x80, d       match:   dist = (((c & 0x7F) << 8) | d) >> 4, len = (d & 0x0F) + 3,
                              copy byte-by-byte from out[-dist] (overlap allowed, MVN semantics)
Source reads that pass $xx:FFFF continue at the next LoROM bank ($8000), which is
contiguous in file offsets.
"""

TABLE = 0x50000


def entry_offset(rom, idx):
    o = TABLE + idx * 4
    return TABLE + int.from_bytes(rom[o:o + 4], 'big')


def entry_count(rom):
    first = entry_offset(rom, 0)
    return (first - TABLE) // 4


def decompress(rom, off):
    """Return (data, end_offset)."""
    size = rom[off] | rom[off + 1] << 8
    p = off + 4
    out = bytearray()
    while len(out) < size:
        c = rom[p]
        p += 1
        if c < 0x80:
            n = c + 1
            out += rom[p:p + n]
            p += n
        else:
            d = rom[p]
            p += 1
            dist = (((c & 0x7F) << 8) | d) >> 4
            n = (d & 0x0F) + 3
            if dist == 0 or dist > len(out):
                raise ValueError('bad distance %d at %x' % (dist, p))
            for _ in range(n):
                out.append(out[-dist])
    if len(out) != size:
        raise ValueError('overrun: %d > %d' % (len(out), size))
    return bytes(out), p


def compress(data, word2=b'\x00\x00'):
    """Greedy LZ encoder producing a stream decodable by `decompress`."""
    data = bytes(data)
    n = len(data)
    out = bytearray((n & 0xFF, n >> 8)) + bytearray(word2)
    lit = bytearray()
    i = 0
    maxd, maxl = 0x7FF, 18

    def flush():
        while lit:
            chunk = lit[:0x80]
            out.append(len(chunk) - 1)
            out.extend(chunk)
            del lit[:len(chunk)]

    # index of 3-byte prefixes -> recent positions
    heads = {}
    while i < n:
        best_l = best_d = 0
        if i + 3 <= n:
            key = data[i:i + 3]
            for j in reversed(heads.get(key, [])):
                d = i - j
                if d > maxd:
                    break
                l = 0
                while l < maxl and i + l < n and data[j + l] == data[i + l]:
                    l += 1
                if l > best_l:
                    best_l, best_d = l, d
                    if l == maxl:
                        break
        if best_l >= 3:
            flush()
            v = (best_d << 4) | (best_l - 3)
            out.append(0x80 | (v >> 8))
            out.append(v & 0xFF)
            step = best_l
        else:
            lit.append(data[i])
            step = 1
        for k in range(i, min(i + step, n - 2)):
            heads.setdefault(data[k:k + 3], []).append(k)
            lst = heads[data[k:k + 3]]
            if len(lst) > 64:
                del lst[:len(lst) - 64]
        i += step
    flush()
    return bytes(out)
