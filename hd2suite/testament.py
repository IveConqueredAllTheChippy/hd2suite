#!/usr/bin/env python3
"""
hd2suite / testament.py - read and write Helldivers 2 "testament_new.sav" files (the player profile save).

Container (Nov 10-11, 2026; verified on 5 cloud and 11 local samples):
  local file  (AppData\\Roaming\\Arrowhead\\Helldivers2\\saves\\<id>_testament_new.sav):
      u32 crc32(everything after this field) | u32 size (file length - 16) | u32 V | u32 0xF0000001 | [inner]
  cloud file  (Steam userdata\\<id>\\553850\\remote\\testament_new.sav):
      u64 const cc237b5f6b1cfdd4 | u32 1 | then exactly a local file
  inner:  u32 V | u32 0 | then chunks: u32 compressed_size, LZ4 block (64 KiB uncompressed each; the last one
          is padded); V = total uncompressed length. The chunk list runs to the end of the file.
  body: u32 version | [version >= 0x107: u32 ?] | u32 body length | u32 body hash | ...
        body hash = low 32 bits of MurmurHash64A (seed 0) over the whole body with the hash field zeroed.
        The game also rejects a body whose hash is wrong (seen Nov 11: valid crc32, one edited field, profile reset).
  The game rejects a file whose crc32 is wrong and resets the profile to defaults (seen Nov 10: earlier versions of
  this tool copied the first 8 bytes of a local template instead of recomputing them).

usage:
  testament.py decode <file.sav> [out.bin]          plaintext body (default: <file>.bin)
  testament.py encode <body.bin> <template.sav> <out.sav>   re-pack a (possibly edited) body in the template's container
  testament.py info <file.sav>
"""
import os, sys, struct, zlib

MAGIC = 0xF0000001
CLOUD_CONST = 0xcc237b5f6b1cfdd4
CHUNK = 65536


def lz4_decompress(src):
    """LZ4 block -> bytes. Raises ValueError on a damaged block."""
    try: return _lz4_decompress(src)
    except IndexError: raise ValueError('lz4: block ends in the middle of a sequence') from None


def _lz4_decompress(src):
    out = bytearray(); i = 0; n = len(src)
    while i < n:
        tok = src[i]; i += 1
        ll = tok >> 4
        if ll == 15:
            while True:
                x = src[i]; i += 1; ll += x
                if x != 255: break
        if i + ll > n: raise ValueError('lz4: literals past end')
        out += src[i:i + ll]; i += ll
        if i >= n: break
        off = src[i] | (src[i + 1] << 8); i += 2
        if off == 0 or off > len(out): raise ValueError('lz4: bad offset')
        ml = tok & 15
        if ml == 15:
            while True:
                x = src[i]; i += 1; ml += x
                if x != 255: break
        ml += 4
        start = len(out) - off
        for k in range(ml): out.append(out[start + k])
    return bytes(out)


def lz4_compress(src):
    """bytes -> LZ4 block. Greedy, one candidate per 4-byte key, window 65535: valid, not optimal (a little larger than
    the game's own output). Keeps the format's end rules: the last match starts at least 12 bytes before the end of
    the block and the last 5 bytes are literals. This is the only compressor the tool uses, so that every copy of it
    writes the same bytes; tests/check.py checks it against the reference decoder when the lz4 package is installed."""
    n = len(src); out = bytearray(); i = 0; lit = 0; table = {}
    def emit(lit_start, lit_len, ml, off):
        tok_l = 15 if lit_len >= 15 else lit_len
        tok_m = 15 if ml >= 19 else max(ml - 4, 0)
        out.append((tok_l << 4) | tok_m)
        if lit_len >= 15:
            r = lit_len - 15
            while r >= 255: out.append(255); r -= 255
            out.append(r)
        out.extend(src[lit_start:lit_start + lit_len])
        if ml:
            out.append(off & 255); out.append(off >> 8)
            if ml >= 19:
                r = ml - 19
                while r >= 255: out.append(255); r -= 255
                out.append(r)
    while i < n - 12:
        key = src[i:i + 4]; cand = table.get(key); table[key] = i
        if cand is not None and i - cand <= 65535:
            ml = 4
            while i + ml < n - 5 and src[cand + ml] == src[i + ml]: ml += 1
            emit(lit, i - lit, ml, i - cand)
            i += ml; lit = i
        else:
            i += 1
    emit(lit, n - lit, 0, 0)
    return bytes(out)


M64 = (1 << 64) - 1


