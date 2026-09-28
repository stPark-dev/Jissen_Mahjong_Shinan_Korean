"""Log LZ asset decompressions ($00:9691, table reads at $0A:8002,X) and VRAM DMAs in order."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))


def asset_events(emu, step):
    emu.trace(read=(0x0A8000, 0x0A8337))
    step(emu)
    out = []
    last = None
    for x in emu.events():
        if x.kind == 0 and x.pbpc == 0x969F and x.val == 0x10000:
            idx = (x.addr - 0x0A8002) // 4
            out.append(('LZ', idx))
        elif x.kind == 3 and (x.val & 0xFF) in (0x18, 0x19) and not (x.val >> 12):
            out.append(('DMA', x.addr, x.extra >> 16, x.extra & 0xFFFF))
    emu.trace_off()
    return out
