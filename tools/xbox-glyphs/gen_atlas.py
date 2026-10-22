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

The label pass (PS -> Xbox letters) is inherited from the current .urpl files;
only the four face-button cells are redrawn (with upright letters).
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
    os.makedirs(VIEW, exist_ok=True)
    out = {}
    for addr, cy, tag in (('0000001151a64000', 103, 'u1'),
                          ('0000001153798000', 108, 'u2')):
        p = f'{MODDIR}/{addr}.urpl'
        art = fix_atlas(load_urpl(p), cy)
        out[tag] = art
        save_urpl(p, art)
        preview(art, f'atlas_{tag}_upright')
        print(f'{tag}: {p} written')
    # U3 shares the very same art; its HUD keeps alpha in a separate texture.
    # Kept in a u3-only dir so the key cannot affect U1/U2 (run.sh exports
    # "mods/texreplace:mods/texreplace/u3" for u3).
    os.makedirs(f'{MODDIR}/u3', exist_ok=True)
    p3 = f'{MODDIR}/u3/0000001150228000.urpl'
    save_urpl(p3, out['u1'])
    preview(out['u1'], 'atlas_u3_upright')
    print(f'u3: {p3} written')


if __name__ == '__main__':
    main()
