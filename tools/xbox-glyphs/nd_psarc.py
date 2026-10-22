#!/usr/bin/env python3
"""Naughty Dog psarc (UDC/TLOU variant), empirically validated:
32B header | TOC [32, toc_end): entryCount+1 entries x 30B
(md5[16], u32 idx, u40 len, u40 off) | u16 BE block-size array
(0 = full stored block). Blocks: size==len chunk -> stored, else zlib."""
import struct, zlib, hashlib, sys

class Psarc:
    def __init__(self, path):
        self.f = open(path, 'rb')
        h = self.f.read(32)
        assert h[:4] == b'PSAR'
        (self.toc_end, self.ent_size, self.count, self.block_size,
         self.flags) = struct.unpack('>IIIII', h[12:32])
        n_ents = self.count
        self.f.seek(32 + n_ents * 30)
        n = (self.toc_end - (32 + n_ents * 30)) // 2
        self.sizes = struct.unpack('>%dH' % n, self.f.read(2 * n))
        self.f.seek(32)
        self.entries = []
        for _ in range(n_ents):
            e = self.f.read(30)
            idx, = struct.unpack('>I', e[16:20])
            ln = (e[20] << 32) | struct.unpack('>I', e[21:25])[0]
            off = (e[25] << 32) | struct.unpack('>I', e[26:30])[0]
            self.entries.append({'md5': e[:16], 'idx': idx, 'len': ln, 'off': off})
        man = self.read(0)
        names = [l.strip('\x00\r') for l in man.decode('utf-8', 'replace').split('\n') if l.strip('\x00\r')]
        self.names = {hashlib.md5(n.encode()).digest(): n for n in names}
        self.by_name = {}
        for i, e in enumerate(self.entries):
            if e['md5'] in self.names:
                e['name'] = self.names[e['md5']]
                self.by_name[e['name']] = i

    def read(self, i):
        e = self.entries[i]
        out, off, left, k = b'', e['off'], e['len'], e['idx']
        while left > 0:
            dsz = min(self.block_size, left)
            v = self.sizes[k]
            if v == 0:
                v = dsz                # stored block, full remainder of the block
            self.f.seek(off)
            raw = self.f.read(v)
            if v == dsz:
                out += raw             # stored
            else:
                out += zlib.decompress(raw)
            off += v
            left -= dsz
            k += 1
        return out[:e['len']]

if __name__ == '__main__':
    cmd, path = sys.argv[1], sys.argv[2]
    p = Psarc(path)
    if cmd == 'list':
        pat = sys.argv[3].lower() if len(sys.argv) > 3 else ''
        for e in p.entries:
            n = e.get('name', '#' + e['md5'].hex()[:8])
            if pat in n.lower():
                print(f"{e['len']:>10}  {n}")
    else:
        name, out = sys.argv[3], sys.argv[4]
        open(out, 'wb').write(p.read(p.by_name[name]))
        print(f"extracted -> {out}")
