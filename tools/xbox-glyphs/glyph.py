#!/usr/bin/env python3
"""Author Xbox A/B/X/Y glyph blobs for the UDC port.

build_color_blob(art_rgba, orig_blob, params) -> 46080-byte tiled blob:
encodes per-mip DXT1 (or keeps original blocks for padded slots we don't use),
lays out mips exactly like the game (mips 0-3 exact, 4-8 padded to 512B),
re-tiles with detile.Params(THIN, macro=False).
"""
import numpy as np
import detile
from PIL import Image, ImageDraw, ImageFont

# Xbox 360 face button colors
XBOX = {
    'A': ((29, 185, 84), 'A'),    # green
    'B': ((232, 61, 51), 'B'),    # red
    'X': ((41, 128, 232), 'X'),   # blue
    'Y': ((255, 205, 0), 'Y'),    # yellow
}


def _font(size):
    for p in ('/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
              '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_glyph(letter, rgb, size=256, disc=True):
    """Xbox-style prompt: colored disc + white letter + soft dark rim/shadow."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = size // 2
    r = int(size * 0.36)
    if disc:
        # soft drop shadow
        sh = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sh)
        ds.ellipse([cx-r+6, cy-r+10, cx+r+6, cy+r+10], fill=(0, 0, 0, 110))
        sh = sh.filter(__import__('PIL.ImageFilter', fromlist=['GaussianBlur']).GaussianBlur(6))
        img.alpha_composite(sh)
        # disc with vertical gradient
        grad = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        dg = ImageDraw.Draw(grad)
        top = tuple(min(255, int(c * 1.25)) for c in rgb) + (255,)
        bot = tuple(int(c * 0.72) for c in rgb) + (255,)
        dg.ellipse([cx-r, cy-r, cx+r, cy+r], fill=bot)
        mask = Image.new('L', (size, size), 0)
        ImageDraw.Draw(mask).ellipse([cx-r, cy-r, cx+r, cy+r], fill=255)
        grad2 = Image.new('RGBA', (size, size), top)
        grad = Image.composite(grad2, grad, grad.point(lambda v: v))  # base
        # vertical shade: darken lower half of the disc
        shade = Image.new('L', (size, size), 0)
        sd = ImageDraw.Draw(shade)
        sd.rectangle([0, cy, size, size], fill=70)
        shade = Image.composite(Image.new('L', (size, size), 70), Image.new('L', (size, size), 0), mask)
        dark = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        dark.putalpha(shade.point(lambda v: v if v else 0))
        grad.alpha_composite(dark)
        grad.putalpha(mask)
        img.alpha_composite(grad)
        # rim
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(0, 0, 0, 160), width=max(3, size//90))
    # letter
    f = _font(int(r * 1.5))
    bbox = d.textbbox((0, 0), letter, font=f)
    lw, lh = bbox[2]-bbox[0], bbox[3]-bbox[1]
    tx, ty = cx - lw/2 - bbox[0], cy - lh/2 - bbox[1]
    d.text((tx+2, ty+3), letter, font=f, fill=(0, 0, 0, 140))
    d.text((tx, ty), letter, font=f, fill=(255, 255, 255, 255))
    return img


# ---------------- DXT1 encoding ----------------

def _rgb565(c):
    r, g, b = c[..., 0].astype(np.uint16), c[..., 1].astype(np.uint16), c[..., 2].astype(np.uint16)
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def dxt1_encode(rgba):
    """RGBA (H,W,4), H/W %4==0 -> DXT1 block bytes (H//4*W//4*8)."""
    h, w, _ = rgba.shape
    bh, bw = h // 4, w // 4
    blocks = rgba.reshape(bh, 4, bw, 4, 4).swapaxes(1, 2).reshape(bh, bw, 16, 4)
    out = np.zeros((bh, bw, 8), dtype=np.uint8)
    opaque = (blocks[..., 3] == 255).all(axis=-1)
    # 4-color blocks: endpoints by luminance extremes
    px = blocks[..., :3].astype(np.float32)
    lum = px @ np.float32([0.299, 0.587, 0.114])
    i0 = np.argmax(lum, axis=-1)
    i1 = np.argmin(lum, axis=-1)
    ii = np.arange(bh)[:, None], np.arange(bw)[None, :]
    c0 = px[ii[0], ii[1], i0]  # brightest
    c1 = px[ii[0], ii[1], i1]  # darkest
    u0, u1 = _rgb565(c0), _rgb565(c1)
    # ensure c0 > c1 for 4-color mode (bump c1 down if equal)
    same = u0 <= u1
    u1 = np.where(same, (u1 - 1) & 0xFFFF, u1).astype(np.uint16)
    pal = np.stack([
        c0, c1,
        (2 * c0 + c1) / 3, (c0 + 2 * c1) / 3,
    ], axis=-2)  # [bh,bw,4,3]
    dist = ((px[..., None, :] - pal[..., None, :, :]) ** 2).sum(-1)  # [bh,bw,16,4]
    idx = np.argmin(dist, axis=-1).astype(np.uint8)
    # pack indices: 2 bits per pixel, one byte per block row
    packed = np.zeros((bh, bw, 4), dtype=np.uint8)
    for p in range(16):
        r_, c_ = p // 4, p % 4
        packed[:, :, r_] |= idx[:, :, p] << (2 * c_)
    out4 = np.zeros((bh, bw, 8), dtype=np.uint8)
    out4[:, :, 0] = u0 & 0xFF
    out4[:, :, 1] = u0 >> 8
    out4[:, :, 2] = u1 & 0xFF
    out4[:, :, 3] = u1 >> 8
    out4[:, :, 4:] = packed  # one byte per block row, 2 bits per pixel
    out[opaque] = out4[opaque]
    # 3-color blocks (has transparent px): c0 <= c1, index 3 = transparent
    tblocks = ~opaque
    if tblocks.any():
        tb = blocks[tblocks]
        tpx = tb[..., :3].astype(np.float32)
        distp = ((tpx[:, :, None, :] - tpx[:, None, :, :]) ** 2).sum(-1)
        flat = distp.reshape(distp.shape[0], -1)
        pair = np.argmax(flat, axis=1)
        pa, pb = pair // 16, pair % 16
        c0 = tpx[np.arange(len(tb)), pa]
        c1 = tpx[np.arange(len(tb)), pb]
        u0 = _rgb565(c0).astype(np.uint16)
        u1 = _rgb565(c1).astype(np.uint16)
        swap = u0 > u1
        u0, u1 = np.where(swap, u1, u0), np.where(swap, u0, u1)
        c0f, c1f = np.where(swap[:, None], c1, c0), np.where(swap[:, None], c0, c1)
        pal = np.stack([c0f, c1f, (c0f + c1f) / 2], axis=-2)
        dist2 = ((tpx[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1)
        alpha0 = tb[:, :, 3] == 0
        idx = np.argmin(dist2, axis=-1).astype(np.uint8)
        idx[alpha0] = 3
        packed = np.zeros((len(tb), 4), dtype=np.uint8)
        for p in range(16):
            r_, c_ = p // 4, p % 4
            packed[:, r_] |= idx[:, p] << (2 * c_)
        o = np.zeros((len(tb), 8), dtype=np.uint8)
        o[:, 0] = u0 & 0xFF
        o[:, 1] = u0 >> 8
        o[:, 2] = u1 & 0xFF
        o[:, 3] = u1 >> 8
        o[:, 4:] = packed
        out[tblocks] = o
    return out.reshape(-1).tobytes()


def mip_chain(img):
    """PIL image -> [(w,h,nparray)] down to 1x1, box-filtered."""
    chain = []
    im = img
    while True:
        chain.append(np.asarray(im, dtype=np.uint8))
        if im.size == (1, 1):
            break
        nw, nh = max(im.size[0] // 2, 1), max(im.size[1] // 2, 1)
        im = im.resize((nw, nh), Image.BOX)
    return chain


def build_color_blob(art, orig_blob, p=None):
    """art: 256x256 RGBA PIL image. Returns 46080-byte tiled blob matching orig layout."""
    p = p or detile.Params(detile.THIN, macro=False)
    orig_lin = np.frombuffer(detile.detile(orig_blob, detile.U1_MIPS, p),
                             dtype=np.uint8).copy()
    chain = mip_chain(art)
    # mip block dims: pw blocks, ph blocks, region offset, region size
    dims = detile.mip_block_dims(detile.U1_MIPS)
    for mip, arr in enumerate(chain):
        pw, ph, off, rsize = dims[mip]
        bw, bh = (arr.shape[1] + 3) // 4, (arr.shape[0] + 3) // 4
        enc = dxt1_encode(arr) if (bw * 4 == arr.shape[1] and bh * 4 == arr.shape[0]) else None
        if enc is None:  # pad to block multiple (tiny mips)
            pad = np.zeros((bh * 4, bw * 4, 4), dtype=np.uint8)
            pad[:arr.shape[0], :arr.shape[1]] = arr
            enc = dxt1_encode(pad)
        nblocks = bw * ph  # row stride in the mip grid is pw blocks
        lin = np.frombuffer(enc, dtype=np.uint8).reshape(bh, bw, 8)
        grid = np.frombuffer(orig_lin[off:off + rsize], dtype=np.uint8).reshape(rsize // 8 // pw, pw, 8).copy()
        grid[:bh, :bw] = lin
        orig_lin[off:off + rsize] = grid.reshape(-1)
    return detile.tile(orig_lin.tobytes(), detile.U1_MIPS, p)


if __name__ == '__main__':
    import sys
    art = draw_glyph('A', XBOX['A'][0])
    art.save('view/glyph_A_test.png')
    print("test art saved")
