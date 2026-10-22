#!/usr/bin/env python3
"""Regenerate the BB_TEXREPLACE .urpl atlases (Xbox button glyphs).

The 512x512 UI atlas used by the trilogy is stored UPRIGHT in guest memory
(readable OPTIONS/SHARE labels, triangle pointing up), so the Xbox letters are
drawn upright here.  (The U3 *pak* textures are the flipped ones - see
u3pak_patch.py.)

  - 0000001151a64000.urpl  U1 collection-screen / in-game UI atlas
  - 0000001153798000.urpl  U2 UI atlas
  - 0000001150228000.urpl  U3 shared UI atlas *colour* half (the U3 HUD keeps
    colour and alpha in two textures; 0x1150338000 is the mask, left alone)

Two modes:

  default        redraw only the four face cells on top of the art already in
                 the .urpl files (fast, idempotent - keeps the label pass that
                 is baked into them)
  --from-dump D  rebuild from a pristine BB_TEXDUMP directory: the original
                 512x512 atlas dump is decoded, the PS labels are replaced by
                 the Xbox ones (LABELS table) and the face cells are redrawn.
                 This is what a fresh clone needs - run the game once unmodded
                 with BB_TEXDUMP=<D> and visit the collection/menu screen.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tile32

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
MOD = pathlib.Path(os.environ.get('BB_GLYPH_MOD_DIR') or REPO / 'mods/uncharted-xbox-glyphs')
MODDIR = str(MOD / 'texreplace')
VIEW = os.environ.get('BB_VIEW_DIR') or str(pathlib.Path.home() / 'psarc-lab/view/bbmod')
CELLS = [(5, 59), (69, 126), (133, 187), (197, 251)]
LETTERS = ['B', 'X', 'Y', 'A']
COLORS = [(208, 74, 66), (75, 123, 209), (232, 193, 60), (109, 185, 64)]
R = 26


def font(size):
    for p in ('/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf',
              '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_cell(img, cx, cy, letter, col):
    d = ImageDraw.Draw(img)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(32, 32, 34, 255))
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(0, 0, 0, 220), width=2)
    d.arc([cx - R, cy - R, cx + R, cy + R], 200, 340, fill=col + (255,), width=3)
    f = font(int(R * 1.15))
    tile = Image.new('RGBA', (int(R * 2.6), int(R * 2.6)), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    bb = td.textbbox((0, 0), letter, font=f)
    lw, lh = bb[2] - bb[0], bb[3] - bb[1]
    td.text((tile.width / 2 - lw / 2 - bb[0] + 2, tile.height / 2 - lh / 2 - bb[1] + 2),
            letter, font=f, fill=(0, 0, 0, 255))
    td.text((tile.width / 2 - lw / 2 - bb[0], tile.height / 2 - lh / 2 - bb[1]),
            letter, font=f, fill=col + (255,))
    img.alpha_composite(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)))


# Original PS labels -> Xbox text.  (x0, y0, x1, y1) are the label boxes in the
# stock 512x512 atlas (identical art in all three games); the two instances of
# R2/L2, OPTIONS, SHARE and L3/R3 are listed separately.
LABELS = [
    (275, 22, 298, 37, 'RT'),     # R2 (top)
    (344, 22, 365, 37, 'LT'),     # L2 (top)
    (408, 57, 464, 70, 'MENU'),   # OPTIONS
    (447, 122, 465, 137, 'LB'),   # L1
    (369, 131, 390, 146, 'RB'),   # R1
    (19, 162, 41, 177, 'RT'),     # R2 (cap row)
    (88, 162, 108, 177, 'LT'),    # L2 (cap row)
    (412, 163, 460, 176, 'VIEW'), # SHARE
    (285, 182, 304, 195, 'LS'),   # L3 (top row)
    (358, 182, 378, 195, 'RS'),   # R3 (top row)
    (155, 197, 206, 207, 'MENU'), # OPTIONS (second)
    (162, 303, 197, 313, 'VIEW'), # SHARE (second)
    (29, 321, 47, 335, 'LS'),     # L3 (bottom row)
    (103, 321, 122, 335, 'RS'),   # R3 (bottom row)
    (112, 268, 133, 284, 'RB'),   # R1 (lower cap row)
    (190, 259, 209, 275, 'LB'),   # L1 (lower cap row)
]


def replace_labels(rgba):
    """PS label text -> Xbox label text, keeping the atlas' cream text colour."""
    from PIL import ImageFilter
    smooth = np.asarray(Image.fromarray(rgba[..., :3].astype(np.uint8), 'RGB')
                        .filter(ImageFilter.MedianFilter(15))).astype(np.int16)
    img = Image.fromarray(rgba, 'RGBA')
    done = 0
    for x0, y0, x1, y1, text in LABELS:
        arr = np.asarray(img).copy()
        rgb = arr[..., :3].astype(np.int16)
        lum = rgb.mean(-1)
        sat = rgb.max(-1) - rgb.min(-1)
        pad = 3
        cx0, cy0 = max(x0 - pad, 0), max(y0 - pad, 0)
        cx1, cy1 = min(x1 + pad, arr.shape[1]), min(y1 + pad, arr.shape[0])
        txt = (lum[cy0:cy1, cx0:cx1] > 110) & (sat[cy0:cy1, cx0:cx1] < 90)
        if txt.sum() < 8:
            print(f'  label {text} at {(x0, y0)}: no text pixels, skipped')
            continue
        col = np.median(rgb[cy0:cy1, cx0:cx1][txt], 0)
        sub = rgb[cy0:cy1, cx0:cx1].copy()
        sm = smooth[cy0:cy1, cx0:cx1]
        erase = txt.copy()
        erase[1:, :] |= txt[:-1, :]
        erase[:-1, :] |= txt[1:, :]
        erase[:, 1:] |= txt[:, :-1]
        erase[:, :-1] |= txt[:, 1:]
        sub[erase] = sm[erase]
        arr[cy0:cy1, cx0:cx1, :3] = np.clip(sub, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr, 'RGBA')
        d = ImageDraw.Draw(img)
        yy, xx = np.nonzero(txt)
        ty0, ty1 = yy.min(), yy.max() + 1
        f = font(max(int((ty1 - ty0) * 1.28), 8))
        tb = d.textbbox((0, 0), text, font=f)
        lw, lh = tb[2] - tb[0], tb[3] - tb[1]
        ccx = cx0 + (xx.min() + xx.max() + 1) / 2
        ccy = cy0 + (ty0 + ty1) / 2
        d.text((ccx - lw / 2 - tb[0], ccy - lh / 2 - tb[1]), text, font=f,
               fill=tuple(int(v) for v in col) + (255,))
        done += 1
    print(f'  labels replaced: {done}/{len(LABELS)}')
    return np.asarray(img).astype(np.uint8)


