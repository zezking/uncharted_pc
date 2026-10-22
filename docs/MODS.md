# File mods

The launcher has a **Mods** group: pick the folder, a master switch, an enable
toggle per mod, and arrows to set the load order. Changes apply on the next
launch. The lower enabled mod has the higher priority; when two mods provide the
same file, the log says which one replaced which.

By default `bbport/mods/` is used, and `~/.local/share/bbport/mods/` in the
AppImage. Unpack a downloaded mod like this:

```text
mods/
  Mod name/
    dvdroot_ps4/
      chr/...
      param/...
      menu/...
```

These layouts are also accepted:

- `Mod name/app0/dvdroot_ps4/...` and `Mod name/CUSA03173/dvdroot_ps4/...`;
- an extra wrapper folder, as happens when an archive is unpacked into a folder
  of its own name: `Mod name/Mod name v1.2/dvdroot_ps4/...` (a readme or images
  may sit next to it);
- a mod without `dvdroot_ps4` that holds the game folders directly:
  `Mod name/chr/...`, `Mod name/parts/...` (`chr`, `parts`, `map`, `menu`,
  `msg`, `param`, `sfx`, `sound`, `font` and the other `dvdroot_ps4` folders).

Name case does not matter inside a mod: `DVDROOT_PS4/Chr/C0000.chrbnd.dcx` from
a mod built on Windows replaces the game's `dvdroot_ps4/chr/c0000.chrbnd.dcx`.
Previously such a file was added alongside under its own name and the game never
saw it. The launch log shows how many game files a mod replaced and how many it
added: `Mods: 12 game files replaced, 0 added`. If a mod is supposed to replace
files but reports `0 game files replaced`, check the paths inside the mod.
ZIP/7z archives have to be unpacked first. Ready-made `dvdroot_ps4` replacements
are supported: textures, models, parameters, interface, sound and fonts. The
manager does not merge the contents of two identical `.dcx`/`.bnd` files: the
last replacement wins as a whole.

For an already prepared folder, shadPS4 also supports the sibling directory
`CUSA03173-mods/dvdroot_ps4/...` next to `CUSA03173/`. It is mounted
automatically before the mods from the list. The master switch turns it off as
well. You can also select a folder that directly contains `dvdroot_ps4` as the
mods folder; such a folder is mounted as a whole, without a list of individual
mods. The `-mods` convention is verified against the
[shadPS4 sources](https://github.com/shadps4-emu/shadPS4/blob/main/src/core/file_sys/fs.cpp).

The game originals are never overwritten. At launch a separate merged tree of
links is created in the data directory `out/mod-game-*`; reads, stat and
directory listings see the selected replacements plus the remaining original
files. The game's `/app0` and `/hostapp` are read-only. Saves stay in their
usual folder and remain writable. On a normal exit, or when the launcher stops
the game, the temporary tree is deleted. After a SIGKILL or a power loss it can
be left behind; such directories are not used by the next launch.

Mods that replace `eboot.bin`, `sce_module` or `sce_sys`, DLL injectors and
script plugins are not supported by this loader. Executable-code patches stay in
the existing `patches/` / `BB_PATCHES` system. Symlinks inside a mod are not
accepted. Whether a particular mod is compatible with CUSA03173 1.09 is up to
its author.

To run from a terminal:

```sh
BB_GAME_DIR=/path/to/CUSA03173 BB_MODS_DIR=/path/to/mods bash run.sh
BB_GAME_DIR=/path/to/CUSA03173 BB_MODS_ENABLED=0 bash run.sh
```

Load order and disabled mods are stored in `mods.json` in the data directory:

```json
{"order": ["First", "Second"], "disabled": ["First"]}
```

New folders are enabled automatically and appended at the end in alphabetical
order. `BB_MODS_CONFIG` changes the profile path. `BB_MOD_TRACE=1` together with
`BB_MODS_DIR` prints the first reads of the files that are actually mounted, for
diagnostics.

# Third-party patches (shadPS4 XML)

The `patches/` folder in the data directory (`~/.local/share/bbport/patches/` in
the AppImage; in the launcher it is the **Third-party patches** group, where
another folder can be selected). XML patch files in shadPS4/GoldHEN format are
accepted: `Metadata` for `AppVer="01.09"` and `eboot.bin` is used, files with
another game's `TitleID` are skipped. The initial enabled state comes from the
file's `isEnabled`; the launcher's choice is saved in `patches.json` in the data
directory:

```json
{"enabled": ["file.xml/Patch name"], "disabled": ["file.xml/Other patch"]}
```

The lines `bytes`, `bytes16/32/64`, `float32/64`, `utf8` and `utf16` are
supported. A patch that uses `mask` lines (pattern search) or that patches an
address outside eboot is skipped entirely, with a message in the log. Third-party
patches are applied after the built-in ones (`patches/Bloodborne.xml`); on a
conflict the third-party one wins. From a terminal:
`BB_PATCHES_DIR=/path BB_PATCHES_CONFIG=/path/patches.json bash run.sh`.

Patches that replace pointers in tables (such as `60 FPS++` and `90 FPS++`) are
relocated by the loader to the image's real address. Previously such patches
aborted the launch with `patch overlaps a relocation`.

# TAA sharpening

The `sharpen` and `sharpness` settings now also apply to TAA, both in the
launcher and in the game's menu. Range **0…1**; at 0, or with the switch off,
there is no extra pass. RCAS is applied to the finished scene before the HUD. The
TAA history keeps the colour from before sharpening so it is not amplified when
re-accumulated. Flat areas keep their original colour, HDR included; no extra
buffer is needed.

## UI texture replacement (texreplace)

Any mod can ship a `texreplace/` directory of its own with files named
`<16 hex digits of the guest memory address>.urpl`. When the game uploads the
texture at that address, the port replaces its contents in guest memory
(`BB_TEXREPLACE`; the code is in
`gpu/shadps4/video_core/texture_cache/texture_cache.cpp`). File format: `URPL`,
`u32` width, `u32` height, then RGBA8888 pixels in PS4 tiling.

That is how interface graphics that do not exist in the pak files are replaced:
the button atlas is assembled by the game itself in memory. A
`texreplace/<exe>/` subdirectory (`u1`, `u2`, `u3`) is scanned last and holds
keys that must not leak into the other parts of the collection.
`BB_MODS_ENABLED=0` disables both file mods and texture replacement. Log:
`<port data>/user/texreplace.log`.
