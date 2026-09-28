"""Headless libretro harness for the patched snes9x core (tools/emu/setup.sh).

Provides frame stepping, scripted joypad input, screenshots, save states,
memory access and the kr_trace read/write/exec/DMA event log.
"""
import ctypes as C
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORE = os.path.join(ROOT, '.ext', 'snes9x', 'libretro', 'snes9x_libretro.so')

# libretro joypad ids
BTN = {'B': 0, 'Y': 1, 'SELECT': 2, 'START': 3, 'UP': 4, 'DOWN': 5, 'LEFT': 6, 'RIGHT': 7,
       'A': 8, 'X': 9, 'L': 10, 'R': 11}

ENV_CB = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO_CB = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO_CB = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDIO_BATCH_CB = C.CFUNCTYPE(C.c_size_t, C.c_void_p, C.c_size_t)
POLL_CB = C.CFUNCTYPE(None)
STATE_CB = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)


class GameInfo(C.Structure):
    _fields_ = [('path', C.c_char_p), ('data', C.c_void_p), ('size', C.c_size_t), ('meta', C.c_char_p)]


class KrEvent(C.Structure):
    _fields_ = [('kind', C.c_uint32), ('pbpc', C.c_uint32), ('addr', C.c_uint32), ('val', C.c_uint32),
                ('a', C.c_uint16), ('x', C.c_uint16), ('y', C.c_uint16), ('d', C.c_uint16), ('s', C.c_uint16),
                ('db', C.c_uint8), ('p', C.c_uint8), ('ph', C.c_uint8), ('pad1', C.c_uint8), ('extra', C.c_uint32)]


KIND = {0: 'R', 1: 'W', 2: 'X', 3: 'DMA'}


