#!/usr/bin/env python3
"""Python port of gpu/shadps4/video_core/host_shaders/tiling.comp (bbport fork).

Detile / retile PS4 (GCN) tiled surface data for 64bpp block formats (BC1/BC4,
one 8-byte block = one tiling element). Supports the shader's ARRAY_2D_TILED_THIN1
macro path (P8_32x32_16x16 / P8_32x32_8x16 / P2) and the 1D micro-tiled path,
for NUM_SAMPLES=1, MICRO_TILE_THICKNESS=1, slices=1, no PRT. Tile split never
engages for bpp=64 thin (micro tile 512B <= color tile split >= 512B).
"""
import numpy as np

MICRO_BYTES = 512  # 8x8 blocks * 8 bytes

THIN, DISPLAY = 1, 0            # micro tile modes
P2, P8_8x16, P8_16x16 = 0, 10, 12  # pipe configs


class Params:
    """macro=False -> 1D micro-tiled (bank/pipe/aspect unused)."""
    def __init__(self, micro=THIN, pipe=P8_16x16, bank_swizzle=0,
                 bank_width=1, bank_height=1, num_banks=16, aspect=1, macro=True):
        self.micro = micro
        self.pipe = pipe
        self.bank_swizzle = bank_swizzle
        self.bw = bank_width
        self.bh = bank_height
        self.nb = num_banks
        self.aspect = aspect
        self.macro = macro
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
    """Pixel number within an 8x8 micro tile; x,y arrays with coords < 8."""
    x = np.asarray(x, dtype=np.uint32)
    y = np.asarray(y, dtype=np.uint32)
    x0, x1, x2 = x & 1, (x >> 1) & 1, (x >> 2) & 1
    y0, y1, y2 = y & 1, (y >> 1) & 1, (y >> 2) & 1
    if micro == DISPLAY:  # 64bpp display order: p=x0,y0,x1,x2,y1,y2
        return x0 | (y0 << 1) | (x1 << 2) | (x2 << 3) | (y1 << 4) | (y2 << 5)
    return x0 | (y0 << 1) | (x1 << 2) | (y1 << 3) | (x2 << 4) | (y2 << 5)  # THIN


def _pipe(p, tx, ty):
    x3, x4, x5 = tx & 1, (tx >> 1) & 1, (tx >> 2) & 1
    y3, y4, y5 = ty & 1, (ty >> 1) & 1, (ty >> 2) & 1
    if p.pipe == P2:
        return x3 ^ y3
    if p.pipe == P8_8x16:
        p0, p1, p2 = x4 ^ y3 ^ x5, x3 ^ y4, x5 ^ y5
    else:  # P8_16x16
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
    else:  # 2
        b0, b1, b2, b3 = x3 ^ y3, 0, 0, 0
    bank = b0 | (b1 << 1) | (b2 << 2) | (b3 << 3)
    bank ^= p.bank_swizzle  # slice 0 -> no slice/tile-split rotation
    return bank & (p.nb - 1)


