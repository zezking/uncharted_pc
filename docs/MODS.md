# Mods

The launcher has a **Mods** page: pick the folder, a master switch, an enable
toggle per mod, and arrows for the load order. Changes apply on the next launch.
The lower enabled mod wins when two mods provide the same file, and the log says
which one replaced which. The same system is described for the generic bbport
loader in `docs/MODS.ru.md` (Russian, inherited from upstream).

## Where mods live

By default the checkout's `mods/` folder is used, with `mods.json` next to it
(`<port>/mods`, `<port>/mods.json`). In the packaged/AppImage layout the data
directory is `~/.local/share/bbport/` (see `packaging/appimage.sh`). A mod is a
folder with the game's files in the same relative layout:

```text
mods/
  Xbox controller prompts/
    u1data/
      build/main/pak19/ps4/particle.pak
    u2data/...
    u3data/...
    texreplace/                 optional, see below
```

Accepted layouts (the loader detects them automatically):

- the collection's content folders directly — `u1data`, `u2data`, `u3data`,
  `shareddata` — which is what this port uses;
- `dvdroot_ps4/...`, `app0/dvdroot_ps4/...` or `CUSA03173/dvdroot_ps4/...`
  (bbport/Bloodborne heritage, still accepted);
- one wrapper folder, as happens when an archive is unpacked into a folder of
  its own name: `Mod name/Mod name v1.2/u1data/...` (a readme or screenshots may
  sit next to it);
- the game's top-level folders without a wrapper (`chr/`, `parts/`, `menu/`, …),
  which are mapped under `dvdroot_ps4/`.

File names are matched case-insensitively, so a mod built on Windows works
unchanged. A mod may also add files that the game does not have.

## How it is mounted

The originals are never touched. At launch `scripts/mods.py` builds a private
tree of links in `out/mod-game-*` that contains the game plus every enabled
mod's files; the game is then started against that tree, and `/app0` is
read-only. Saves stay in `user/` and remain writable. The tree is removed when
the game exits normally or the launcher stops it; after a SIGKILL or power loss
it can be left behind, and such a directory is never reused.

The launch log reports the result:

```text
Mods: 12 game files replaced, 0 added
```

If a mod is supposed to replace files but reports `0 game files replaced`, its
paths do not match the game's layout (or the files are nested one folder too
deep). ZIP/7z archives have to be unpacked first.

Not supported: replacing `eboot.bin`, `sce_module` or `sce_sys`, DLL injectors,
script plugins, and symlinks inside a mod. Executable-code patches are a
separate mechanism (see *Patches* below), not something a mod ships.

## Order and switches

`mods.json` in the port's data directory:

```json
{"order": ["First mod", "Second mod"], "disabled": ["Second mod"]}
```

New folders are enabled automatically and appended in alphabetical order.
From a terminal:

```sh
BB_MODS_DIR=/path/to/mods BB_MODS_CONFIG=/path/to/mods.json ./uncharted.sh u3
BB_MODS_ENABLED=0 ./uncharted.sh u3          # no mods, no texture replacements
BB_MOD_TRACE=1 BB_MODS_DIR=/path/to/mods ./uncharted.sh u3
```

`BB_MOD_TRACE=1` prints the first reads of files that actually come from the
mod tree (up to 32 lines), which is the fastest way to see whether the game
looks for the path you thought it did.

## Texture replacements (texreplace)

Some interface art never exists as a file: the button atlas is assembled by the
game itself in guest memory. Any mod can ship a `texreplace/` directory with
files named after the guest address of that texture:

```text
<mod>/texreplace/<16 hex digits>.urpl
<mod>/texreplace/<exe>/<16 hex digits>.urpl     game-specific keys (u1, u2, u3)
```

When the game uploads a texture at that address, the port writes the `.urpl`
contents over it (`BB_TEXREPLACE`, implemented in
`gpu/shadps4/video_core/texture_cache/texture_cache.cpp`). Format:

```text
'URPL' | u32 width | u32 height | width*height RGBA8888 pixels, PS4-tiled
```

The dimensions and the byte size must match the upload, so only 32 bpp
(RGBA8) textures can be replaced this way — block-compressed pak textures are
patched in the pak instead. The `<exe>` subdirectory is scanned last and wins,
so a key that only makes sense in one game cannot leak into the other two.

What fired is written to `user/texreplace.log`:

```text
loaded 3 replacement(s) from .../texreplace:.../texreplace/u3
  0000001151a64000 512x512
  patched 0000001151a64000 512x512
```

The Xbox-button-glyph mod in `tools/xbox-glyphs` uses both mechanisms and is a
worked example.

## Runtime settings (`bbport.ini`)

`bbport.ini` in the data directory holds the graphics settings the GPU library
reads; the launcher writes it, and `BB_*` environment variables override it.

| key | values | meaning |
|---|---|---|
| `upscaler` | `fsr4`, `fsr411`, `fsr3`, `taa`, `off` | temporal upscaler |
| `preset` | `0`…`4` | Native AA, Quality ×1.5, Balanced ×1.7, Performance ×2, Ultra Performance ×3 |
| `output_res` | `1280x720`, `1920x1080`, `2560x1440`, `3840x2160` | output resolution |
| `sharpen`, `sharpness` | `0`/`1`, `0.0`…`1.0` | RCAS sharpening of the final image |
| `live_resolution` | `auto`, `0`, `1` | let the window/resolution follow the video card |
| `show_fps` | `0`/`1` | on-screen frame rate |
| `model_lod`, `object_motion` | `0`/`1` | LOD and object motion vectors |
| `frame_gen`, `frame_gen_multiplier` | `off`/`fsr3`/`dlss`, `2`…`4` | frame interpolation (FSR 3 works on any GPU) |

Sharpening also applies to **TAA**: the range is 0…1, at 0 (or with the switch
off) there is no extra pass, RCAS runs on the finished scene before the HUD, and
the TAA history keeps the colour from before sharpening so it is not amplified
when re-accumulated. Flat areas keep their original colour, HDR included, and no
extra buffer is needed.

## Patches

The `patches/` folder, `patches.json`, `BB_PATCHES_DIR` and `BB_PATCHES_CONFIG`
come from bbport (the Bloodborne port) and are kept for compatibility: they
accept shadPS4/GoldHEN XML patch files whose `TitleID` and
`Metadata AppVer="01.09"` match Bloodborne. The bundled
`patches/Bloodborne.xml` targets Bloodborne's `eboot.bin`, so **nothing in this
system applies to the Uncharted dumps** (`CUSA02320`, app versions 01.00/01.02).

Because of that the launcher does not offer those controls at all: the
"third-party patches" page and the old `effect_*` switches (chromatic
aberration, DoF, motion blur, SSAO, game AA, dynamic shadows, SSR, intro skip,
debug camera/menu) are gone, and the launcher removes those keys from
`bbport.ini` when it saves, so the file only lists settings the port reads.

Uncharted's own runtime changes live in the port instead: the frame rate, the
upscaler/frame-interpolation setup and the mouse hooks are built-in patches that
locate the eboot code by pattern (`src/runtime_pad.c`, `src/probe.c`), so they
work on both the 1.00 and the 1.02 dump without any XML.
