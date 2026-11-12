#!/usr/bin/env python3
"""
hd2suite / tests/check.py - checks that need no window. Run with any Python 3, also the bundled one:

    python tests/check.py [folder with .sav files]

Covers the part that must never be wrong: the save container (LZ4, crc32, body hash) and the item lists.
With a folder of saves, every file in it is read, re-packed and read back (the files are only read).
Exit code 0 = all passed.
"""
import os, io, sys, glob, random, struct, zlib, contextlib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import testament, savecore

done = []
def check(name, fn):
    try:
        with contextlib.redirect_stderr(io.StringIO()): note = fn()      # parse() warns on stderr about the deliberately damaged files
    except Exception as e: print('FAIL  %s: %s: %s' % (name, type(e).__name__, e)); done.append(False); return
    print('ok    %s%s' % (name, '  (%s)' % note if note else '')); done.append(True)


def blocks(rng):
    """test data of the kinds a save body is made of, at sizes around the format's limits"""
    for n in (0, 1, 4, 5, 12, 13, 14, 19, 20, 64, 255, 256, 4096, 65535, 65536):
        yield bytes(n); yield rng.randbytes(n)
        b = bytearray(n)
        for _ in range(n // 150): o = rng.randrange(n); b[o:o + 6] = rng.randbytes(6)[:n - o]
        yield bytes(b)
        w = [rng.randbytes(rng.randrange(1, 9)) for _ in range(8)]; rep = bytearray()
        while len(rep) < n: rep += rng.choice(w) * rng.randrange(1, 20)
        yield bytes(rep[:n])


def lz4_round_trip():
    try: import lz4.block as ref
    except ImportError: ref = None
    n = 0
    for src in blocks(random.Random(1)):
        c = testament.lz4_compress(src)
        assert testament.lz4_decompress(c) == src, 'own decoder, %d bytes' % len(src)
        if ref and src:
            assert ref.decompress(c, uncompressed_size=len(src)) == src, 'reference decoder, %d bytes' % len(src)
            assert testament.lz4_decompress(ref.compress(src, store_size=False)) == src, 'reference compressor, %d bytes' % len(src)
        n += 1
    return '%d blocks%s' % (n, ', also against the lz4 package' if ref else '; lz4 package not installed, own decoder only')


def lz4_damaged():
    rng = random.Random(2); c = testament.lz4_compress(bytes(300) + rng.randbytes(300) + bytes(300))
    for cut in range(1, len(c)):
        try: testament.lz4_decompress(c[:cut])
        except ValueError: pass       # anything else (IndexError, a hang) fails the check


def hash_known_answers():
    # MurmurHash64A, seed 0. The expected values come from the public reference implementation (MurmurHash2.cpp, C).
    for data, want in ((b'', 0x0), (b'a', 0x071717d2d36b6b11), (b'testament', 0x7f1b9fd95ad13232), (bytes(range(64)), 0xf22ae58d36c6dd7e)):
        got = testament.murmur64(data); assert got == want, '%r -> %016x, expected %016x' % (data[:9], got, want)
    assert testament.murmur64(b'booster_free_eat') >> 32 == 1213901450      # how the game makes a booster's id from its name


def body(version, n=70000):
    """a synthetic body with the fields the container needs: version, [extra], length, hash"""
    b = bytearray(random.Random(version).randbytes(n)); b[0:4] = struct.pack('<I', version); o = 8 if version >= 0x107 else 4
    struct.pack_into('<I', b, o, n); return testament.fix_body_hash(bytes(b))


def container():
    for version in (0xFE, 0x107):
        for kind in ('local', 'cloud'):
            b = body(version); f = testament.build(b, b'', kind); p = testament.parse(f)
            assert p['kind'] == kind and p['body'] == b and p['crc_ok'] and p['hash_ok'] and p['trailing'] == 0, (hex(version), kind)
            base = 12 if kind == 'cloud' else 0
            assert struct.unpack_from('<I', f, base)[0] == zlib.crc32(f[base + 4:]) and struct.unpack_from('<I', f, base + 4)[0] == len(f) - base - 16
            bad = bytearray(f); bad[-1] ^= 1; assert not testament.parse(bytes(bad))['crc_ok'], 'a changed byte must fail the crc'
            edited = bytearray(b); edited[100] ^= 1
            assert not testament.body_hash_ok(bytes(edited)) and testament.body_hash_ok(testament.fix_body_hash(bytes(edited)))
    return 'both body layouts, local and cloud'


def item_lists():
    it = savecore.load_items(); pools = dict(kits=it['kits'], weapons=it['weapons'], stratagems=it['stratagems'], other=it['other'], **{'misc.' + k: v for k, v in it['misc'].items()})
    for name, pool in pools.items():
        assert pool, name + ' is empty'; assert all(0 < i < 2 ** 32 for i in pool), name + ' has an id that is 0 (= empty slot) or not a u32'
    assert all(k['kind'] in ('Helmet', 'Armor', 'Cape') and k['name'] for k in it['kits'].values())
    assert all(w['type'] and w['name'] for w in it['weapons'].values())
    for slot, _, _, cat in savecore.SLOTS:
        if cat.startswith('misc:'):
            sub = cat[5:]; ids = it['types'].get(sub); assert ids, 'no id list for ' + sub
            assert len(ids) == len(set(ids)); assert set(it['misc'].get(sub, {})) <= set(ids), sub + ': a named id is not in the game list'
    kinds = [set(v) for v in it['types'].values()]
    assert sum(len(k) for k in kinds) == len(set().union(*kinds)), 'an id is listed under two kinds'
    return '%d kits, %d weapons, %d stratagems, %d character items' % (len(it['kits']), len(it['weapons']), len(it['stratagems']), sum(len(k) for k in kinds))


def saves(folder):
    def run():
        it = savecore.load_items(); files = sorted(glob.glob(os.path.join(folder, '*.sav'))); assert files, 'no .sav files in ' + folder
        versions = set()
        for f in files:
            s = savecore.Save(f, it); versions.add(s.version); booster = [i for i in it['types']['booster'] if i != s.original['booster']][0]
            for changes in ({}, {'booster': booster}, {'helmet': s.original['armor'], 'title': it['types']['title'][0]}):
                p = testament.parse(s.build(changes)); assert p['crc_ok'] and p['hash_ok'] and p['kind'] == s.kind, os.path.basename(f)
                t = savecore.Save.__new__(savecore.Save); t.body = bytearray(p['body']); t.offsets = s.offsets
                assert t.values() == {**s.original, **changes}, os.path.basename(f)
            if s.crc_ok and s.hash_ok: assert testament.parse(s.build({}))['body'] == bytes(s.body), os.path.basename(f) + ': unchanged body must come back identical'
            for dump in (savecore.dump_text, savecore.dump_json, savecore.dump_csv): assert dump(s)
        return '%d files, formats %s' % (len(files), ', '.join(sorted('0x%x' % v for v in versions)))
    return run


if __name__ == '__main__':
    check('LZ4: compress and read back', lz4_round_trip)
    check('LZ4: damaged blocks are refused cleanly', lz4_damaged)
    check('body hash: known answers', hash_known_answers)
    check('container: build, read back, detect changes', container)
    check('item lists', item_lists)
    for folder in sys.argv[1:]: check('saves in %s' % folder, saves(folder))
    print('%d of %d checks passed' % (sum(done), len(done)))
    sys.exit(0 if all(done) else 1)
