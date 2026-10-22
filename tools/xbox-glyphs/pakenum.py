#!/usr/bin/env python3
"""Enumerate ND big2/big3 .pak textures by descriptor scan.

Descriptor (64B, found by structure, offset relative to the pak's data base):
  +0  u64 dataOff   (file offset = data_base + dataOff)
  +8  u32 size      (mip chain size in bytes)
  +20 u32 fmt       (0x47 BC1, 0x48 BC1 sRGB, 0x50 BC4, ...)
  +28 u32 mips
  +32 u32 width
  +36 u32 height
Name taken from the nearest preceding "<...>/<name>.tga/<16hex>.ndb" string.
"""
import re
import struct
import sys

DESC = 64
NAME_RE = re.compile(rb'([A-Za-z0-9_./\-]+\.(?:tga|png|dds|bmp|gif))/[0-9A-Fa-f]{16}\.ndb')
FMT = {0x47: 'BC1', 0x48: 'BC1-sRGB', 0x50: 'BC4', 0x51: 'BC4-sRGB'}


def scan(path):
    d = open(path, 'rb').read()
    data_size = struct.unpack('<I', d[0x20:0x24])[0]
    data_base = len(d) - data_size
    out = []
    seen = set()
    for off in range(0, len(d) - DESC, 4):
        dataoff, size = struct.unpack('<QI', d[off:off + 12])
        fmt, flags, mips = struct.unpack('<III', d[off + 20:off + 32])
        w, h = struct.unpack('<II', d[off + 32:off + 40])
        if fmt not in FMT:
            continue
        if not (0 < mips <= 13):
            continue
        if not (0 < w <= 8192 and 0 < h <= 8192):
            continue
        if dataoff + size > data_size or size == 0:
            continue
        # mip-chain sanity: BCn 4x4 block size
        bpb = 8 if fmt in (0x47, 0x48) else 8
        need = sum(((max(w >> m, 1) + 3) // 4) * ((max(h >> m, 1) + 3) // 4) * bpb
                   for m in range(mips))
        if abs(need - size) > 512 * mips:
            continue
        if dataoff in seen:
            continue
        seen.add(dataoff)
        m = None
        for mm in NAME_RE.finditer(d, max(0, off - 4096), off):
            m = mm
        name = m.group(1).decode('utf-8', 'replace') if m else f'@0x{dataoff:x}'
        out.append(dict(name=name, dataoff=dataoff, size=size, fmt=fmt, mips=mips,
                        w=w, h=h, file_off=data_base + dataoff))
    return out, data_base, data_size, len(d)


if __name__ == '__main__':
    path = sys.argv[1]
    pat = sys.argv[2].lower() if len(sys.argv) > 2 else ''
    ents, base, dsize, total = scan(path)
    print(f'data_base={base:#x} data_size={dsize:#x} file={total:#x} textures={len(ents)}')
    for e in ents:
        if pat in e['name'].lower():
            print(f"  {e['name']:<70} {e['w']}x{e['h']} m{e['mips']} "
                  f"{FMT[e['fmt']]:<9} size={e['size']} off={e['dataoff']:#x} file={e['file_off']:#x}")


def scan_fast(path):
    """Vectorised version of scan() for multi-hundred-MB paks."""
    import numpy as np
    d = open(path, 'rb').read()
    data_size = struct.unpack('<I', d[0x20:0x24])[0]
    data_base = len(d) - data_size
    n = len(d) // 4
    u32 = np.frombuffer(d[:n * 4], dtype='<u4')
    k = np.arange(len(u32) - 12)
    fmt = u32[k + 5]
    mips = u32[k + 7]
    w = u32[k + 8]
    h = u32[k + 9]
    size = u32[k + 2]
    doff = u32[k].astype(np.uint64) | (u32[k + 1].astype(np.uint64) << np.uint64(32))
    ok = ((fmt == 0x47) | (fmt == 0x48) | (fmt == 0x50) | (fmt == 0x51))
    ok &= (mips > 0) & (mips <= 13)
    ok &= (w > 0) & (w <= 8192) & (h > 0) & (h <= 8192)
    ok &= (size > 0) & (size <= data_size)
    ok &= (doff + size) <= data_size
    idx = np.nonzero(ok)[0]
    out, seen = [], set()
    for i in idx:
        off = int(i) * 4
        dataoff = int(doff[i])
        if dataoff in seen:
            continue
        seen.add(dataoff)
        m = None
        for mm in NAME_RE.finditer(d, max(0, off - 4096), off):
            m = mm
        name = m.group(1).decode('utf-8', 'replace') if m else f'@0x{dataoff:x}'
        out.append(dict(name=name, dataoff=dataoff, size=int(size[i]), fmt=int(fmt[i]),
                        mips=int(mips[i]), w=int(w[i]), h=int(h[i]),
                        file_off=data_base + dataoff))
    return out, data_base, data_size, len(d)
