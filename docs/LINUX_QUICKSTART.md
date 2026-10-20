# Linux quickstart (verified end to end on CachyOS, RTX 5070 Ti)

This branch (`linux`) is upstream `main` 0.3.6 plus the changes that make a Linux
build work: PRs #72, #112, #110, #223 (the set tracked in issue #293), the FFmpeg
link fix in `build.sh`, the `gpu_capabilities` include fix, and PR #348
(pattern-based mouse hooks and code patches so they also match the US 1.02 dump,
not just 1.00). `uncharted.sh` / `uncharted-gui.sh` are launchers in the bbport
`bb.sh`/`bb-gui.sh` style.

## Build

```bash
sudo pacman -S boost zydis nlohmann-json vulkan-headers robin-map vulkan-swrast xxhash
# vulkan-memory-allocator is not packaged: header-only, put vk_mem_alloc.h in a
# dir on CMAKE_INCLUDE_PATH (e.g. ~/.local/opt/vma/vk_mem_alloc.h).
bash build.sh
```

- `vulkan-swrast` (lavapipe) is optional, for the software-rendering fallback.
- On a host without system Vulkan headers, `CPATH=<vulkan-headers>/include` also
  works around the loader's pkg-config passing the gate (see build.sh's check).

## Game data

The port needs a decrypted dump of the collection: a folder with `eboot.bin`,
`big2-ps4_Shipping.elf`, `big3-ps4_Shipping.elf`, `sce_sys`, `u1data`, `u2data`,
`u3data`. Scene-repacked packages whose executables are fakesigned (plaintext
SELF segments) unpack fully offline with flatz's `pkg_pfs_tool`:

```bash
pkg_pfs_tool -u <base.pkg>   <out>   # then the patch pkg into the same <out>
pkg_pfs_tool --unpack-sc-entries -u <patch.pkg> <out>   # outer-container metadata
cp -a <out>/Sc0/. <out>/Image0/sce_sys/                # param.sfo, icons, ...
```

The default layout expected by the launchers is the dump at
`../game/CUSA02320/Image0` next to this checkout (`UC_GAME_DIR` overrides).

## Run

```bash
./uncharted.sh u2        # Drake's Fortune / Among Thieves / Drake's Deception = u1/u2/u3
./uncharted-gui.sh       # zenity picker: game, frame rate, fullscreen
```

Settings are saved in `~/.config/uncharted-launcher/settings.json`
(`exe`, `vblank`, `fullscreen`); `BB_*` environment variables always win.
Saves and shader caches land in the checkout's `user/` directory; the first run
per game stutters while the shader cache builds.

Note: game callbacks and code patches are matched by code pattern (PR #348) and
install on both 1.00 and 1.02 dumps — watch for `Callbacks: ...` lines in the
log to confirm.
