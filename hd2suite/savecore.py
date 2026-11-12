#!/usr/bin/env python3
"""
hd2suite / savecore.py - the part of the loadout save editor that has no window: find saves, read the loadout
slots, change them, write a valid file (crc32 + body hash handled by testament.py), and the item lists in data/.

Used by modules/loadout.py. The save format is described at the top of testament.py.
"""
import os, re, sys, json, struct, time, shutil, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import testament

APP_ID = '553850'
SAVE_NAME = 'testament_new.sav'
# body layouts seen so far: version -> offset of the helmet slot (body type sits 4 bytes before it, weapons near the start)
KIT_OFFSET = {0xFE: 285, 0x100: 285, 0x107: 289}

# slot key, label, group, option category
SLOTS = [
    ('helmet', 'Helmet', 'ARMOR', 'kit:Helmet'), ('armor', 'Armor', 'ARMOR', 'kit:Armor'), ('cape', 'Cape', 'ARMOR', 'kit:Cape'),
    ('primary', 'Primary', 'WEAPONS', 'weapon:PrimaryWeapon'), ('secondary', 'Secondary', 'WEAPONS', 'weapon:SidearmWeapon'),
    ('grenade', 'Throwable', 'WEAPONS', 'weapon:ThrowableWeapon'),
    ('strat1', 'Stratagem 1', 'STRATAGEMS', 'strat'), ('strat2', 'Stratagem 2', 'STRATAGEMS', 'strat'),
    ('strat3', 'Stratagem 3', 'STRATAGEMS', 'strat'), ('strat4', 'Stratagem 4', 'STRATAGEMS', 'strat'),
    ('booster', 'Booster', 'CHARACTER', 'misc:booster'), ('body', 'Body type', 'CHARACTER', 'misc:body'),
    ('voice', 'Voice pack', 'CHARACTER', 'misc:voice'), ('pose', 'Victory pose', 'CHARACTER', 'misc:pose'),
    ('card', 'Player card', 'CHARACTER', 'misc:card'), ('title', 'Title', 'CHARACTER', 'misc:title'),
]
KIT_SLOTS = ('helmet', 'armor', 'cape')


def read_bytes(path):
    with open(path, 'rb') as f: return f.read()


def read_json(path):
    with open(path, encoding='utf-8') as f: return json.load(f)


def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=1, ensure_ascii=False)


def slug(name):
    """'Free of Thought' -> 'free_of_thought' (picture file names)"""
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def load_items(path=None):
    """data/items.json: names by id. data/item_types.json (optional): which ids the game files under each character slot."""
    path = path or os.path.join(HERE, 'data', 'items.json'); d = read_json(path)
    it = dict(kits={int(k): v for k, v in d['kits'].items()}, weapons={int(k): v for k, v in d['weapons'].items()},
              stratagems={int(k): v for k, v in d['stratagems'].items()},
              misc={s: {int(k): v for k, v in m.items()} for s, m in d['misc'].items()},
              other={int(k): v for k, v in d.get('other', {}).items()})
    tp = os.path.join(os.path.dirname(path), 'item_types.json')
    it['types'] = {s: [int(x) for x in l] for s, l in read_json(tp)['types'].items()} if os.path.exists(tp) else {}
    return it


def item_name(items, slot, vid):
    """-> (name, kind) for display; kind is the kit kind / weapon type / '' """
    if vid == 0: return '(empty)', ''
    if slot.startswith('strat') and vid in items['stratagems']: return items['stratagems'][vid], 'Stratagem'
    if vid in items['kits']: k = items['kits'][vid]; return k['name'], k['kind']
    if vid in items['weapons']: w = items['weapons'][vid]; return w['name'], w['type']
    if vid in items['stratagems']: return items['stratagems'][vid], 'Stratagem'
    for s, m in items['misc'].items():
        if vid in m: return m[vid], s
    if vid in items['other']: return items['other'][vid], ''
    return 'unknown id %d' % vid, ''


