#!/usr/bin/env python3
"""Uncharted trilogy button-glyph pak patcher: PS4 symbols -> Xbox.

All three games keep their HUD button art in ONE pak and sample it with a
vertically flipped V (proof: the stock art stores the triangle pointing down
and the shoulder labels as flipped text - "L1" is stored as "Γ1").  The
runtime-composited 512x512 atlas is stored upright instead (see gen_atlas.py),
so pak art must be drawn MIRRORED TOP-BOTTOM and atlas art upright.

Paks:
  u1  u1data/build/main/pak19/ps4/particle.pak
  u2  u2data/build/main/pak22/ps4/hud.pak
  u3  u3data/build/main/pak23/ps4/hud.pak
Output: the loose-file mod overlay (mods/uncharted-xbox-glyphs/...), so the
game paks stay pristine.

Usage:
  python3 pakpatch.py --game u1 --preview   # before/after renders
  python3 pakpatch.py --game all --write    # rebuild the overlay paks
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detile
import pakenum

# Paths: override with env vars; defaults assume the script sits in
# <port>/tools/xbox-glyphs/ next to the port checkout.
import pathlib
_HERE = pathlib.Path(__file__).resolve()
def _port_dir():
    cands = [os.environ.get('BB_PORT_DIR'), _HERE.parents[2], _HERE.parent,
             pathlib.Path('/run/media/enzez/Games/uncharted-pc/uncharted_pc')]
    for c in cands:
        if c and (pathlib.Path(c) / 'mods').is_dir():
            return pathlib.Path(c)
    return pathlib.Path(cands[0] or '.')

REPO = _port_dir()
GAME = pathlib.Path(os.environ.get('BB_GAME_ROOT') or REPO.parent / 'game/CUSA02320/Image0')
MOD = pathlib.Path(os.environ.get('BB_GLYPH_MOD_DIR') or REPO / 'mods/uncharted-xbox-glyphs')
LAB = pathlib.Path(os.environ.get('BB_LAB') or pathlib.Path.home() / 'psarc-lab')
VIEW = pathlib.Path(os.environ.get('BB_VIEW_DIR') or LAB / 'view/pakpatch')

GAMES = {
    'u1': dict(pak=f'{GAME}/u1data/build/main/pak19/ps4/particle.pak',
               out=f'{MOD}/u1data/build/main/pak19/ps4/particle.pak',
               pristine=f'{LAB}/particle.pak.orig'),
    'u2': dict(pak=f'{GAME}/u2data/build/main/pak22/ps4/hud.pak',
               out=f'{MOD}/u2data/build/main/pak22/ps4/hud.pak',
               pristine=f'{LAB}/u2_hud.pak.orig'),
    'u3': dict(pak=f'{GAME}/u3data/build/main/pak23/ps4/hud.pak',
               out=f'{MOD}/u3data/build/main/pak23/ps4/hud.pak',
               pristine=f'{LAB}/u3_hud.pak.orig'),
}

P1D = detile.Params(detile.THIN, macro=False)

# Xbox colours used by the rest of the mod
XB = {
    'A': (109, 185, 64),
    'B': (208, 74, 66),
    'X': (75, 123, 209),
    'Y': (232, 193, 60),
}


def font(size, serif=False):
    names = ('/usr/share/fonts/dejavu/DejaVuSerif.ttf' if serif else
             '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
             '/usr/share/fonts/TTF/DejaVuSerif.ttf' if serif else
             '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
             '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf' if serif else
             '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    for p in names:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ---------------- pak mip layout / codec ----------------

def mip_layout(w, h, nmips):
    """(off, region, tile_w, tile_h, mw, mh) per mip.

    The game pads every mip below 512 bytes to a 32x32 pixel (8x8 block) tile;
    the real mip content sits in its top-left corner.
    """
    mips, off = [], 0
    for m in range(nmips):
        mw, mh = max(w >> m, 1), max(h >> m, 1)
        exact = ((mw + 3) // 4) * ((mh + 3) // 4) * 8
        if exact <= 512:
            region, tw, th = 512, 32, 32
        else:
            region, tw, th = exact, mw, mh
        mips.append((off, region, tw, th, mw, mh))
        off += region
    return mips


def decode(blob, w, h, nmips):
    mips = [(off, region, tw, th) for off, region, tw, th, _mw, _mh in mip_layout(w, h, nmips)]
    lin = detile.detile(blob, mips, P1D)
    return detile.dxt1_decode(lin[:mips[0][1]], w // 4, h // 4)


def encode(rgba, w, h, nmips):
    import glyph
    layout = mip_layout(w, h, nmips)
    lin = bytearray(sum(m[1] for m in layout))
    img = Image.fromarray(rgba, 'RGBA')
    for m, (off, region, tw, th, mw, mh) in enumerate(layout):
        cur = img if m == 0 else img.resize((mw, mh), Image.BOX)
        arr = np.asarray(cur, dtype=np.uint8)
        bw, bh = (mw + 3) // 4, (mh + 3) // 4
        if arr.shape[0] != bh * 4 or arr.shape[1] != bw * 4:
            pad = np.zeros((bh * 4, bw * 4, 4), dtype=np.uint8)
            pad[:arr.shape[0], :arr.shape[1]] = arr
            arr = pad
        block = np.frombuffer(glyph.dxt1_encode(arr), dtype=np.uint8).reshape(bh, bw, 8)
        stride = tw // 4
        grid = np.frombuffer(bytes(region), dtype=np.uint8).reshape(region // 8 // stride, stride, 8).copy()
        if bh > grid.shape[0]:
            raise RuntimeError(f'mip {m}: {bw}x{bh} blocks do not fit {tw}x{th}')
        grid[:bh, :bw] = block
        lin[off:off + region] = grid.reshape(-1).tobytes()
    mips = [(off, region, tw, th) for off, region, tw, th, _mw, _mh in layout]
    return detile.tile(bytes(lin), mips, P1D)


# ---------------- image helpers ----------------

def flood(mat):
    """Mask of pixels reachable from the border through `mat`."""
    out = np.zeros_like(mat)
    out[0, :] = mat[0, :]
    out[-1, :] = mat[-1, :]
    out[:, 0] = mat[:, 0]
    out[:, -1] = mat[:, -1]
    while True:
        n = out.copy()
        n[1:, :] |= out[:-1, :]
        n[:-1, :] |= out[1:, :]
        n[:, 1:] |= out[:, :-1]
        n[:, :-1] |= out[:, 1:]
        n &= mat
        if np.array_equal(n, out):
            return out
        out = n


def inpaint(rgb, mask, valid=None, iters=600):
    """Fill `mask` pixels from their unmasked, valid 4-neighbours (mean diffusion)."""
    img = rgb.astype(np.float32).copy()
    todo = mask.copy()
    ok_all = ~mask if valid is None else (valid & ~mask)
    for _ in range(iters):
        if not todo.any():
            break
        acc = np.zeros_like(img)
        cnt = np.zeros(img.shape[:2], np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            src = np.roll(img, (dy, dx), (0, 1))
            ok = np.roll(ok_all, (dy, dx), (0, 1))
            acc += src * ok[..., None]
            cnt += ok
        fill = todo & (cnt > 0)
        img[fill] = acc[fill] / cnt[fill][:, None]
        todo &= ~fill
        ok_all |= fill
    return img


def erode(mask, iters=1):
    m = mask.copy()
    for _ in range(iters):
        n = m.copy()
        n[1:, :] &= m[:-1, :]
        n[:-1, :] &= m[1:, :]
        n[:, 1:] &= m[:, :-1]
        n[:, :-1] &= m[:, 1:]
        m = n
    return m


def dilate(mask, iters=1):
    m = mask.copy()
    for _ in range(iters):
        n = m.copy()
        n[1:, :] |= m[:-1, :]
        n[:-1, :] |= m[1:, :]
        n[:, 1:] |= m[:, :-1]
        n[:, :-1] |= m[:, 1:]
        m = n
    return m


def analyse(rgba):
    """-> (matte, inside_mask, sat, lum)"""
    rgb = rgba[..., :3].astype(np.int16)
    corners = np.concatenate([rgb[:8, :8].reshape(-1, 3), rgb[:8, -8:].reshape(-1, 3),
                              rgb[-8:, :8].reshape(-1, 3), rgb[-8:, -8:].reshape(-1, 3)])
    matte = np.median(corners, 0)
    matte_like = (np.abs(rgb - matte).sum(-1) < 42)
    outside = flood(matte_like)
    inside = ~outside
    lum = rgb.mean(-1)
    sat = rgb.max(-1) - rgb.min(-1)
    return matte, inside, sat, lum


def bbox(mask):
    ys, xs = np.where(mask)
    if not len(ys):
        return None
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def trim(mask, pad=6):
    """Drop BC1 edge speckle: a few stray pixels otherwise blow up the bbox."""
    m = mask.copy()
    m[:pad] = False
    m[-pad:] = False
    m[:, :pad] = False
    m[:, -pad:] = False
    return m


def central(mask, frac=0.42):
    """Keep only the middle window (frac of the bbox size) of a mask."""
    box = bbox(mask)
    if box is None:
        return mask
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    wx, wy = max(int((x1 - x0) * frac / 2), 6), max(int((y1 - y0) * frac / 2), 6)
    m = np.zeros_like(mask)
    m[max(0, cy - wy):cy + wy, max(0, cx - wx):cx + wx] = True
    return mask & m


def draw_letter(rgba, center, height, letter, color, flip=True):
    h, w, _ = rgba.shape
    img = Image.fromarray(rgba, 'RGBA')
    d = ImageDraw.Draw(img)
    size = int(height * 1.45)
    f = font(size)
    bb = d.textbbox((0, 0), letter, font=f)
    lw, lh = bb[2] - bb[0], bb[3] - bb[1]
    tile = Image.new('RGBA', (int(lw * 2.2) + 8, int(lh * 1.4) + 8), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    ox, oy = tile.width / 2 - lw / 2 - bb[0], tile.height / 2 - lh / 2 - bb[1]
    td.text((ox + 3, oy + 3), letter, font=f, fill=(0, 0, 0, 170))
    td.text((ox, oy), letter, font=f, fill=tuple(int(c) for c in color) + (255,))
    if flip:
        tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
    img.alpha_composite(tile, (int(center[0] - tile.width / 2), int(center[1] - tile.height / 2)))
    return np.asarray(img).astype(np.uint8)


def smooth_erase(rgba, inside, passes=3, msize=25, thresh=20):
    """Replace glyph pixels with a median-filtered version of the same area.

    The prompts are glossy gradients, so the local median gives a seamless
    fill; thin glyph strokes are exactly what a median removes, so the
    |orig - median| difference localises them even when they are dark."""
    from PIL import ImageFilter
    base = Image.fromarray(rgba[..., :3].astype(np.uint8), 'RGB')
    smooth = np.asarray(base.filter(ImageFilter.MedianFilter(msize))).astype(np.int16)
    out = rgba[..., :3].astype(np.int16).copy()
    killed = np.zeros(inside.shape, bool)
    for _ in range(passes):
        diff = np.abs(out - smooth).sum(-1)
        sat = out.max(-1) - out.min(-1)
        g = inside & ((diff > thresh) | (sat > 40) | (out.mean(-1) > 150))
        g = dilate(g, 1) & inside & ~killed
        if not g.any():
            break
        out[g] = smooth[g]
        killed |= g
    return np.clip(out, 0, 255).astype(np.uint8)


def paint_shape(out, inside, color, arc=True):
    """Redraw the colored rim highlight so the disc reads as a button."""
    x0, y0, x1, y1 = bbox(inside)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2 - 2, (y1 - y0) / 2 - 2
    img = Image.fromarray(out, 'RGBA')
    d = ImageDraw.Draw(img)
    if arc:
        w = max(2, int(min(rx, ry) * 0.10))
        d.arc([cx - rx, cy - ry, cx + rx, cy + ry], 205, 335,
              fill=tuple(int(c) for c in color) + (235,), width=w)
    return img


def patch_face(rgba, letter, arc=True):
    matte, inside, sat, lum = analyse(rgba)
    inside = trim(inside, 3)
    rgb = smooth_erase(rgba, erode(inside, 5))
    out = rgba.copy()
    out[..., :3] = rgb
    img = paint_shape(out, inside, XB[letter], arc)
    x0, y0, x1, y1 = bbox(inside)
    H = 0.60 * min(x1 - x0, y1 - y0)
    return draw_letter(np.asarray(img).astype(np.uint8), ((x0 + x1) / 2, (y0 + y1) / 2),
                       H, letter, XB[letter])


def patch_cap(rgba, letter):
    return patch_face(rgba, letter, arc=False)


def patch_label(rgba, text):
    """Replace a cap's PS label ("L1"/"R2") with the Xbox one.

    The caps are vertical gradients, so a per-row median of the cap pixels is
    a text-free shading model.  The label area is a fixed centred rectangle:
    its whole footprint is repainted with the model (no ghost strokes), and
    the new label is drawn in the colour sampled from the old glyphs
    (dark-on-light in U1/U2, light-on-dark in U3), mirrored so it reads
    upright in game."""
    h, w, _ = rgba.shape
    matte, inside, sat, lum = analyse(rgba)
    inside = trim(inside)
    x0, y0, x1, y1 = bbox(inside)
    w_i, h_i = x1 - x0, y1 - y0
    profile = np.zeros((h, 3), np.float32)
    for y in range(y0, y1):
        row = rgba[y, :, :3][inside[y]]
        if len(row):
            profile[y] = np.median(row, 0)
    ker = np.ones(9, np.float32) / 9
    for c in range(3):
        p = np.convolve(profile[:, c], ker, mode='same')
        p[:y0] = profile[:y0, c]
        p[y1:] = profile[y1:, c]
        profile[:, c] = p
    model = np.repeat(profile[:, None, :], w, axis=1)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    hw, hh = int(w_i * 0.34), int(h_i * 0.30)
    rect = np.zeros((h, w), bool)
    rect[max(cy - hh, 0):cy + hh, max(cx - hw, 0):cx + hw] = True
    rect &= inside
    lum_o = rgba[..., :3].astype(np.float32).mean(-1)
    lum_m = model.mean(-1)
    dark = rect & (lum_o < lum_m - 45)
    bright = rect & (lum_o > lum_m + 45)
    txt = dark if dark.sum() >= bright.sum() else bright
    if txt.sum() > 30:
        col = np.median(rgba[..., :3][txt], 0)
    else:  # no glyph found: pick a contrasting colour from the cap
        base = np.median(rgba[..., :3][rect], 0)
        col = np.array([20, 20, 20]) if base.mean() > 110 else np.array([235, 232, 215])
    # feathered replacement so the repaint has no visible rectangle edge
    from PIL import ImageFilter
    feather = Image.fromarray((rect * 255).astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(4))
    a = (np.asarray(feather).astype(np.float32) / 255.0)[..., None]
    out = rgba.copy()
    rgb = rgba[..., :3].astype(np.float32) * (1 - a) + model * a
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    img = Image.fromarray(out, 'RGBA')
    d = ImageDraw.Draw(img)
    th = max(int(h_i * 0.38), 8)
    f = font(th, serif=True)
    bb = d.textbbox((0, 0), text, font=f)
    lw, lh = bb[2] - bb[0], bb[3] - bb[1]
    tile = Image.new('RGBA', (int(lw * 2) + 8, int(lh * 2) + 8), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    ox, oy = tile.width / 2 - lw / 2 - bb[0], tile.height / 2 - lh / 2 - bb[1]
    td.text((ox, oy), text, font=f, fill=tuple(int(c) for c in col) + (255,))
    tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
    img.alpha_composite(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)))
    return np.asarray(img).astype(np.uint8)


# basename -> (kind, replacement); matched against the texture name tail
PATCH = {
    'x-button-color.tga': ('face', 'A'),
    'circle-button-color.tga': ('face', 'B'),
    'square-button-color.tga': ('face', 'X'),
    'triangle-button-color.tga': ('face', 'Y'),
    'circle-button-up.tga': ('cap', 'B'),
    'circle-button-down.tga': ('cap', 'B'),
    'square-button-up.tga': ('cap', 'X'),
    'square-button-down.tga': ('cap', 'X'),
    'triangle-button-UP.tga': ('cap', 'Y'),
    'triangle-button-DOWN.tga': ('cap', 'Y'),
    'L1-button.tga': ('label', 'LB'),
    'L2-button.tga': ('label', 'LT'),
    'R1-button.tga': ('label', 'RB'),
    'R2-button.tga': ('label', 'RT'),
}


def entries_for(ents, basename):
    """All pak entries whose name ends with `basename` (duplicates exist)."""
    return [e for e in ents if e['name'].endswith('/' + basename) or e['name'] == basename]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', default='u3', help='u1|u2|u3|all')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--preview', action='store_true')
    ap.add_argument('--only', default='')
    args = ap.parse_args()
    games = list(GAMES) if args.game == 'all' else [args.game]
    os.makedirs(VIEW, exist_ok=True)
    for g in games:
        cfg = GAMES[g]
        ents, base, dsize, total = pakenum.scan_fast(str(cfg['pak']))
        pristine = cfg['pristine'] if os.path.exists(cfg['pristine']) else cfg['pak']
        data = open(pristine, 'rb').read()
        src = open(cfg['pak'], 'rb').read()
        if src != data:
            print(f'{g}: NOTE game pak differs from {os.path.basename(pristine)} - patching from {os.path.basename(pristine)}')
        out = bytearray(data)
        done = 0
        for basename, (kind, repl) in PATCH.items():
            if args.only and args.only not in basename:
                continue
            hits = entries_for(ents, basename)
            if not hits:
                continue
            for e in hits:
                blob = data[e['file_off']:e['file_off'] + e['size']]
                rgba = decode(blob, e['w'], e['h'], e['mips'])
                try:
                    if kind == 'face':
                        art = patch_face(rgba, repl)
                    elif kind == 'cap':
                        art = patch_cap(rgba, repl)
                    else:
                        art = patch_label(rgba, repl)
                except RuntimeError as ex:
                    print(f'{g}: SKIP {e["name"]} ({ex})')
                    continue
                new = encode(art, e['w'], e['h'], e['mips'])
                assert len(new) == e['size'], (e['name'], len(new), e['size'])
                out[e['file_off']:e['file_off'] + e['size']] = new
                tag = basename.replace('.tga', '')
                if args.preview:
                    for lbl, im in (('before', rgba), ('after', art)):
                        bg = Image.new('RGBA', (im.shape[1], im.shape[0]), (128, 128, 128, 255))
                        bg.alpha_composite(Image.fromarray(im, 'RGBA'))
                        bg.convert('RGB').save(f'{VIEW}/{g}_{tag}_{lbl}.png')
                done += 1
                print(f'{g}: patched {kind:<5} {e["name"].split("/")[-1]:<28} -> {repl}')
        print(f'{g}: {done} texture(s) processed')
        if args.write:
            os.makedirs(os.path.dirname(cfg['out']), exist_ok=True)
            with open(cfg['out'], 'wb') as f:
                f.write(out)
                f.flush()
                os.fsync(f.fileno())
            print(f'{g}: wrote {cfg["out"]} ({len(out)} bytes)')


if __name__ == '__main__':
    main()