def addr_map(pw, ph, p):
    """Tiled byte address of every element of a pw x ph block-grid mip."""
    xs = np.arange(pw, dtype=np.uint32)
    ys = np.arange(ph, dtype=np.uint32)
    x, y = np.meshgrid(xs, ys)  # row-major
    total = pixel_index(x & 7, y & 7, p.micro).astype(np.uint64) * 8
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
    else:  # 1D micro tiled: slice=0
        tpr = pw // 8
        addr = (y // 8).astype(np.uint64) * tpr * MICRO_BYTES + (x // 8) * MICRO_BYTES + total
    return addr


# sidecar records: (byte offset, byte size, pitch_px, height_px)
U1_MIPS = [(0, 32768, 256, 256), (32768, 8192, 128, 128), (40960, 2048, 64, 64)] + \
          [(43008 + 512 * i, 512, 32, 32) for i in range(6)]
# mips 0-2 are shader-consistent (map fills their region exactly); mips 3-8 are
# single 8x8 micro tiles packed plainly at 512B (the shader's 256B pipe-interleave
# window shift would spill past their region, so the game can't have used it there)
U1_MIPS_MACRO = U1_MIPS[:3]


def mip_block_dims(mips):
    return [(pitch // 4, height // 4, off, size) for off, size, pitch, height in mips]


def _apply(tiled, mips, p, inverse, micro_tile_small):
    data = np.frombuffer(tiled, dtype=np.uint8)
    out = np.zeros(len(data), dtype=np.uint8)
    lanes = np.arange(8, dtype=np.uint64)
    for pw, ph, off, size in mip_block_dims(mips):
        if micro_tile_small and pw <= 8 and ph <= 8:
            idx = (pixel_index(np.arange(pw)[None, :].repeat(ph, 0),
                               np.arange(ph)[:, None].repeat(pw, 1),
                               p.micro).astype(np.uint64) * 8)
        else:
            idx = addr_map(pw, ph, p)
            if idx.max() >= size or len(np.unique(idx)) != idx.size:
                raise ValueError(f"invalid map for mip {pw}x{ph} with {p}")
        gather = off + idx[..., None] + lanes  # [ph, pw, 8] byte addresses
        if inverse:
            out[gather] = data[off:off + size].reshape(ph, pw, 8)
        else:
            out[off:off + size] = data[gather].reshape(-1)
    return out.tobytes()


def detile(tiled, mips, p, micro_tile_small=True):
    return _apply(tiled, mips, p, inverse=False, micro_tile_small=micro_tile_small)


def tile(linear, mips, p, micro_tile_small=True):
    return _apply(linear, mips, p, inverse=True, micro_tile_small=micro_tile_small)


# ---------------- BC1 (DXT1) / BC4 decoding ----------------

def dxt1_decode(linear, pw, ph):
    """pw x ph DXT1 blocks -> (ph*4, pw*4, 4) uint8 RGBA."""
    blocks = np.frombuffer(linear, dtype=np.uint8).reshape(ph, pw, 8)
    c0 = blocks[:, :, 0].astype(np.uint16) | (blocks[:, :, 1].astype(np.uint16) << 8)
    c1 = blocks[:, :, 2].astype(np.uint16) | (blocks[:, :, 3].astype(np.uint16) << 8)
    pal = np.zeros((ph, pw, 4, 3), dtype=np.uint16)
    for i, c in ((0, c0), (1, c1)):
        r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
        pal[:, :, i, 0] = (r << 3) | (r >> 2)
        pal[:, :, i, 1] = (g << 2) | (g >> 4)
        pal[:, :, i, 2] = (b << 3) | (b >> 2)
    four_color = (c0 > c1).astype(np.uint16)
    pal[:, :, 2, 0] = (2 * pal[:, :, 0, 0] + pal[:, :, 1, 0]) // 3
    pal[:, :, 2, 1] = (2 * pal[:, :, 0, 1] + pal[:, :, 1, 1]) // 3
    pal[:, :, 2, 2] = (2 * pal[:, :, 0, 2] + pal[:, :, 1, 2]) // 3
    pal[:, :, 3, 0] = (pal[:, :, 0, 0] + 2 * pal[:, :, 1, 0]) // 3
    pal[:, :, 3, 1] = (pal[:, :, 0, 1] + 2 * pal[:, :, 1, 1]) // 3
    pal[:, :, 3, 2] = (pal[:, :, 0, 2] + 2 * pal[:, :, 1, 2]) // 3
    alpha = np.where(four_color.astype(bool), 255, 0).astype(np.uint8)

    bits = ((blocks[:, :, 4:8, None] >> np.arange(8, dtype=np.uint8)[None, None, None, :]) & 1)
    bits = bits.reshape(ph, pw, 32)
    pidx = (bits[:, :, 0::2] | (bits[:, :, 1::2] << 1)).astype(np.intp)  # [ph,pw,16]
    rr = np.arange(ph)[:, None, None]
    cc = np.arange(pw)[None, :, None]
    rgb = pal[rr, cc, pidx]  # [ph,pw,16,3]
    a = np.where(pidx == 3, alpha[..., None], 255).astype(np.uint8)
    img = np.zeros((ph * 4, pw * 4, 4), dtype=np.uint8)
    for px in range(16):
        r, c = px // 4, px % 4
        img[r::4, c::4, :3] = rgb[:, :, px, :]
        img[r::4, c::4, 3] = a[:, :, px]
    return img


def bc4_decode(linear, pw, ph):
    """pw x ph BC4 blocks -> (ph*4, pw*4) uint8."""
    blocks = np.frombuffer(linear, dtype=np.uint8).reshape(ph, pw, 8)
    a0, a1 = blocks[:, :, 0].astype(np.uint16), blocks[:, :, 1].astype(np.uint16)
    pal = np.zeros((ph, pw, 8), dtype=np.uint16)
    pal[:, :, 0], pal[:, :, 1] = a0, a1
    for i in range(6):
        w0, w1 = 7 - i, 1 + i
        pal[:, :, 2 + i] = (w0 * a0 + w1 * a1) // 8
    if (a0 > a1).any():
        pal6 = np.zeros_like(pal)
        pal6[:, :, 0], pal6[:, :, 1] = a0, a1
        for i in range(6):
            w0, w1 = 5 - i, 1 + i
            pal6[:, :, 2 + i] = (w0 * a0 + w1 * a1) // 6
        pal = np.where((a0 > a1)[..., None], pal6, pal)
    bits = ((blocks[:, :, 2:8, None] >> np.arange(8, dtype=np.uint8)[None, None, None, :]) & 1)
    bits = bits.reshape(ph, pw, 48)
    code = (bits[:, :, 0::3] | (bits[:, :, 1::3] << 1) | (bits[:, :, 2::3] << 2)).astype(np.intp)
    rr = np.arange(ph)[:, None, None]
    cc = np.arange(pw)[None, :, None]
    vals = pal[rr, cc, code]  # [ph,pw,16]
    img = np.zeros((ph * 4, pw * 4), dtype=np.uint8)
    for px in range(16):
        img[px // 4::4, px % 4::4] = vals[:, :, px]
    return img


# ---------------- brute-force ----------------

def candidate_params():
    cands = []
    for micro in (THIN, DISPLAY):
        for pipe in (P8_16x16, P8_8x16, P2):
            npipes = 2 if pipe == P2 else 8
            for aspect in (1, 2, 4):
                for bw in (1, 2, 4):
                    if 8 * bw * npipes * aspect > 64:  # macro pitch must fit mip0
                        continue
                    for bh in (1, 2, 4, 8):
                        for nb in (2, 4, 8, 16):
                            if 8 * bh * nb // aspect > 64:  # macro height must fit mip0
                                continue
                            for swz in range(nb):
                                cands.append(Params(micro, pipe, swz, bw, bh, nb, aspect))
        cands.append(Params(micro, macro=False))
    return cands


def try_detile(tiled, p, mips=U1_MIPS):
    return detile(tiled, mips, p)


def brute(tiled_bytes, out_prefix, keep=8):
    import os
    from PIL import Image
    results = []
    for p in candidate_params():
        try:
            lin = detile(tiled_bytes, U1_MIPS_MACRO, p)
        except ValueError:
            continue
        zero_frac = (np.frombuffer(lin[:32768], dtype=np.uint64) == 0).mean()
        rgba = dxt1_decode(lin[:32768], 64, 64)
        tfrac = (rgba[..., 3] == 0).mean()
        results.append((tfrac, zero_frac, p, rgba))
    results.sort(key=lambda r: (-r[0], -r[1]))
    d = out_prefix + "_cands"
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.unlink(os.path.join(d, f))
    for i, (tfrac, zfrac, p, rgba) in enumerate(results[:keep]):
        path = f"{d}/{i:02d}_alpha{tfrac:.2f}_zero{zfrac:.2f}.png"
        Image.fromarray(rgba, "RGBA").save(path)
        print(f"{i}: {p}  alpha0={tfrac:.3f} zero_blk={zfrac:.3f}  {path}")
    return results