class Emu:
    def __init__(self, rom_bytes, core=CORE):
        self.lib = C.CDLL(core)
        self.frame = None
        self.fw = self.fh = self.pitch = 0
        self.pad = 0
        self.frames = 0
        self._sysdir = C.c_char_p(os.path.join(ROOT, 'work').encode())
        self._cbs = [ENV_CB(self._env), VIDEO_CB(self._video), AUDIO_CB(lambda l, r: None),
                     AUDIO_BATCH_CB(lambda p, n: n), POLL_CB(lambda: None), STATE_CB(self._state)]
        L = self.lib
        L.retro_set_environment(self._cbs[0])
        L.retro_init()
        L.retro_set_video_refresh(self._cbs[1])
        L.retro_set_audio_sample(self._cbs[2])
        L.retro_set_audio_sample_batch(self._cbs[3])
        L.retro_set_input_poll(self._cbs[4])
        L.retro_set_input_state(self._cbs[5])
        self._rom = C.create_string_buffer(bytes(rom_bytes), len(rom_bytes))
        gi = GameInfo(b'game.sfc', C.cast(self._rom, C.c_void_p), len(rom_bytes), None)
        if not L.retro_load_game(C.byref(gi)):
            raise RuntimeError('retro_load_game failed')
        L.retro_get_memory_data.restype = C.c_void_p
        L.retro_get_memory_size.restype = C.c_size_t
        L.retro_serialize_size.restype = C.c_size_t
        for fn in ('retro_kr_buf', 'retro_kr_vram', 'retro_kr_cgram', 'retro_kr_oam', 'retro_kr_regs', 'retro_kr_fillram'):
            getattr(L, fn).restype = C.c_void_p
        L.retro_kr_count.restype = C.c_uint32
        L.retro_kr_set.argtypes = [C.c_uint32] * 7
        L.retro_kr_pcfilter.argtypes = [C.c_uint32] * 2

    # --- libretro callbacks ---
    def _env(self, cmd, data):
        if cmd == 9 or cmd == 31:  # GET_SYSTEM_DIRECTORY / GET_SAVE_DIRECTORY
            C.cast(data, C.POINTER(C.c_char_p))[0] = self._sysdir.value
            return True
        if cmd == 10:  # SET_PIXEL_FORMAT
            self.pixfmt = C.cast(data, C.POINTER(C.c_int))[0]
            return True
        if cmd == 3:  # GET_CAN_DUPE
            C.cast(data, C.POINTER(C.c_bool))[0] = True
            return True
        return False

    def _video(self, data, w, h, pitch):
        if data:
            self.fw, self.fh, self.pitch = w, h, pitch
            self.frame = C.string_at(data, pitch * h)

    def _state(self, port, device, index, id_):
        if port == 0 and device == 1:
            return 1 if (self.pad >> id_) & 1 else 0
        return 0

    # --- control ---
    def run(self, n=1, buttons=()):
        self.pad = 0
        for b in buttons:
            self.pad |= 1 << BTN[b]
        for _ in range(n):
            self.lib.retro_run()
            self.frames += 1
        self.pad = 0

    def press(self, button, hold=4, release=12):
        self.run(hold, (button,) if isinstance(button, str) else button)
        self.run(release)

    def save_state(self):
        n = self.lib.retro_serialize_size()
        buf = C.create_string_buffer(n)
        assert self.lib.retro_serialize(buf, n)
        return buf.raw

    def load_state(self, blob):
        buf = C.create_string_buffer(blob, len(blob))
        assert self.lib.retro_unserialize(buf, len(blob))

    # --- memory ---
    def _mem(self, kind):
        p = self.lib.retro_get_memory_data(kind)
        n = self.lib.retro_get_memory_size(kind)
        return (C.c_uint8 * n).from_address(p)

    def wram(self):
        return bytes(self._mem(2))

    def sram(self):
        return bytes(self._mem(0))

    def poke_wram(self, addr, data):
        m = self._mem(2)
        for i, b in enumerate(data):
            m[addr + i] = b

    def vram(self):
        return C.string_at(self.lib.retro_kr_vram(), 0x10000)

    def cgram(self):
        return C.string_at(self.lib.retro_kr_cgram(), 512)

    def fillram(self):
        return C.string_at(self.lib.retro_kr_fillram(), 0x8000)

    # --- tracing ---
    def trace(self, read=None, write=None, exec_=None, pc=None):
        """pc=(lo, hi) restricts logged reads/writes to instructions with PBPC in range."""
        p = pc or (0, 0xFFFFFF)
        self.lib.retro_kr_pcfilter(p[0], p[1])
        r = read or (1, 0)
        w = write or (1, 0)
        x = exec_ or (1, 0)
        self.lib.retro_kr_clear()
        self.lib.retro_kr_set(r[0], r[1], w[0], w[1], x[0], x[1], 1)

    def trace_off(self):
        self.lib.retro_kr_set(1, 0, 1, 0, 1, 0, 0)

    def dma_log(self, on=True):
        # DMA events are logged whenever tracing is on; empty ranges keep other kinds quiet
        self.lib.retro_kr_clear()
        self.lib.retro_kr_set(1, 0, 1, 0, 1, 0, 1 if on else 0)

    def events(self):
        n = self.lib.retro_kr_count()
        arr = (KrEvent * n).from_address(self.lib.retro_kr_buf())
        return [arr[i] for i in range(n)]

    # --- screenshot ---
    def screenshot(self, path, scale=2):
        from PIL import Image
        w, h, pitch = self.fw, self.fh, self.pitch
        im = Image.new('RGB', (w, h))
        px = im.load()
        f = self.frame
        for y in range(h):
            row = f[y * pitch:y * pitch + w * 2]
            for x in range(w):
                v = row[2 * x] | row[2 * x + 1] << 8
                px[x, y] = ((v >> 11) << 3, ((v >> 5) & 63) << 2, (v & 31) << 3)
        if scale != 1:
            im = im.resize((w * scale, h * scale), Image.NEAREST)
        im.save(path)
        return im


def load_rom(path=None):
    path = path or os.path.join(ROOT, 'Jissen! Mahjong Shinan (Japan).sfc')
    with open(path, 'rb') as f:
        return f.read()
