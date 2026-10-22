# Xbox button-glyph mod — Uncharted: The Nathan Drake Collection (PC port)

Replaces the PS4 controller prompts with Xbox ones in all three games:

| PS4 | Xbox | | PS4 | Xbox |
|---|---|---|---|---|
| ✕ cross | **A** (green) | | L1 / R1 | **LB / RB** |
| ○ circle | **B** (red) | | L2 / R2 | **LT / RT** |
| □ square | **X** (blue) | | OPTIONS | **MENU** |
| △ triangle | **Y** (yellow) | | SHARE | **VIEW** |
| L3 / R3 press | **LS / RS** | | | |

This directory contains the *generators*. They read your unmodified game paks
and write the mod into `mods/uncharted-xbox-glyphs/`. No game file is ever
modified, and no game data is stored in this repository — the generated mod is
gitignored and must be rebuilt locally.

---

## How the mod is applied

Two layers, both inert without the mod folder:

| layer | covers | mechanism |
|---|---|---|
| patched pak copies (`mods/uncharted-xbox-glyphs/{u1,u2,u3}data/…/pak`) | in-game prompts: face discs, pressed/unpressed caps, shoulder caps | the port's loose-file mod overlay (`scripts/mods.py`, `mods.json`) |
| `mods/uncharted-xbox-glyphs/texreplace/*.urpl` | the 512×512 UI atlas: collection/menu screens, OPTIONS/SHARE labels, inline icons | `BB_TEXREPLACE` — the `.urpl` bytes are written into guest memory when that texture is uploaded (`gpu/shadps4/video_core/texture_cache/texture_cache.cpp`) |

**The orientation differs per layer, and that is the whole trick:**

- the 512×512 atlas is stored **upright** (its labels read normally in a dump,
  the triangle points up) → letters are drawn upright;
- the pak button art is stored **vertically flipped** (the stock art points the
  triangle down and stores `L1` as "Γ1") because the UI samples it with a
  flipped V → letters are drawn mirrored and read upright on screen.

Getting this backwards is what produces "correct button, upside-down letter".

---

## Using it

```bash
bash /path/to/uncharted/uncharted.sh u1      # or u2 / u3
```

Nothing else to do — `run.sh` picks up the mod on launch. Desktop icons and the
GUI launcher use the same path.

- **Disable the pak half**: `mods.json` → `"disabled": ["uncharted-xbox-glyphs"]`.
- **Disable everything** (paks *and* texture replacement): `BB_MODS_ENABLED=0`.
- **Check what happened**: `<port>/user/texreplace.log`

  ```
  loaded 3 replacement(s) from …/texreplace:…/texreplace/u3
    0000001151a64000 512x512
    0000001153798000 512x512
    0000001150228000 512x512
  patched 0000001151a64000 512x512
  ```

---

## Rebuilding

Requirements: `python3`, `numpy`, `pillow`.

### 1. The overlay paks (in-game prompts)

```bash
export BB_GAME_ROOT=/path/to/CUSA02320/Image0     # the folder with eboot.bin
python3 tools/xbox-glyphs/pakpatch.py --game all --write
```

Reads the pristine paks (or the `*.pak.orig` copies from `$BB_LAB` if present),
patches 10 textures for U1, 11 for U2 and 14 for U3, and writes only
`mods/uncharted-xbox-glyphs/`.

### 2. The `.urpl` atlases (menus/labels)

The atlas is built by the game at runtime, so it has to be captured once from
an **unmodded** run:

```bash
mkdir -p ~/atlas-dump
BB_TEXDUMP=~/atlas-dump bash /path/to/uncharted/uncharted.sh u1
#   boot to the collection screen / main menu, then quit
python3 tools/xbox-glyphs/gen_atlas.py --from-dump ~/atlas-dump
```

That decodes the stock 512×512 atlas, swaps the PS labels (`LABELS` table in
`gen_atlas.py`), redraws the four face cells, and writes:

```
mods/uncharted-xbox-glyphs/texreplace/0000001151a64000.urpl        U1
mods/uncharted-xbox-glyphs/texreplace/0000001153798000.urpl        U2
mods/uncharted-xbox-glyphs/texreplace/u3/0000001150228000.urpl     U3 (colour half)
```