def find_dump_atlas(dumpdir):
    """Locate a pristine 512x512 RGBA atlas dump in a BB_TEXDUMP directory."""
    import glob
    for addr in ('1151a64000', '1153798000', '1150228000'):
        for p in glob.glob(os.path.join(dumpdir, f'tex_000000{addr}_512x512_*.bin')):
            d = open(p, 'rb').read()
            if len(d) >= 512 * 512 * 4:
                lin = tile32.detile(d, 512, 512, tile32.Params(tile32.THIN, macro=False))
                return tile32.to_rgba(lin, 512, 512), p
    raise SystemExit(f'no 512x512 atlas dump found in {dumpdir} - run the game once '
                     f'unmodded with BB_TEXDUMP={dumpdir} and open the collection screen')


def load_urpl(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'URPL'
    w, h = struct.unpack('<2I', d[4:12])
    lin = tile32.detile(d[12:], w, h, tile32.Params(tile32.THIN, macro=False))
    return np.frombuffer(lin, np.uint8).reshape(h, w, 4).copy()


def save_urpl(path, rgba):
    h, w, _ = rgba.shape
    tiled = tile32.tile(np.ascontiguousarray(rgba).tobytes(), w, h,
                        tile32.Params(tile32.THIN, macro=False))
    with open(path, 'wb') as f:
        f.write(b'URPL' + struct.pack('<2I', w, h) + tiled)
        f.flush()
        os.fsync(f.fileno())


def fix_atlas(rgba, cy):
    img = Image.fromarray(rgba, 'RGBA')
    for (x0, x1), letter, col in zip(CELLS, LETTERS, COLORS):
        draw_cell(img, (x0 + x1) // 2, cy, letter, col)
    return np.asarray(img).astype(np.uint8)


def preview(rgba, name):
    bg = Image.new('RGBA', (512, 512), (90, 25, 15, 255))
    bg.alpha_composite(Image.fromarray(rgba, 'RGBA'))
    bg.convert('RGB').save(f'{VIEW}/{name}.png')


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--from-dump', metavar='DIR', default='',
                    help='pristine BB_TEXDUMP directory: rebuild from scratch (labels + cells)')
    ap.add_argument('--preview', action='store_true', help='render only, do not write')
    args = ap.parse_args()
    os.makedirs(VIEW, exist_ok=True)
    base = None
    if args.from_dump:
        base, src = find_dump_atlas(args.from_dump)
        base = replace_labels(base)
        print(f'base atlas: {src}')
    out = {}
    for addr, cy, tag in (('0000001151a64000', 103, 'u1'),
                          ('0000001153798000', 108, 'u2')):
        p = f'{MODDIR}/{addr}.urpl'
        art = fix_atlas(base.copy() if base is not None else load_urpl(p), cy)
        out[tag] = art
        preview(art, f'atlas_{tag}_upright' + ('_fromdump' if base is not None else ''))
        if args.preview:
            print(f'{tag}: preview only')
        else:
            save_urpl(p, art)
            print(f'{tag}: {p} written')
    # U3 shares the very same art; its HUD keeps alpha in a separate texture.
    # Kept in a u3-only dir so the key cannot affect U1/U2 (run.sh exports
    # "mods/texreplace:mods/texreplace/u3" for u3).
    os.makedirs(f'{MODDIR}/u3', exist_ok=True)
    p3 = f'{MODDIR}/u3/0000001150228000.urpl'
    if not args.preview:
        save_urpl(p3, out['u1'])
        print(f'u3: {p3} written')


if __name__ == '__main__':
    main()
