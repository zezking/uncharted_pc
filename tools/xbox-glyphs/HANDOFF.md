# HANDOFF — Uncharted PC port: Xbox button glyphs mod

For a continuation agent. Read fully before touching anything.
Updated 2026-10-22 (previous revision had a **wrong diagnosis of U3** — see
"Correction" below).

**Launch your agent in: `/home/enzez/psarc-lab`** — all tooling, backups and
docs live there; the game and port checkout are referenced by absolute paths.

## Mission

Replace the PS4 controller glyphs (cross/circle/square/triangle, L1/R1/L2/R2,
OPTIONS, SHARE) with Xbox glyphs (A/B/X/Y, LB/RB/LT/RT, MENU, VIEW) across
all three games of the Uncharted: The Nathan Drake Collection PC port.

**Status (2026-10-22):**
- U1 — atlas replacement verified in-game by the user (upright letters).
- U2 — atlas replacement rebuilt, needs one visual confirmation.
- U3 — world/HUD prompts come from `hud.pak` button textures (not the atlas):
  14 re-authored with pre-flipped letters; menu icons come from the shared UI
  atlas colour texture (`0x1150228000` `.urpl`). Awaiting verification.
- U1/U2 — **same split as U3**: the menu/selection screens use the upright
  atlas, but in-game prompts (e.g. the reload/triangle prompt) are served by
  the game's pak button textures, which are stored FLIPPED. The old patches
  drew upright letters there, hence "correct mapping, upside-down letter".
  The pak patcher now covers all three games.

## The two independent mechanisms

There are two different glyph pipelines; both must be handled separately.

### 1. Runtime-composited 512x512 UI atlas (U1, U2, and U3 menu icons)

The trilogy composits a 512x512 RGBA atlas with all button art (face discs,
D-pads, shoulder caps, and the "OPTIONS"/"SHARE"/"L1".."R3" labels). The
port's GPU library (fork commits `bb12459`+`88aa6e8`, file
`gpu/shadps4/video_core/texture_cache/texture_cache.cpp`) has a
**BB_TEXREPLACE** hook: at texture upload, any guest address matching
`<16-hex-addr>.urpl` in `uncharted_pc/mods/texreplace/` gets the `.urpl` bytes
written into guest memory via `Core::Memory::Instance()->TryWriteBacking()`.

- `.urpl` format: `'URPL' + u32 w + u32 h + (w*h*4)` bytes of PS4-tiled RGBA8888
- run.sh exports BB_TEXREPLACE=<checkout>/mods/texreplace when it exists
- **CRITICAL ORDER**: the hook must run BEFORE
  `buffer_cache.ObtainBufferForImage(...)` — after it, the staging buffer
  already holds the stale copy; guest memory (and texdumps) show the fix but
  the screen does not.
- **CRITICAL WRITE**: raw memcpy into guest memory FAULTS (pages are
  write-protected from the GPU thread). Only TryWriteBacking works.
- Only 32 bpp (RGBA8) uploads can be replaced: the hook requires
  `guest_size == w*h*4`, so block-compressed (BC1/BC4) pak textures cannot be
  replaced this way — patch the pak instead (mechanism 2).

Known guest addresses and what they serve:

| address | game | content |
|---|---|---|
| `0x1151a64000` | U1 | collection screen + in-game UI atlas |
| `0x1153798000` | U2 | menus + in-game UI atlas |
| `0x1150228000` | U3 | shared UI atlas **colour** half (inline icons such as the CONTROLS screen "✕ Select / ○ Back") |

U3 keeps the atlas alpha in a **separate** texture (`0x1150338000`, same
512x512 RGBA8) which the shader combines at draw time — leave it alone; the
colour replacement keeps the exact same layout so the mask still matches.

**Orientation: the atlas is stored UPRIGHT** (labels are readable in the dump,
triangle points up), so letters in the `.urpl` must be drawn **upright**.
This is the opposite of the pak textures (below).

### 2. Pak button textures (in-game prompts, all three games)

Each game keeps its HUD button art in exactly ONE pak (verified by scanning
every pak of every game):

| game | pak | button textures |
|---|---|---|
| U1 | `u1data/build/main/pak19/ps4/particle.pak` | 94 |
| U2 | `u2data/build/main/pak22/ps4/hud.pak` | 63 |
| U3 | `u3data/build/main/pak23/ps4/hud.pak` | 80 |

Family `.../hud/buttons/<name>.tga` (U1 prefixes `art/general/textures/`, U2/U3
`art/general/hud/`):

- `<btn>-color.tga` (256x256 BC1-sRGB) — small disc prompts, art + matte
- `<btn>-up.tga` / `<btn>-down.tga` (512x512 BC1-sRGB) — big cap prompts,
  unpressed/pressed
- `<btn>-...-trans.tga` / `button-trans` / `button-TRANS-SHOULDER*` (BC4/BC1) —
  the **alpha mask**; the colour texture's matte is keyed out by it