# ------------------------------------------------------------------ finding save files
def steam_roots():
    roots = []
    if os.name == 'nt':
        try:
            import winreg
            for hive, key, val in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                                   (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')):
                try:
                    with winreg.OpenKey(hive, key) as k: roots.append(os.path.normpath(winreg.QueryValueEx(k, val)[0]))
                except OSError: pass
        except ImportError: pass
        for env in ('ProgramFiles(x86)', 'ProgramFiles'):
            if os.environ.get(env): roots.append(os.path.join(os.environ[env], 'Steam'))
    out = []
    for r in roots:
        if r and os.path.isdir(r) and r.lower() not in [x.lower() for x in out]: out.append(r)
    return out


def find_saves(kind):
    """-> list of candidate save paths, newest first. kind 'local' (AppData) or 'cloud' (Steam userdata)."""
    c = []
    if kind == 'local':
        base = os.environ.get('APPDATA')
        if base: c = glob.glob(os.path.join(base, 'Arrowhead', 'Helldivers2', 'saves', '*_' + SAVE_NAME))
    else:
        for r in steam_roots():
            c += glob.glob(os.path.join(r, 'userdata', '*', APP_ID, 'remote', SAVE_NAME))
    c = [p for p in c if os.path.isfile(p)]
    return sorted(set(c), key=lambda p: -os.path.getmtime(p))


def process_running(image):
    """True / False, or None when it cannot be checked (not Windows)."""
    if os.name != 'nt': return None
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ' + image, '/NH'], capture_output=True, text=True,
                             creationflags=0x08000000).stdout
        return image.lower() in out.lower()
    except Exception:
        return None


# ------------------------------------------------------------------ one save file
class Save:
    def __init__(self, path, items):
        self.path = path; self.items = items
        self.raw = read_bytes(path)
        p = testament.parse(self.raw)
        self.kind = p['kind']; self.crc_ok = p['crc_ok']; self.hash_ok = p['hash_ok']
        self.body = bytearray(p['body'])
        if len(self.body) < 1024: raise ValueError('the save body is only %d bytes long' % len(self.body))
        self.version = struct.unpack_from('<I', self.body, 0)[0]; self.known_version = self.version in KIT_OFFSET
        off = self._find_kits()
        w0 = 17 if self.version >= 0x107 else 13
        self.offsets = dict(primary=w0, secondary=w0 + 4, grenade=w0 + 8, strat1=w0 + 12, strat2=w0 + 20, strat3=w0 + 28,
                            strat4=w0 + 36, body=off - 4, helmet=off, cape=off + 4, armor=off + 8, booster=off + 12,
                            voice=off + 16, pose=off + 20, card=off + 24, title=off + 32)
        self.original = self.values(); self.kit_offset = off
        self.seen = self._seen()

    def _find_kits(self):
        """offset of the helmet slot: the first three kit ids in a row; if a slot holds an id that is not in items.json
        (an item newer than the list), the place this body version keeps them, checked by the body type next to it."""
        kits = self.items['kits']; b = self.body
        for o in range(0, 1024 - 12):
            if all(v in kits for v in struct.unpack_from('<III', b, o)): return o
        o = KIT_OFFSET.get(self.version)
        if o and struct.unpack_from('<I', b, o - 4)[0] in set(self.items['types'].get('body', ())) | {0}: return o
        raise ValueError('could not find the helmet / cape / armor slots in this save (format 0x%x)' % self.version)

    def _seen(self):
        """ids that appear in the save's own item lists (items this profile has equipped / acknowledged before), plus
        what is equipped right now. NOT an ownership list: ownership is decided by the server. A blank profile has none."""
        it = self.items; known = set(it['kits']) | set(it['weapons']) | set(it['stratagems']) | set(it['other'])
        for m in list(it['misc'].values()) + list(it['types'].values()): known |= set(m)
        out = set(); b = self.body
        for o in range(400 + (self.kit_offset - 400) % 4, len(b) - 4, 4):
            v = struct.unpack_from('<I', b, o)[0]
            if v and v in known: out.add(v)
        if len(out & set(it['kits'])) < 5: return set()      # a fresh profile: stray matches only, no usable history
        return out | {v for v in self.original.values() if v}

    def values(self):
        return {k: struct.unpack_from('<I', self.body, o)[0] for k, o in self.offsets.items()}

    def build(self, changes, kind=None):
        """-> bytes of a complete save with the given {slot: id} applied (does not modify self)."""
        b = bytearray(self.body)
        for k, v in changes.items(): struct.pack_into('<I', b, self.offsets[k], int(v) & 0xffffffff)
        data = testament.build(bytes(b), self.raw, kind or self.kind)
        chk = testament.parse(data)
        if not (chk['crc_ok'] and chk['hash_ok']): raise ValueError('internal check failed: the new file is not valid')
        got = {k: struct.unpack_from('<I', chk['body'], o)[0] for k, o in self.offsets.items()}
        want = dict(self.original); want.update({k: int(v) for k, v in changes.items()})
        if got != want: raise ValueError('internal check failed: the new file does not read back as intended')
        return data


