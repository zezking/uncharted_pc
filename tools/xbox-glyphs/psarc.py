#!/usr/bin/env python3
"""Minimal PSARC (PS4) list/extract. Format: 'PSAR' header, zlib TOC with
(count+1) entries: 16-byte MD5 name, u64 BE offset, u40 BE length; then (count+1)
u32 BE log2 block sizes per entry-block table is per-entry block size list."""
import struct, sys, zlib, hashlib, os

def read_header(f):
    magic, maj, mn, toc_len, ent_size, ent_count, block_size = struct.unpack('>IHHIIII', f.read(28))
    assert magic == 0x50534152, 'not PSAR'
    return toc_len, ent_size, ent_count, block_size

def md5(s): return hashlib.md5(s.encode()).digest()

def open_psarc(path):
    f = open(path, 'rb')
    toc_len, ent_size, ent_count, block_size = read_header(f)
    toc = zlib.decompress(f.read(toc_len - 28))
    entries = []
    off = 0
    for i in range(ent_count + 1):
        name = toc[off:off+16]; off += 16
        eoff, = struct.unpack('>Q', toc[off:off+8]); off += 8
        elen = int.from_bytes(toc[off:off+5], 'big'); off += 5
        entries.append({'md5': name, 'off': eoff, 'len': elen, 'blocks': []})
    # per-entry block size exponents
    for e in entries:
        n = (e['len'] + block_size - 1) // block_size if e['len'] else 0
        for _ in range(max(1, n) if e['len'] else 0):
            v, = struct.unpack('>I', toc[off:off+4]); off += 4
            e['blocks'].append(v)
    return f, entries, block_size, toc

def read_entry(f, e, block_size):
    f.seek(e['off'])
    data = b''
    for v in e['blocks']:
        raw = f.read(block_size if v == 0 else 1 << v)
        data += raw
        if len(data) >= e['len']:
            break
    return data[:e['len']]

if __name__ == '__main__':
    path = sys.argv[1]
    f, entries, block_size, toc = open_psarc(path)
    # name table: entry 0 is 'Path.txt' manifest
    pt = md5('Path.txt')
    manifest = None
    for e in entries:
        if e['md5'] == pt:
            manifest = read_entry(f, e, block_size)
    print(f"{path}: {len(entries)-1} entries, block {block_size}")
    if manifest:
        names = manifest.decode(errors='replace').split('\n')
        print(f"manifest: {len(names)} names")
        with open(os.path.basename(path) + '.names', 'w') as out:
            out.write(manifest.decode(errors='replace'))
        # map md5->name
        by_md5 = {md5(n.strip()): n.strip() for n in names if n.strip()}
        hit = sum(1 for e in entries if e['md5'] in by_md5)
        print(f"named: {hit}/{len(entries)-1}")
        for e in entries:
            n = by_md5.get(e['md5'])
            if n and 'hud/buttons' in n:
                print(f"  {n}  ({e['len']} bytes)")