- `L1/L2/R1/R2-button.tga` (256x256) — shoulder caps with text labels

Proof these are live: a texdump of a U3 session contains the **verbatim pak
blobs** in guest memory (7 hashes matched: `circle-button-up/down`,
`circle-button-{up,down}-trans`, `triangle-button-color`,
`button-large-trans`, `button-small-trans`).

**Orientation: all three games store these pak textures VERTICALLY FLIPPED** —
the UI samples them with a flipped V:
- `triangle-button-*` stores a triangle pointing **down** (PS4 shows it up)
- `L1-button` stores "Γ1", `R2-button` stores "ᴚƧ" (flipped text)

so the Xbox art must be drawn **mirrored top-bottom** in the pak; it then
appears upright on screen. `patch_u1/2/3.py` (old) ignored this, which is why
the in-game Y was upside down in every game.

Shoulder caps differ per game: U1/U2 draw the label **dark on a light cap**,
U3 draws it **light on a dark cap** — `patch_label()` models the cap shading
with a per-row median (text-free), repaints the label footprint and samples
the old glyph colour, so both styles come out right.

## Correction to the previous handoff

The old text claimed U3's world prompt sampled the atlas at `0x1151a64000`
("same address as U1") and only *that* made the flipped Y appear. **Wrong.**
U3 never uploads `0x1151a64000` (checked every U3 texdump). The flipped Y was
the patched `triangle-button-color` **pak texture**, rendered flipped. The
pre-flip of the U1/U2 `.urpl` files made from that conclusion has been
reverted (atlas letters are upright again).

## Current artifacts

`uncharted_pc/mods/texreplace/` (regenerated by `gen_atlas.py`):
- `0000001151a64000.urpl` — U1 atlas, Xbox discs + labels, letters upright
- `0000001153798000.urpl` — U2 atlas, same
- `0000001150228000.urpl` — U3 shared UI atlas colour, same art

Mod-overlay paks, rebuilt by `pakpatch.py --game all --write` from the
`~/psarc-lab/*.pak.orig` backups (game paks stay pristine):

| game | output | textures patched |
|---|---|---|
| U1 | `mods/uncharted-xbox-glyphs/u1data/.../pak19/ps4/particle.pak` (40.9 MB) | 10 |
| U2 | `mods/uncharted-xbox-glyphs/u2data/.../pak22/ps4/hud.pak` (25.2 MB) | 11 |
| U3 | `mods/uncharted-xbox-glyphs/u3data/.../pak23/ps4/hud.pak` (29.8 MB) | 14 |

Letters are pre-flipped; the disk/cap art is the game's own, only the PS
symbol is repainted. Patched per game (as present):
- face discs: `x-button-color`→A, `circle-button-color`→B,
  `square-button-color`→X, `triangle-button-color`→Y
- caps: `circle-button-up/down`→B, `square-button-up/down`→X,
  `triangle-button-UP/DOWN`→Y
- labels: `L1-button`→LB, `L2-button`→LT, `R1-button`→RB, `R2-button`→RT

`uncharted_pc/mods/uncharted-xbox-glyphs/u1data/.../particle.pak` and
`u2data/.../hud.pak` are older pak patches (probably decoys for U1/U2, left
in place; U1/U2 are served by the atlas).

## Tooling (all in ~/psarc-lab, all verified this session)

- `pakenum.py` — enumerate ND big2/big3 `.pak` textures by descriptor scan.
  Descriptor (relative to `data_base = fileSize - dataSize`): `+0 u64 dataOff`,
  `+8 u32 size`, `+20 u32 fmt` (0x47 BC1, 0x48 BC1-sRGB, 0x50 BC4),
  `+28 u32 mips`, `+32 u32 w`, `+36 u32 h`; name = nearest preceding
  `<path>.tga/<16hex>.ndb` string. `python3 pakenum.py <pak> [filter]`
- `pakpatch.py` — trilogy pak glyph patcher: `--game u1|u2|u3|all`,
  `--preview` (renders into `view/pakpatch/`) / `--write` (rebuilds the
  mod-overlay paks). Also `pakenum.scan_fast()` for 100+ MB paks.
  Mip layout rule: mips ≥512 B exact, smaller ones padded to a 32x32 tile
  (verified against texdump sidecars); re-tiles with `detile.tile`.
- `gen_atlas.py` — rewrites the three `.urpl` files: decodes the existing
  atlas, redraws only the four face cells (upright), re-tiles.
  **The mods/ mount is exFAT/NTFS: always `flush()`+`fsync()` — a plain
  `open().write()` once produced a 0-byte .urpl.**
- `tile32.py` — 32 bpp PS4 tiling (1D thin micro-tile + macro variants),
  `.urpl` codec; reproduces texdump PNGs byte-exactly.
