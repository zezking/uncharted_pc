#!/usr/bin/env python3
"""ND big2/big3 .pak walker (UDC). Spec from icemesh/big2-ps3-pak-research.
LE fields; page-relative offsets; magic 0xA79 (UDC: 0x10A79)."""
import struct, sys

class Pak:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        (self.magic, self.hdr_size, self.login_idx, self.login_off,
         self.page_ct, self.page_table, self.num_fixup, self.fixup_off,
         self.data_size, self.vram_page, self.vram_off) = struct.unpack('<11I', self.d[:44])
        assert self.magic & 0xFFFF == 0x0A79, hex(self.magic)
        self.pages = []
        for i in range(self.page_ct):
            off, size, own = struct.unpack('<3I', self.d[self.page_table + i*12: self.page_table + i*12 + 12])
            self.pages.append((off, size, own))
        self.items = []          # (page_idx, name, type, item_off, unk)
        for pi, (poff, psize, own) in enumerate(self.pages):
            page = self.d[poff:poff+psize]
            unk, psz, unk2, n = struct.unpack('<4I', page[:16])
            for k in range(n):
                try:
                    e = page[16 + k*16: 16 + k*16 + 16]
                    if len(e) < 16: break
                    name64, = struct.unpack('<Q', e[:8])
                    rio, pad = struct.unpack('<2I', e[8:16])
                    if rio + 32 > len(page) or pad != 0x00012345:
                        continue
                    it = page[rio:rio+32]
                    no, to = struct.unpack('<2Q', it[:16])
                    unknum, = struct.unpack('<I', it[16:20])
                    if no >= len(page) or to >= len(page):
                        continue
                    name = page[no:].split(b'\0')[0].decode('utf-8', 'replace')
                    typ  = page[to:].split(b'\0')[0].decode('utf-8', 'replace')
                    self.items.append((pi, name, typ, poff + rio, unknum))
                except Exception:
                    continue

if __name__ == '__main__':
    p = Pak(sys.argv[1])
    print(f"magic={p.magic:#x} pages={p.page_ct} items={len(p.items)} data_size={p.data_size}")
    pat = sys.argv[2].lower() if len(sys.argv) > 2 else ''
    for pi, name, typ, off, unk in p.items:
        if pat in name.lower():
            print(f"  page{pi} @{off:#x} unk={unk:#x} [{typ}] {name}")
