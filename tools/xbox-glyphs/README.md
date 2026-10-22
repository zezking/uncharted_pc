# Xbox button-glyph mod — build tools

The mod swaps the PS4 button prompts (cross / circle / square / triangle,
L1/R1/L2/R2, OPTIONS/SHARE) for Xbox ones (A/B/X/Y, LB/RB/LT/RT, MENU/VIEW)
in all three games of the Uncharted: The Nathan Drake Collection port.

Everything here is a *generator*: it reads the unmodified game paks and writes
the mod into `mods/uncharted-xbox-glyphs/`. No game file is ever modified, and
no game data is in this repository.

## How the mod is applied (two layers)

| layer | what it covers | mechanism |
|---|---|---|
| patched pak copies in `mods/uncharted-xbox-glyphs/<game>data/.../pak` | in-game prompts, pressed states, shoulder caps | the port's loose-file mod overlay (`scripts/mods.py`, `mods.json`) |
| `mods/uncharted-xbox-glyphs/texreplace/*.urpl` | the 512x512 UI atlas: collection/menu screens, OPTIONS/SHARE labels, small inline icons | `BB_TEXREPLACE` — `.urpl` bytes are written into guest memory when that texture is uploaded (`gpu/shadps4/video_core/texture_cache/texture_cache.cpp`) |

**Orientation matters and differs per layer** — this is the whole trick:

- the 512 atlas is stored **upright** (its labels read normally in a dump), so
  its letters are drawn upright;
- the pak button art is stored **vertically flipped** (the stock art has the
  triangle pointing down and the shoulder labels mirrored), so its letters are
  drawn mirrored and come out upright on screen.

## Using the mod

```bash
# normal launch - the mod is picked up automatically
bash /path/to/uncharted/uncharted.sh u1      # or u2 / u3
```

- Enable/disable the pak half: `mods.json` → `"disabled": ["uncharted-xbox-glyphs"]`.
- Disable everything (pak overlay *and* texture replacement): `BB_MODS_ENABLED=0`.
- What actually fired is logged to `<port>/user/texreplace.log`
  (`loaded N replacement(s) from ...`, `patched <addr> <w>x<h>`).

## Rebuilding

```bash
pip install numpy pillow          # only requirements
export BB_GAME_ROOT=/run/media/.../CUSA02320/Image0     # folder with eboot.bin
python3 pakpatch.py --game all --write                 # the three overlay paks
python3 gen_atlas.py                                   # the .urpl atlases
```

`pakpatch.py --game u1 --preview` renders before/after images instead of
writing, which is the fast way to tune the art. `--only <substring>` limits it
to one texture.

Environment variables (all optional):

| var | default | meaning |
|---|---|---|
| `BB_PORT_DIR` | two levels up from this file | port checkout |
| `BB_GAME_ROOT` | `$BB_PORT_DIR/../game/CUSA02320/Image0` | game dump |
| `BB_GLYPH_MOD_DIR` | `$BB_PORT_DIR/mods/uncharted-xbox-glyphs` | mod output |
| `BB_LAB` | `~/psarc-lab` | folder with pristine `*.pak.orig` backups; falls back to the game paks if absent |
| `BB_VIEW_DIR` | `$BB_LAB/view/...` | preview / render output |

Caveat: `gen_atlas.py` redraws the four face cells on top of the art already in
the `.urpl` files, because the PS→Xbox label pass (OPTIONS→MENU, SHARE→VIEW,
R1→RB, …) was applied to the atlases once by hand. Rebuilding the atlas from a
texdump of the original game is possible but needs that label pass redone.

## Files

| file | purpose |
|---|---|
| `pakpatch.py` | rebuilds the three overlay paks (pak texture scan + flip-aware art) |
| `gen_atlas.py` | rebuilds the `.urpl` UI atlases |
| `pakenum.py` | ND big2/big3 `.pak` texture descriptor scanner |
| `tile32.py` | PS4 tiling / `.urpl` codec for 32 bpp surfaces |
| `detile.py` | PS4 tiling + DXT1/BC4 decoders for block-compressed textures |
| `glyph.py` | DXT1 encoder, mip chains, pak blob builder |
| `nd_pak.py`, `nd_psarc.py`, `psarc.py` | container readers (research helpers) |
| `drive_menu.sh`, `drive_ingame.sh` | pad-file drivers for unattended texdumps |
| `HANDOFF.md` | full write-up: formats, addresses, dead ends, verification steps |

## Legal

These tools contain no game data. The generated mod does (re-encoded game art),
so it is gitignored and must not be redistributed — rebuild it locally from your
own copy of the game.