def backup_and_write(save, data, backup_dir, changes):
    """Copy the current file into backup_dir (timestamped), then replace it with data. -> backup path"""
    os.makedirs(backup_dir, exist_ok=True)
    if read_bytes(save.path) != save.raw:
        raise IOError('the save file changed on disk since it was loaded. Load it again before applying.')
    stamp = time.strftime('%Y%m%d-%H%M%S'); n = 1
    bak = os.path.join(backup_dir, '%s_%s_%s' % (stamp, save.kind, os.path.basename(save.path)))
    while os.path.exists(bak):      # never write over an earlier backup
        n += 1; bak = os.path.join(backup_dir, '%s-%d_%s_%s' % (stamp, n, save.kind, os.path.basename(save.path)))
    shutil.copy2(save.path, bak)
    if read_bytes(bak) != save.raw: raise IOError('backup verification failed; nothing was changed')
    tmp = save.path + '.hd2suite.tmp'
    try:
        with open(tmp, 'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, save.path)
    finally:
        if os.path.exists(tmp): os.remove(tmp)      # only left behind when the replace failed
    if read_bytes(save.path) != data: raise IOError('write verification failed; restore from ' + bak)
    with open(os.path.join(backup_dir, 'receipts.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(dict(time=stamp, file=save.path, kind=save.kind, backup=bak,
                                changes={k: [save.original[k], int(v)] for k, v in changes.items()})) + '\n')
    return bak


# ------------------------------------------------------------------ dumps (for people who want to look at the data)
def dump_text(save):
    """annotated listing of the body: named ids, collapsed zero / FF runs, hex for the rest"""
    it = save.items; names = {}
    for vid, k in it['kits'].items(): names[vid] = '%s %s' % (k['kind'], k['name'])
    for vid, w in it['weapons'].items(): names.setdefault(vid, '%s %s' % (w['type'], w['name']))
    for vid, n in it['stratagems'].items(): names.setdefault(vid, 'Stratagem ' + n)
    for s_, m in it['misc'].items():
        for vid, n in m.items(): names.setdefault(vid, '%s %s' % (s_, n))
    for vid, n in it['other'].items(): names.setdefault(vid, 'item ' + n)
    slot_at = {o: k for k, o in save.offsets.items()}
    b = bytes(save.body); n = len(b); lines = []; i = 0; pend = 0
    def hexrow(a, e):
        for p in range(a, e, 16):
            ch = b[p:min(p + 16, e)]
            lines.append('%08d  %-48s %s' % (p, ch.hex(' '), ''.join(chr(c) if 32 <= c < 127 else '.' for c in ch)))
    while i < n:
        if i in slot_at and i + 4 <= n:
            v = struct.unpack_from('<I', b, i)[0]; hexrow(pend, i)
            lines.append('%08d  u32 %-10d  [slot %s] %s' % (i, v, slot_at[i], names.get(v, ''))); i += 4; pend = i; continue
        c = b[i]
        if c in (0, 0xFF):
            j = i
            while j < n and b[j] == c and j not in slot_at: j += 1
            if j - i >= 8: hexrow(pend, i); lines.append('%08d  %d x %02x' % (i, j - i, c)); i = j; pend = i; continue
        if i + 4 <= n:
            v = struct.unpack_from('<I', b, i)[0]
            if v in names and v > 0xffff: hexrow(pend, i); lines.append('%08d  u32 %-10d  %s' % (i, v, names[v])); i += 4; pend = i; continue
        i += 1
    hexrow(pend, n)
    head = ['# Helldivers 2 testament save, %s container, body version 0x%x, %d bytes' % (save.kind, save.version, n),
            '# offset    content   (u32 = named id; "N x 00" = run of N equal bytes; the rest is hex)', '']
    return '\n'.join(head + lines) + '\n'


def dump_json(save):
    vals = save.values()
    return json.dumps(dict(file=save.path, container=save.kind, body_version=save.version, body_bytes=len(save.body),
                           crc_ok=save.crc_ok, body_hash_ok=save.hash_ok,
                           slots={k: dict(offset=save.offsets[k], id=v, name=item_name(save.items, k, v)[0]) for k, v in vals.items()},
                           used_before=sorted(save.seen)), indent=1, ensure_ascii=False)


def dump_csv(save):
    rows = ['slot,offset,id,name']
    for k, v in save.values().items(): rows.append('%s,%d,%d,"%s"' % (k, save.offsets[k], v, item_name(save.items, k, v)[0].replace('"', "'")))
    return '\n'.join(rows) + '\n'


def loadout_from_save(path, items):
    s = Save(path, items); cur = s.values()
    return dict(name=os.path.splitext(os.path.basename(path))[0], saved=time.strftime('%Y-%m-%d %H:%M'), source=path,
                slots=cur, names={k: item_name(items, k, v)[0] for k, v in cur.items()})
