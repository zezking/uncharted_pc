#!/usr/bin/env python3
"""PS4 (GCN) tiling for 32bpp RGBA8 surfaces (BB_TEXDUMP / .urpl format).

Element = one 32-bit pixel. Micro tile = 8x8 pixels = 256 bytes, THIN order.
Supports 1D micro-tiled and 2D macro-tiled (P8/P2) layouts, matching
gpu/shadps4/video_core/host_shaders/tiling.comp.
"""
import numpy as np

MICRO_BYTES = 256  # 8x8 pixels * 4 bytes

THIN, DISPLAY = 1, 0
P2, P8_8x16, P8_16x16 = 0, 10, 12


class Params:
    def __init__(self, micro=THIN, pipe=P8_16x16, bank_swizzle=0,
                 bank_width=1, bank_height=1, num_banks=16, aspect=1, macro=True):
        self.micro, self.pipe, self.bank_swizzle = micro, pipe, bank_swizzle
        self.bw, self.bh, self.nb, self.aspect, self.macro = bank_width, bank_height, num_banks, aspect, macro
        self.npipes = 2 if pipe == P2 else 8
        self.pipe_bits = 1 if pipe == P2 else 3
        self.bank_bits = max(num_banks.bit_length() - 1, 1)

    def __repr__(self):
        m = 'THIN' if self.micro == THIN else 'DISP'
        if not self.macro:
            return f"Params(1D,{m})"
        return (f"Params({m},pipe={self.pipe},swz={self.bank_swizzle},bw={self.bw},"
                f"bh={self.bh},nb={self.nb},a={self.aspect})")


def pixel_index(x, y, micro):
    x = np.asarray(x, dtype=np.uint32)
    y = np.asarray(y, dtype=np.uint32)
    x0, x1, x2 = x & 1, (x >> 1) & 1, (x >> 2) & 1
    y0, y1, y2 = y & 1, (y >> 1) & 1, (y >> 2) & 1
    if micro == DISPLAY:
        return x0 | (y0 << 1) | (x1 << 2) | (x2 << 3) | (y1 << 4) | (y2 << 5)
    return x0 | (y0 << 1) | (x1 << 2) | (y1 << 3) | (x2 << 4) | (y2 << 5)


def _pipe(p, tx, ty):
    x3, x4, x5 = tx & 1, (tx >> 1) & 1, (tx >> 2) & 1
    y3, y4, y5 = ty & 1, (ty >> 1) & 1, (ty >> 2) & 1
    if p.pipe == P2:
        return x3 ^ y3
    if p.pipe == P8_8x16:
        p0, p1, p2 = x4 ^ y3 ^ x5, x3 ^ y4, x5 ^ y5
    else:
        p0, p1, p2 = x3 ^ y3 ^ x4, x4 ^ y4, x5 ^ y5
    return p0 | (p1 << 1) | (p2 << 2)


def _bank(p, tx, ty):
    txq = tx // (p.bw * p.npipes)
    tyq = ty // p.bh
    x3, x4, x5, x6 = txq & 1, (txq >> 1) & 1, (txq >> 2) & 1, (txq >> 3) & 1
    y3, y4, y5, y6 = tyq & 1, (tyq >> 1) & 1, (tyq >> 2) & 1, (tyq >> 3) & 1
    if p.nb == 16:
        b0, b1, b2, b3 = x3 ^ y6, x4 ^ y5 ^ y6, x5 ^ y4, x6 ^ y3
    elif p.nb == 8:
        b0, b1, b2, b3 = x3 ^ y5, x4 ^ y4 ^ y5, x5 ^ y3, 0
    elif p.nb == 4:
        b0, b1, b2, b3 = x3 ^ y4, x4 ^ y3, 0, 0
    else:
        b0, b1, b2, b3 = x3 ^ y3, 0, 0, 0
    bank = b0 | (b1 << 1) | (b2 << 2) | (b3 << 3)
    bank ^= p.bank_swizzle
    return bank & (p.nb - 1)


def addr_map(pw, ph, p):
    """Tiled byte address of every pixel of a pw x ph mip (element = 4 bytes)."""
    x, y = np.meshgrid(np.arange(pw, dtype=np.uint32),
                       np.arange(ph, dtype=np.uint32))
    total = pixel_index(x & 7, y & 7, p.micro).astype(np.uint64) * 4
    if p.macro:
        mtp = 8 * p.bw * p.npipes * p.aspect
        mth = 8 * p.bh * p.nb // p.aspect
        mtb = MICRO_BYTES * p.bw * p.bh
        tpr = pw // mtp
        if tpr > 0 and mth <= ph:
            mtx, mty = x // mtp, y // mth
            total += (mty.astype(np.uint64) * tpr + mtx) * mtb
        tri = (y // 8) % p.bh
        tci = ((x // 8) // p.npipes) % p.bw
        total += ((tri * p.bw + tci) * MICRO_BYTES).astype(np.uint64)
        pipe = _pipe(p, x // 8, y // 8).astype(np.uint64)
        bank = _bank(p, x // 8, y // 8).astype(np.uint64)
        addr = (total & 0xFF) | (pipe << np.uint64(8)) | \
               (bank << np.uint64(8 + p.pipe_bits)) | \
               ((total >> np.uint64(8)) << np.uint64(8 + p.pipe_bits + p.bank_bits))
    else:  # 1D micro tiled
        tpr = pw // 8
        addr = (y // 8).astype(np.uint64) * tpr * MICRO_BYTES + (x // 8) * MICRO_BYTES + total
    return addr


def _apply(tiled, w, h, p, inverse, small_plain=False):
    data = np.frombuffer(tiled, dtype=np.uint8)
    out = np.zeros(len(data), dtype=np.uint8)
    pw, ph = w, h
    if small_plain and pw <= 8 and ph <= 8:
        idx = pixel_index(np.arange(pw)[None, :].repeat(ph, 0),
                          np.arange(ph)[:, None].repeat(pw, 1), p.micro).astype(np.uint64) * 4
    else:
        idx = addr_map(pw, ph, p)
    gather = idx[..., None] + np.arange(4, dtype=np.uint64)
    if inverse:
        out[gather] = data.reshape(ph, pw, 4)
    else:
        out = data[gather].reshape(-1)
    return out.tobytes()


def detile(tiled, w, h, p):
    return _apply(tiled, w, h, p, inverse=False)


def tile(linear, w, h, p):
    return _apply(linear, w, h, p, inverse=True)


def to_rgba(linear, w, h):
    return np.frombuffer(linear, dtype=np.uint8).reshape(h, w, 4).copy()


def candidate_params():
    cands = []
    for micro in (THIN, DISPLAY):
        for pipe in (P8_16x16, P8_8x16, P2):
            for aspect in (1, 2, 4):
                for bw in (1, 2, 4):
                    for bh in (1, 2, 4, 8):
                        for nb in (2, 4, 8, 16):
                            if 8 * bw * (2 if pipe == P2 else 8) * aspect > 512:
                                continue
                            if 8 * bh * nb // aspect > 512:
                                continue
                            for swz in range(nb):
                                try:
                                    p = Params(micro, pipe, swz, bw, bh, nb, aspect)
                                except Exception:
                                    continue
                                cands.append(p)
        cands.append(Params(micro, macro=False))
    return cands
