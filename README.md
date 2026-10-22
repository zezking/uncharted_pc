# Uncharted: The Nathan Drake Collection — Linux

Native Linux build of the PS4 collection: Uncharted 1, 2 and 3 run their original PS4 code
directly on your machine, with the graphics translated to Vulkan. One launcher, one game dump,
three games.

This is a **Linux fork** of [SuperMedo's Windows port](https://github.com/Supermedo/uncharted_pc),
built on [bbport](https://github.com/deadinside28/bloodborne_pc) (deadinside28's native Linux
Bloodborne port) and the [shadPS4](https://github.com/shadps4-emu/shadPS4) renderer.
The original Windows README is kept at [`docs/original-readme/README.md`](docs/original-readme/README.md).

> **No game files are included.** You need your own decrypted dump of the collection
> (`CUSA02320` — the folder with `eboot.bin`, `big2-ps4_Shipping.elf`,
> `big3-ps4_Shipping.elf`, `sce_sys`, `u1data`, `u2data`, `u3data`).
> This project is not affiliated with Sony Interactive Entertainment or Naughty Dog.

## What this branch changes

Branch `linux` = upstream `0.3.6` plus everything needed to build and run it on Linux:

- the Linux build fixes tracked in upstream issue #293 (PRs #72, #112, #110, #223), the FFmpeg
  link fix in `build.sh`, the `gpu_capabilities` include fix;
- PR #348: callbacks and code patches are matched by **code pattern**, so they install on both
  the 1.00 and the 1.02 dumps;
- Linux launchers: `uncharted.sh` (CLI) and `uncharted-gui.sh` (GTK4), settings in
  `~/.config/uncharted-launcher/settings.json`;
- a loose-file **mods** system for the collection's content layout (`u1data`/`u2data`/`u3data`)
  and a **runtime texture replacement** hook (`BB_TEXREPLACE`), used by the Xbox button-glyph mod.

Verified on CachyOS (NVIDIA RTX 5070 Ti) and Pop!_OS 22.04 with GCC 14; lavapipe works as a
software fallback for smoke tests.

## Features

- **All three games** from one launcher: Drake's Fortune, Among Thieves, Drake's Deception.
- **60 Hz or 120 Hz** vblank like/above PS4; higher rates are experimental.
- **Upscaling**: FSR 4, FSR 4.1.1, FSR 3, TAA, or off — with Native AA / Quality / Balanced /
  Performance / Ultra Performance presets, output resolution and sharpening.
- **Frame interpolation**: FSR 3.1 (any GPU, 2×) via `BB_FRAME_GEN=fsr3`; not exposed in the
  launcher yet. DLSS upscaling and DLSS frame generation are Windows-only.
- **Game effects toggled by code patches**: chromatic aberration, depth of field, motion blur,
  SSAO, the game's own anti-aliasing, dynamic shadows, SSR.
- **Keyboard, mouse and controller** together, remappable; mouse look in all three games.
- **Mods**: loose-file overlay and per-mod texture replacement, `mods.json` decides order and
  which ones are enabled.
- **Launcher**: GTK4, Russian/English UI, desktop shortcut and Steam entry helpers.

## Requirements

- x86-64 Linux, Vulkan 1.3 with a current driver, **6 GB of VRAM or more**, ~8 GB of RAM.
  4 GB cards (GTX 1650, RX 570) run out of video memory and crash after a while; keep the
  upscaler and frame generation off on those.
- A CPU with the PS4 instruction set (AVX, BMI1, MOVBE, LZCNT). AMD FX works (MOVBE is
  emulated, a bit slower); Intel Core 3rd generation and older can't run the games.
- For building: **GCC 14 or Clang** (the code needs C++23; GCC 11/12 fail), CMake, Ninja,
  pkg-config with `vulkan` and `sdl3`, FFmpeg development headers.

## Building

```bash
git clone --recursive https://github.com/zezking/uncharted_pc.git
cd uncharted_pc
bash build.sh              # out/bb-probe, out/gpu/libbbgpu.so, out/bb-gpu-capabilities
bash build.sh --test       # plus the C test suite
```

Arch:

```bash
sudo pacman -S base-devel cmake ninja pkgconf vulkan-headers vulkan-icd-loader \
               sdl3 ffmpeg boost zydis nlohmann-json robin-map xxhash
```

Debian/Ubuntu: see [`docs/LINUX_BUILD.md`](docs/LINUX_BUILD.md) — it also covers building
Protobuf 29 from source with `-fPIC`, which the GPU library needs.

Notes:

- Submodules (`gpu/third_party/*`, `third_party/Vulkan-Headers`) are pulled by `build.sh` if
  missing; the FSR-Vulkan patches are applied automatically.
- `BB_LTO=OFF` disables link-time optimisation; `BB_PGO=generate|use|off` controls profile-guided
  optimisation (the default uses an existing `pgo/` profile).
- NixOS: `nix-shell shell.nix --run 'bash build.sh'`. AppImage: `packaging/appimage.sh`.
- `libbbgpu.so` is the GPU library — after touching `gpu/` sources, `ninja -C out/gpu bbgpu`
  is enough.

## Game data

The port needs a decrypted dump of the collection and expects it next to the checkout at
`../game/CUSA02320/Image0` (`UC_GAME_DIR` overrides this). Scene-repacked packages whose
executables are fakesigned unpack fully offline with flatz's `pkg_pfs_tool`; the community also
uses `ps4-pkg-tools` plus `psarcy` for the `.psarc` files. Both routes are written up step by
step in [`docs/LINUX_QUICKSTART.md`](docs/LINUX_QUICKSTART.md).

## Running

```bash
./uncharted.sh u1        # Drake's Fortune  (collection eboot)
./uncharted.sh u2        # Among Thieves
./uncharted.sh u3        # Drake's Deception
./uncharted-gui.sh       # GTK4 launcher: game, frame rate, upscaler, effects
```

Settings live in `~/.config/uncharted-launcher/settings.json`; environment variables always win.
Saves and the shader cache go to `./user` in the checkout.

| variable | default | meaning |
|---|---|---|
| `UC_GAME_DIR` / `BB_GAME_DIR` | `../game/CUSA02320/Image0` | decrypted game dump |
| `BB_EXE` | `u1` | `u1`, `u2`, `u3` or a raw executable name |
| `BB_USER_DIR` | `./user` | saves, logs, shader cache |
| `BB_VBLANK_HZ` | `60` | `60` or `120` |
| `BB_FULLSCREEN` | off | `1` for fullscreen |
| `BB_FRAME_GEN` | `off` | `fsr3` (any GPU, 2×) or `dlss` (RTX 40/50, Windows only) |
| `BB_MODS_ENABLED` | `1` | `0` disables file mods and texture replacements |
| `BB_TIMEOUT` | `0` | watchdog timeout in seconds (0 = infinite) |
| `BB_CONTENT_SKU` | `full` | `full` or `trial` |

The first launch of each game stutters while the shader cache builds; later runs are smooth.

## Mods

```
mods/
  <mod name>/
    u1data/…       files that override the game's (same relative paths)
    u2data/…
    u3data/…
    texreplace/    optional <16-hex guest address>.urpl texture replacements
      u3/          per-game subfolder for keys that must not leak into the others
mods.json          {"order": [...], "disabled": [...]}
```

The port builds a private symlink overlay at launch, so the game folder is never touched. The
`<mod>/texreplace/` files are written into guest memory when the game uploads that texture,
which covers UI whose source art does not exist in the paks.

A worked example ships in this repo: **[`tools/xbox-glyphs`](tools/xbox-glyphs/README.md)**
replaces all PS4 button prompts with Xbox A/B/X/Y, LB/RB/LT/RT, MENU/VIEW across the trilogy.
Conventions and details: [`docs/MODS.md`](docs/MODS.md).

## Known limitations

- Frame rates above 120 are experimental.
- DLSS (upscaling and frame generation) is not available in this Linux build; FSR is.
- The GTK4 launcher exposes upscaling but not frame generation — use `BB_FRAME_GEN=fsr3`.
- Some effects sharpness/coverage depends on the dump version (1.00 vs 1.02); the pattern-matched
  hooks cover both, watch for the `Callbacks:` lines in the log.

## Troubleshooting

- **"No eboot.bin in …"** — point `UC_GAME_DIR` at the folder that contains `eboot.bin`.
- **Device lost / crash** — check the driver and VRAM; lower the upscaler preset or turn it off.
- **Black screen** — run with lavapipe (`vulkan-swrast`, `VK_ICD_FILENAMES=...`) to see whether
  it is a driver problem, and check that the GPU driver reports Vulkan 1.3.
- **Where the logs are** — the launcher's **Log** page shows the whole run; `user/texreplace.log`
  records texture replacements, and the GPU build log is `out/gpu-build.log`. Please attach those
  to an issue.

## Credits

The original port and its reverse engineering are **SuperMedo's** work — this fork only makes it
build and run on Linux and adds the mod support. Built on
[bbport](https://github.com/deadinside28/bloodborne_pc) by deadinside28 and the
[shadPS4](https://github.com/shadps4-emu/shadPS4) renderer. Video decoding (Videodec2) and the
DLSS bridge come from
[IFreemz/shadPS4-Bloodborne-DLSS-FSR](https://github.com/IFreemz/shadPS4-Bloodborne-DLSS-FSR).
Thanks to Mindro for the shadPS4 Uncharted build that showed which problems to look for.

Also used: [FSR-Vulkan](https://github.com/FireBurn/FSR-Vulkan) and the AMD FidelityFX SDK (FSR),
FSR 4 assets from [FireBurn/Q2RTX](https://github.com/FireBurn/Q2RTX), the
[NVIDIA DLSS SDK](https://github.com/NVIDIA/DLSS) (`nvngx_dlss.dll`, Windows builds only, under
NVIDIA's license), [LibAtrac9](https://github.com/Thealexbarney/LibAtrac9),
[SDL3](https://github.com/libsdl-org/SDL), [FFmpeg](https://ffmpeg.org),
[Dear ImGui](https://github.com/ocornut/imgui), [sirit](https://github.com/shadps4-emu/sirit),
[magic_enum](https://github.com/Neargye/magic_enum), [xbyak](https://github.com/herumi/xbyak),
[Vulkan Memory Allocator](https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator),
and the Cinzel font (SIL Open Font License).

NVIDIA, GeForce RTX and DLSS are trademarks of NVIDIA Corporation. The default covers and the
icon are original artwork; no official art is included.

## License

GNU GPL v2 or later ([LICENSE](LICENSE)). Third-party components keep their own licenses.
