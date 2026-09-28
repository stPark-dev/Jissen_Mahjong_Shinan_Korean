"""Validate text/ko/*.tsv against text/jp/*.tsv and consumer capacity.

Usage: python3 tools/check_ko.py [GROUP ...] [--allow-missing]
Exit status 1 on any violation.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# group -> (max_lines, max_cells, exact_lines)
LAYOUT = {
    'ADV': (2, 15, False),
    'INS': (4, 13, False),
    'PRO': (5, 13, False),
    'NAM': (1, 6, True),
    'MNU': (None, None, False),   # per-string: same line count as source, cells <= source line cells
    'SYS': (None, None, False),   # same rule as MNU (in-place, fixed layout)
}
PUNCT = set(".,!?…~-()'\":/%")
DIGITS = set('0123456789')


def is_allowed(ch):
    return ch == ' ' or ch in PUNCT or ch in DIGITS or 0xAC00 <= ord(ch) <= 0xD7A3


def read_tsv(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        header = f.readline().rstrip('\n').split('\t')
        for line in f:
            if not line.strip():
                continue
            vals = line.rstrip('\n').split('\t')
            vals += [''] * (len(header) - len(vals))
            rows.append(dict(zip(header, vals)))
    return rows


def src_lines(jp):
    return [re.sub(r'<[^>]+>', 'X', l) for l in re.split(r'(?:<BR>)+', jp)]


def check_group(g, allow_missing=False, path=None):
    errs = []
    src = {r['id']: r for r in read_tsv(os.path.join(ROOT, 'text', 'jp', g + '.tsv'))}
    kp = path or os.path.join(ROOT, 'text', 'ko', g + '.tsv')
    if not os.path.exists(kp):
        return ['%s: missing file' % g] if not allow_missing else []
    ko = read_tsv(kp)
    seen = set()
    max_lines, max_cells, exact = LAYOUT[g]
    for r in ko:
        i = r['id']
        if i not in src:
            errs.append('%s: unknown id' % i)
            continue
        if i in seen:
            errs.append('%s: duplicate id' % i)
        seen.add(i)
        text = r['ko']
        if not text.strip():
            errs.append('%s: empty translation' % i)
            continue
        lines = text.split('|')
        if g in ('MNU', 'SYS'):
            sl = src_lines(src[i]['jp'])
            ml, mc = len(sl), max(len(x) for x in sl)
        else:
            ml, mc = max_lines, max_cells
        if len(lines) > ml or (exact and len(lines) != ml):
            errs.append('%s: %d lines > %d' % (i, len(lines), ml))
        for n, l in enumerate(lines):
            if len(l) > mc:
                errs.append('%s: line %d has %d cells > %d: %r' % (i, n + 1, len(l), mc, l))
            if l != l.strip() and g not in ('NAM', 'MNU', 'SYS'):
                errs.append('%s: line %d leading/trailing space' % (i, n + 1))
            bad = [c for c in l if not is_allowed(c)]
            if bad:
                errs.append('%s: unsupported chars %r' % (i, ''.join(sorted(set(bad)))))
        if r.get('status') not in ('draft', 'reviewed'):
            errs.append('%s: bad status %r' % (i, r.get('status')))
    if not allow_missing:
        for i in src:
            if i not in seen:
                errs.append('%s: not translated' % i)
    return errs


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    allow = '--allow-missing' in sys.argv
    errs = []
    if args and args[0].endswith('.tsv'):
        # part file: python3 tools/check_ko.py text/ko/parts/ADV.i03.tsv  (group = name prefix)
        g = os.path.basename(args[0]).split('.')[0]
        errs += check_group(g, True, args[0])
    else:
        for g in (args or list(LAYOUT)):
            errs += check_group(g, allow)
    for e in errs:
        print(e)
    print('%d problem(s)' % len(errs))
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    main()
