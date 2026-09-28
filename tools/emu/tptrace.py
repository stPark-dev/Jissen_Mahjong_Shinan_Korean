"""Collect source addresses of TilePrint ($00:9A14) strings."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

FETCH_PC = 0x9A2F


def tileprint_sources(emu, step):
    emu.trace(read=(0, 0xFFFFFF), pc=(FETCH_PC, FETCH_PC), exec_=(0x9A14, 0x9A14))
    step(emu)
    starts, prev = [], None
    for x in emu.events():
        if x.kind == 2:
            prev = None
        elif x.kind == 0 and x.val == 0x10000 and x.addr not in (0x23, 0x24, 0x25):
            if prev is None or x.addr != prev + 2:
                starts.append(x.addr)
            prev = x.addr
    emu.trace_off()
    return starts