`gen_atlas.py` without `--from-dump` is the fast path: it redraws only the face
cells on top of the art already in the `.urpl` files (idempotent, handy when
tuning the glyph size/colour). Add `--preview` to render into `$BB_VIEW_DIR`
instead of writing.

U3 keeps the atlas alpha in a separate texture (`0x1150338000`); the colour
replacement keeps the same layout, so the mask still lines up.

### Tuning the art

```bash
python3 tools/xbox-glyphs/pakpatch.py --game u3 --preview            # renders only
python3 tools/xbox-glyphs/pakpatch.py --game u3 --preview --only L1  # one texture
```

Before/after images land in `$BB_VIEW_DIR`.

---

## Paths and environment

| variable | default | meaning |
|---|---|---|
| `BB_PORT_DIR` | two levels up from this file | port checkout |
| `BB_GAME_ROOT` | `$BB_PORT_DIR/../game/CUSA02320/Image0` | game dump |
| `BB_GLYPH_MOD_DIR` | `$BB_PORT_DIR/mods/uncharted-xbox-glyphs` | mod output |
| `BB_LAB` | `~/psarc-lab` | pristine `*.pak.orig` backups (falls back to the game paks) |
| `BB_VIEW_DIR` | `$BB_LAB/view/...` | preview output |

---

## Files

| file | purpose |
|---|---|
| `pakpatch.py` | rebuilds the three overlay paks (pak scan + flip-aware art, mip chains re-encoded) |
| `gen_atlas.py` | builds the `.urpl` UI atlases (label pass + face cells) |
| `pakenum.py` | ND big2/big3 `.pak` texture-descriptor scanner (`scan_fast` for 100+ MB paks) |
| `tile32.py` | PS4 tiling / `.urpl` codec for 32 bpp surfaces |
| `detile.py` | PS4 tiling + DXT1/BC4 decoders for block-compressed textures |
| `glyph.py` | DXT1 encoder, mip chains, pak blob builder |
| `nd_pak.py`, `nd_psarc.py`, `psarc.py` | container readers (research helpers) |
| `drive_menu.sh`, `drive_ingame.sh` | pad-file drivers for unattended texdumps |
| `HANDOFF.md` | deep write-up: formats, guest addresses, dead ends, verification notes |

---

## Troubleshooting

- **Nothing changed** — check `user/texreplace.log`; if it doesn't exist the
  hook never ran (stale `libbbgpu.so` — rebuild with
  `ninja -C out/gpu bbgpu`). If it lists the keys but the screen is unchanged,
  the texture you want isn't one of those addresses.
- **A prompt still shows a PS glyph** — the game serves it from another
  texture. Run with `BB_TEXDUMP=<dir>` (create the dir first), reach that
  screen, then hash-match the dumps against `pakenum.py` output to find the
  texture, and add it to the `PATCH` table in `pakpatch.py`.
- **Letter is upside down** — the two pipelines were mixed up: atlas art is
  upright, pak art is flipped. See "How the mod is applied".
- **After a game/port update** — re-run both rebuild steps; if the atlas dump
  address changed, pass the new one to `gen_atlas.py`'s `find_dump_atlas()`.

---

## Credits and legal

The tiling/container research leans on public reverse-engineering projects:
[icemesh/big2-ps3-pak-research](https://github.com/icemesh/big2-ps3-pak-research),
[icemesh/t2-pak-research](https://github.com/icemesh/t2-pak-research),
[alphazolam/fmt_nd_pak](https://github.com/alphazolam/fmt_nd_pak),
[alphazolam/nd_pak.bt](https://github.com/alphazolam/nd_pak.bt),
[amrshaheen61/TLOU_PSARC_Tool](https://github.com/amrshaheen61/TLOU_PSARC_Tool),
[Ekey/U4.PSARC.Tool](https://github.com/Ekey/U4.PSARC.Tool).

These tools contain no game data. The generated mod does (re-encoded game art),
so keep it local: rebuild it from your own copy of the game and don't
redistribute the paks or `.urpl` files.