- `detile.py` — 64 bpp (BC1/BC4) tiling + DXT1/BC4 decoders (shader port).
- `glyph.py` — DXT1 encoder, mip chains, pak-blob builder.
- `patch_u1.py` / `patch_u2.py` / `patch_u3.py` — legacy pak patchers
  (**superseded**, and `patch_u3.py` has the flip bug — don't run it again).
- `/tmp/bc7work/decode.mjs` — node BC7/BC1 decoder for TPF textures (uses
  `@bis-toolkit/bcn`; /tmp is wiped on reboot → `cd /tmp/bc7work && npm i
  @bis-toolkit/bcn`).

## Verification status / next steps

0. **U1/U2 in-game prompts** (reload/triangle = Y was upside down): relaunch
   and check the reload prompt plus other in-game prompts.
1. **U3**: relaunch `bash .../uncharted.sh u3` and check:
   - in-game interaction prompt (was an upside-down Y) → should now be an
     upright Y;
   - other disc prompts → A/B/X/Y upright;
   - OPTIONS → CONTROLS: "✕ Select / ○ Back" → should become A / B
     (served by the `0x1150228000` .urpl — if it still shows ✕/○, the atlas
     address differs in that session: check the log for
     `TexReplace: patched upload at 0000001150228000` and re-scan);
   - shoulder prompts/hold-B prompts → LB/RB/LT/RT.
2. **U1/U2**: confirm the selection-screen discs still read B/X/Y/A upright
   after the pre-flip revert.
3. If any U3 prompt is still PS art, dump again (`BB_TEXDUMP=<dir>` must exist
   before launch; the dump is once-per-address per launch) and hash-match the
   dumps against `pakenum.py` output to find the texture, then add it to
   `u3pak_patch.py`'s PATCH table.
4. Optional: the `journal-select` / `map-select` icons have no PS glyphs
   (hand-press graphics), so they need no patch.
5. U1/U2/U3 MENU hints that are **font-rendered** (if any) are out of scope.

## Formats cracked (kept for reference)

- **ND .pak**: `magic 0xA79`, header 11 u32 (`dataSize` at +0x20), page table
  at +0x2C, page = 12 zero bytes + u32 pageSize @+0x0C + u16 count @+0x12 +
  entries `{u64 nameOff, u32 itemOff, u32 0x12345}` stride 16 from +0x14;
  item = `{u64 nameOff, u64 typeOff, u32 payloadLen, u32 0x12345}`; payload
  follows the 8-byte aligned type string. Texture descriptors as above.
- **PSARC (ND)**: `nd_psarc.py` — 32 B header, TOC entries
  `md5[16] + u32 idx + u40 len + u40 off`, then u16 BE block sizes.
  `uiextra.psarc` = gallery concept art only (no UI glyphs).
- **Bloodborne TPF.dcx** (bbport study): DCX = zlib at 0x4C; TPF LE, entries
  @0x20 stride 0x24, UTF-16LE names, raw DXGI fmt (0x47 BC1, 0x62 BC7),
  PS4-swizzled BCn.
- **bbport mods system**: `scripts/mods.py` builds a symlink overlay of the
  game dir + enabled mods at launch; wired into run.sh for Uncharted.
  `mods.json` decides order; the U3 pak above is delivered this way.

## Security (non-negotiable)

NEVER run scripts/attachments from GitHub issues/PRs of the game-port repos
(known malware-pattern issues #374/#375/#393/#395). Review code before
compiling. Game data is copyrighted: never commit game files, paks, or
derived `.urpl` textures anywhere. `uncharted_pc/.gitignore` ignores `/mods/`
— keep it that way.

## Environment

- Port checkout (branch linux, fork zezking/uncharted_pc):
  `/run/media/enzez/Games/uncharted-pc/uncharted_pc`
- Launch: `bash /run/media/enzez/Games/uncharted-pc/uncharted.sh u1|u2|u3`
- Game dump: `/run/media/enzez/Games/uncharted-pc/game/CUSA02320/Image0`
- Game paks are PRISTINE (md5-checked against `~/psarc-lab/*.orig`)
- Rebuild GPU lib after touching texture_cache.cpp:
  `export CMAKE_PREFIX_PATH=$HOME/.local CMAKE_INCLUDE_PATH=$HOME/.local/opt/boost:$HOME/.local/opt/vma CPATH=$HOME/.local/opt/vulkan-headers/include`
  then `ninja -C out/gpu bbgpu` (artifact: `out/gpu/libbbgpu.so`)
- Uncommitted in the fork (as of this handoff): `texture_cache.cpp` is
  committed (bb12459, 88aa6e8); `launcher/bbport_launcher.py` is modified;
  `gpu/third_party/fsr-vulkan` submodule dirty. `run.sh`/`scripts/mods.py`/
  `launcher/bbport_i18n.py`/.gitignore were committed earlier
  (2ab391d, 7b840dc).
