"""Long auto-play that records every PrintString source address and every TilePrint
source, and keeps screenshots of new screens. Unknown ROM sources are reported."""
import os, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
from lr import Emu
from autoplay import small, dist


def run(rom, state, outdir, presses, every=12, thresh=180):
    os.makedirs(outdir, exist_ok=True)
    e = Emu(rom)
    e.load_state(open(state, 'rb').read())
    e.trace(read=(0, 0xFFFFFF), exec_=(0x9A14, 0x9BE8), pc=(0x9A2F, 0x9C49))
    ps, tp = {}, {}
    kept, n = [], 0
    for i in range(presses):
        e.press('A', 3, every)
        prev = None
        for x in e.events():
            if x.kind == 2:
                prev = None
                cur = 'ps' if x.pbpc == 0x9BE8 else ('tp' if x.pbpc == 0x9A14 else None)
                if cur:
                    e._cur = cur
                continue
            if x.kind == 0 and x.val == 0x10000 and x.addr not in (0x23, 0x24, 0x25):
                d = ps if x.pbpc == 0x9C49 else (tp if x.pbpc == 0x9A2F else None)
                if d is not None and (prev is None or x.addr != prev + 2):
                    d[x.addr] = d.get(x.addr, 0) + 1
                prev = x.addr
        e.lib.retro_kr_clear()
        s = small(e.frame, e.fw, e.fh, e.pitch)
        if all(dist(s, k) > thresh for k in kept):
            kept.append(s)
            e.screenshot(os.path.join(outdir, '%04d.png' % n), 1)
            open(os.path.join(outdir, '%04d.state' % n), 'wb').write(e.save_state())
            n += 1
    return ps, tp, n
