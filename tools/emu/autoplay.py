"""Auto-play: press A periodically; save a screenshot + state whenever the screen
content differs strongly from every previously kept frame."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from lr import Emu


def small(frame, w, h, pitch):
    out = []
    for y in range(0, h, 8):
        row = frame[y * pitch:(y * pitch) + w * 2]
        for x in range(0, w, 8):
            v = row[2 * x] | row[2 * x + 1] << 8
            out.append(((v >> 11) & 31, (v >> 5) & 63, v & 31))
    return out


def dist(a, b):
    return sum(1 for p, q in zip(a, b) if abs(p[0] - q[0]) + abs(p[1] - q[1]) // 2 + abs(p[2] - q[2]) > 6)


def autoplay(rom, state, outdir, presses=3000, every=10, thresh=180, buttons=('A',)):
    os.makedirs(outdir, exist_ok=True)
    e = Emu(rom)
    e.load_state(open(state, 'rb').read())
    kept = []
    n = 0
    for i in range(presses):
        e.press(buttons[i % len(buttons)], 3, every)
        s = small(e.frame, e.fw, e.fh, e.pitch)
        if all(dist(s, k) > thresh for k in kept):
            kept.append(s)
            e.screenshot(os.path.join(outdir, '%04d.png' % n), 1)
            open(os.path.join(outdir, '%04d.state' % n), 'wb').write(e.save_state())
            n += 1
    return n
