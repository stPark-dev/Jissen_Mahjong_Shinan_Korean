"""One-shot screen survey: LZ loads with VRAM targets, layer setup, TilePrint and PrintString sources."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from lr import Emu
from assetlog import asset_events
from whodraws import layer_info
from tptrace import tileprint_sources
from strtrace import trace_strings


def survey(rom, state, seq, save=None, shot=None):
    e = Emu(rom); e.load_state(open(state, 'rb').read())
    ev = asset_events(e, lambda e: [e.press(*s) for s in seq])
    loads = []
    for i, x in enumerate(ev):
        if x[0] == 'LZ':
            d = [y for y in ev[i + 1:i + 4] if y[0] == 'DMA' and y[1] >= 0x7e0000][:1]
            loads.append((x[1], '%04x' % d[0][2] if d else '-'))
    li = layer_info(e)
    f = e.fillram()
    if save:
        open(save, 'wb').write(e.save_state())
    if shot:
        e.screenshot(shot, 1)
    e2 = Emu(rom); e2.load_state(open(state, 'rb').read())
    tp = list(dict.fromkeys(tileprint_sources(e2, lambda e: [e.press(*s) for s in seq])))
    e3 = Emu(rom); e3.load_state(open(state, 'rb').read())
    ps = list(dict.fromkeys(trace_strings(e3, [lambda e: [e.press(*s) for s in seq]])))
    return dict(loads=loads, layers=li, tm=f[0x212C], obsel=f[0x2101], tp=[hex(a) for a in tp], ps=[hex(a) for a in ps])