def murmur64(b, seed=0):
    m = 0xc6a4a7935bd1e995; n = len(b); h = (seed ^ (n * m)) & M64; n8 = n - n % 8
    for k in struct.unpack_from('<%dQ' % (n8 // 8), b, 0):
        k = (k * m) & M64; k ^= k >> 47; k = (k * m) & M64; h ^= k; h = (h * m) & M64
    if n % 8: h ^= int.from_bytes(b[n8:], 'little'); h = (h * m) & M64
    h ^= h >> 47; h = (h * m) & M64; h ^= h >> 47
    return h


def body_hash_offset(body):
    """offset of the u32 body hash (right after the u32 that equals the body length), or None"""
    for o in (4, 8):
        if len(body) >= o + 8 and struct.unpack_from('<I', body, o)[0] == len(body): return o + 4
    return None


def body_hash(body):
    o = body_hash_offset(body)
    if o is None: return None
    z = bytearray(body); z[o:o + 4] = b'\0\0\0\0'
    return murmur64(bytes(z)) & 0xffffffff


def body_hash_ok(body):
    o = body_hash_offset(body)
    return o is not None and struct.unpack_from('<I', body, o)[0] == body_hash(body)


def fix_body_hash(body):
    """-> body with its hash field recomputed (call after any edit)"""
    o = body_hash_offset(body)
    if o is None: raise ValueError('body length field not found: cannot fix the body hash')
    b = bytearray(body); struct.pack_into('<I', b, o, body_hash(body)); return bytes(b)


def parse(data):
    """-> dict(kind, V, body, chunks, trailing, crc_ok, hash_ok). Problems the game would reject are flagged, not raised."""
    if len(data) >= 36 and struct.unpack_from('<Q', data, 0)[0] == CLOUD_CONST and struct.unpack_from('<I', data, 24)[0] == MAGIC:
        kind = 'cloud'; base = 12
    elif len(data) >= 24 and struct.unpack_from('<I', data, 12)[0] == MAGIC:
        kind = 'local'; base = 0
    else:
        raise ValueError('not a testament save (magic not found)')
    crc, size, V = struct.unpack_from('<III', data, base); inner = base + 16
    crc_ok = crc == (zlib.crc32(data[base + 4:]) & 0xffffffff) and size == len(data) - base - 16
    if not crc_ok: print('warning: crc32 or size field does not match (the game would reject this file)', file=sys.stderr)
    V2 = struct.unpack_from('<I', data, inner)[0]      # followed by a u32 that is always 0
    if V2 != V: print('warning: inner length %d != header %d' % (V2, V), file=sys.stderr)
    pos = inner + 8; body = bytearray(); chunks = []
    while pos + 4 <= len(data):
        sz = struct.unpack_from('<I', data, pos)[0]
        if sz == 0 or pos + 4 + sz > len(data): break
        d = lz4_decompress(data[pos + 4:pos + 4 + sz]); chunks.append((pos, sz, len(d))); body += d; pos += 4 + sz
    body = bytes(body[:V]); hash_ok = body_hash_ok(body)
    if not hash_ok: print('warning: body hash does not match (the game would reject this file)', file=sys.stderr)
    return dict(kind=kind, V=V, body=body, chunks=chunks, trailing=len(data) - pos, crc_ok=crc_ok, hash_ok=hash_ok)


def build(body, template, kind=None):
    """Pack body into a container. kind 'local' / 'cloud'; default: the same kind as template (bytes)."""
    kind = kind or parse(template)['kind']
    body = fix_body_hash(body)
    V = len(body)
    inner = struct.pack('<II', V, 0)
    padded = body + bytes((-len(body)) % CHUNK)
    for k in range(0, len(padded), CHUNK):
        c = lz4_compress(padded[k:k + CHUNK]); inner += struct.pack('<I', len(c)) + c
    rest = struct.pack('<II', V, MAGIC) + inner               # everything after the size field
    tail = struct.pack('<I', len(rest) - 8) + rest            # size = file length - 16 (local numbering)
    local = struct.pack('<I', zlib.crc32(tail) & 0xffffffff) + tail
    return local if kind == 'local' else struct.pack('<QI', CLOUD_CONST, 1) + local


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    def read(path):
        with open(path, 'rb') as f: return f.read()
    def write(path, data):
        with open(path, 'wb') as f: f.write(data)
    if a[0] == 'decode':
        out = a[2] if len(a) > 2 else os.path.splitext(a[1])[0] + '.bin'
        if os.path.exists(out): raise SystemExit('%s exists; give another output name' % out)
        p = parse(read(a[1])); write(out, p['body'])
        print('%s: %s container, body %d bytes, %d chunks, %d trailing bytes -> %s' % (a[1], p['kind'], len(p['body']), len(p['chunks']), p['trailing'], out))
    elif a[0] == 'encode':
        body = read(a[1]); tpl = read(a[2]); out = build(body, tpl); chk = parse(out)
        if not (chk['body'] == fix_body_hash(body) and chk['crc_ok'] and chk['hash_ok']): raise SystemExit('round trip failed; nothing written')
        write(a[3], out)
        print('wrote %s (%d bytes, %s container), round trip OK' % (a[3], len(out), parse(tpl)['kind']))
    elif a[0] == 'info':
        p = parse(read(a[1]))
        print('kind %s  V %d  crc/size %s  chunks %s  trailing %d' % (p['kind'], p['V'], ('OK' if p['crc_ok'] else 'BAD') + '  body hash ' + ('OK' if p['hash_ok'] else 'BAD'), [(s, u) for _, s, u in p['chunks']], p['trailing']))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
