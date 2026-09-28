"""Collect source addresses of strings consumed by PrintString ($00:9BE8)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from lr import Emu, load_rom

FIRST_READ_PC = 0x9C49  # PBPC after 'LDA [$23],Y' at 9C47


def string_starts(events):
    starts = []
    prev = None
    for x in events:
        if x.kind == 0 and x.pbpc == FIRST_READ_PC and x.val == 0x10000:
            a = x.addr
            if a in (0x23, 0x24, 0x25):
                continue
            if prev is None or a != prev + 2:
                starts.append(a)
            prev = a
        elif x.kind == 2 and x.pbpc == 0x9BE8:
            prev = None
    return starts


def trace_strings(emu, steps):
    emu.trace(read=(0, 0xFFFFFF), exec_=(0x9BE8, 0x9BE8))
    out = []
    for fn in steps:
        fn(emu)
        out += string_starts(emu.events())
        emu.lib.retro_kr_clear()
    emu.trace_off()
    return out
