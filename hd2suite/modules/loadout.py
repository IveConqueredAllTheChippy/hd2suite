#!/usr/bin/env python3
"""
hd2suite module: LOADOUT - edit the loadout stored in testament_new.sav (local or Steam Cloud).

Pick the source, LOAD, change slots (type to filter, arrows + Enter, or click a tile), then APPLY (backup first)
or EXPORT a copy. Mission-only fields (stratagems, booster) are hidden until asked for.
"""
import os, time, re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import savecore
from savecore import SLOTS, KIT_SLOTS, slug
from theme import BG, PANEL, TILE, YELLOW, GREEN, ORANGE, RED, TEXT, MUTED, FONT, AutoCombo

MISSION = ('strat1', 'strat2', 'strat3', 'strat4', 'booster')
LABEL = {k: l for k, l, _, _ in SLOTS}
CAT = {k: c for k, _, _, c in SLOTS}
WEAPON_SLOTS = ('primary', 'secondary', 'grenade')
# what a slot's FILTER dialog can show: (value in items.json, label in the dialog, tag in the list)
KIT_KINDS = (('Helmet', 'Helmets', 'HELMET'), ('Armor', 'Armors', 'ARMOR'), ('Cape', 'Capes', 'CAPE'))
WEAPON_KINDS = (('PrimaryWeapon', 'Primaries', 'PRIMARY'), ('SidearmWeapon', 'Secondaries', 'SECONDARY'), ('ThrowableWeapon', 'Throwables', 'THROWABLE'),
                ('SupportWeapon', 'Support weapons', 'SUPPORT'), ('Backpack', 'Backpacks', 'BACKPACK'), ('PermanentGear', 'Other gear', 'GEAR'))
KINDS = {**{s: KIT_KINDS for s in KIT_SLOTS}, **{s: WEAPON_KINDS for s in WEAPON_SLOTS}}
OWN = {s: CAT[s].split(':')[1] for s in KINDS}      # the kind a slot is meant for
ALL_PERKS = 'All perks'
BANG = '   (!)'

CLOUD_STEPS = ('Cloud saves only take effect with this exact order:\n\n'
               '  1. Disable Steam Cloud for Helldivers 2\n  2. Exit Steam completely\n'
               '  3. Apply here (replaces testament_new.sav)\n  4. Start Steam\n'
               '  5. Enable Steam Cloud again\n  6. Start the game\n\n'
               'If Steam is running while the file is replaced, the game throws the file away and creates a default profile.')
NOT_USED = ('These items have never been used on this profile, so the save gives no sign that you own them:\n\n%s\n\n'
            'If the game finds an item you do not own, there is a high chance it deletes the save and replaces it with a '
            'default B-01 profile. Continue anyway?')


def perk_name(p): return re.sub(r'\s*\(\d+\)\s*$', '', p or '').strip()


class LoadoutPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app; self.items = savecore.load_items(); self.save = None
        self.combos = {}; self.rows = {}; self.photos = {}; self.rects = []; self.fbtn = {}; self.fdialog = None
        self.kind = tk.StringVar(value=app.settings.get('source', 'local')); self.path = tk.StringVar()
        self.seen_only = tk.BooleanVar(value=False); self.mission = tk.BooleanVar(value=bool(app.settings.get('show_mission_fields')))
        self.filt = {s: dict(kinds={k: tk.BooleanVar(value=(k == OWN[s])) for k, _, _ in KINDS[s]}, perk=tk.StringVar(value=ALL_PERKS)) for s in KINDS}
        self._top(); self._main(); self._bottom()
        self.kind.trace_add('write', lambda *a: self.detect()); self.detect()
        if '--open' in app.argv[:-1]: self.path.set(app.argv[app.argv.index('--open') + 1]); self.load()

    # ---------------------------------------------------------------- source
    def _top(self):
        f = ttk.Frame(self, padding=(18, 14, 18, 8)); f.pack(fill='x')
        ttk.Label(f, text='LOADOUT SAVE EDITOR', style='Title.TLabel').grid(row=0, column=0, columnspan=6, sticky='w')
        tk.Frame(f, bg=YELLOW, height=2).grid(row=1, column=0, columnspan=6, sticky='ew', pady=(4, 10))
        ttk.Radiobutton(f, text='LOCAL SAVE', variable=self.kind, value='local').grid(row=2, column=0, sticky='w', padx=(0, 14))
        ttk.Radiobutton(f, text='STEAM CLOUD SAVE', variable=self.kind, value='cloud').grid(row=2, column=1, sticky='w', padx=(0, 18))
        self.pathbox = ttk.Combobox(f, textvariable=self.path); self.pathbox.grid(row=2, column=2, sticky='ew')
        ttk.Button(f, text='BROWSE', width=9, command=self.browse).grid(row=2, column=3, padx=(8, 0))
        ttk.Button(f, text='LOAD', style='Go.TButton', width=8, command=self.load).grid(row=2, column=4, padx=(8, 0))
        self.where = ttk.Label(f, text='', style='MutedBG.TLabel'); self.where.grid(row=3, column=2, columnspan=3, sticky='w', pady=(3, 0))
        f.columnconfigure(2, weight=1)

    def detect(self):
        found = savecore.find_saves(self.kind.get()); self.pathbox['values'] = found; self.path.set(found[0] if found else '')
        hint = r'%APPDATA%\Arrowhead\Helldivers2\saves\<number>_testament_new.sav' if self.kind.get() == 'local' else r'<Steam>\userdata\<your id>\553850\remote\testament_new.sav'
        self.where.config(text=('found %d save file(s); ' % len(found) if found else 'none found automatically; type the path or BROWSE.  ') + 'expected: ' + hint)

    def browse(self):
        start = os.path.dirname(self.path.get()) if self.path.get() else None
        p = filedialog.askopenfilename(title='Choose a testament_new.sav file', initialdir=start, filetypes=[('Helldivers 2 save', '*.sav'), ('All files', '*.*')])
        if p: self.path.set(os.path.normpath(p))

    # ---------------------------------------------------------------- form + preview
    def _main(self):
        self.main = ttk.Frame(self, padding=(18, 4, 18, 4))
        left = ttk.Frame(self.main, style='Panel.TFrame', padding=(14, 8)); left.pack(side='left', fill='y')
        ttk.Checkbutton(left, text='Only items this profile has used before', variable=self.seen_only, command=self.refill).grid(row=0, column=0, columnspan=2, sticky='w')
        self.mbtn = ttk.Button(left, text='', style='Small.TButton', command=self.toggle_mission); self.mbtn.grid(row=0, column=2, sticky='e')
        row = 1; group = None
        for key, label, grp, cat in SLOTS:
            ws = []
            if grp != group:
                group = grp
                h = ttk.Label(left, text=grp, style='Head.TLabel'); h.grid(row=row, column=0, columnspan=3, sticky='w', pady=(5, 0)); row += 1
                if grp == 'STRATAGEMS': ws.append(h)
            lab = ttk.Label(left, text=label, style='Panel.TLabel'); lab.grid(row=row, column=0, sticky='w', padx=(0, 10))
            cb = AutoCombo(left, width=32, on_change=self.changed); cb.grid(row=row, column=1, sticky='ew', pady=0)
            ws += [lab, cb]
            if key in KINDS:
                b = ttk.Button(left, text='FILTER', style='Small.TButton', command=lambda k=key: self.filter_dialog(k)); b.grid(row=row, column=2, padx=(6, 0), sticky='e'); self.fbtn[key] = b
            self.combos[key] = cb; self.rows[key] = ws; row += 1
        right = ttk.Frame(self.main); right.pack(side='left', fill='both', expand=True, padx=(16, 0))
        ttk.Label(right, text='Type in a box to filter, Up / Down + Enter to pick, or click a tile. A number is taken as a raw item id.   (!) = never used on this profile, so ownership is unknown.',
                  style='MutedBG.TLabel', wraplength=470, justify='left').pack(side='bottom', anchor='w', pady=(6, 0))
        self.canvas = tk.Canvas(right, bg=BG, highlightthickness=0, width=480, height=480); self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.draw()); self.canvas.bind('<Button-1>', self.click)
        self.canvas.bind('<Motion>', lambda e: self.canvas.configure(cursor='hand2' if self.hit(e) else ''))
        self.show_mission()

    def _bottom(self):
        b = self.bottom = ttk.Frame(self, padding=(18, 6, 18, 8))
        ttk.Button(b, text='APPLY TO SAVE', style='Go.TButton', width=14, command=self.apply).pack(side='left')
        ttk.Button(b, text='EXPORT COPY', width=12, command=self.export).pack(side='left', padx=(8, 0))
        ttk.Button(b, text='RESET', width=7, command=self.reset).pack(side='left', padx=(8, 0))
        self.dbtn = ttk.Button(b, text='DUMP ▾', width=8, command=self.dump_menu); self.dbtn.pack(side='left', padx=(8, 0))
        ttk.Button(b, text='IMPORT .SAV', width=11, command=self.cat_import).pack(side='right')
        ttk.Button(b, text='LOAD', width=6, command=self.cat_load).pack(side='right', padx=(0, 8))
        ttk.Button(b, text='SAVE', width=6, command=self.cat_save).pack(side='right', padx=(0, 8))
        self.catname = tk.StringVar(); self.catbox = ttk.Combobox(b, textvariable=self.catname, width=13); self.catbox.pack(side='right', padx=(0, 8))
        ttk.Label(b, text='My loadouts:').pack(side='right', padx=(0, 6))

    def on_show(self): self.cat_refresh()

    # ---------------------------------------------------------------- mission-only fields
    def show_mission(self):
        on = self.mission.get()
        for k in MISSION:
            for w in self.rows[k]:
                if on: w.grid()
                else: w.grid_remove()
        self.mbtn.configure(text=('HIDE' if on else 'SHOW') + ' MISSION FIELDS', style='On.Small.TButton' if on else 'Small.TButton')
        self.draw()

    def toggle_mission(self): self.mission.set(not self.mission.get()); self.show_mission()

    # ---------------------------------------------------------------- options
    def options(self, key, keep=()):
        """-> list of (label, id, dim) for one slot. keep: ids that must stay in the list whatever the filters say."""
        it = self.items; cat = CAT[key]; seen = self.save.seen if self.save else set(); have_seen = bool(seen); rows = []
        def lab(text, vid): return text + (BANG if have_seen and vid not in seen else '')
        if key in KINDS:   # kits and weapons: the slot's own kind by default, others (tagged) when the filter lets them in
            f = self.filt[key]; kinds = {k for k, v in f['kinds'].items() if v.get()}; perk = f['perk'].get(); tag = {k: t for k, _, t in KINDS[key]}
            pool, kind_of = (it['kits'], 'kind') if key in KIT_SLOTS else (it['weapons'], 'type')
            for vid, x in sorted(pool.items(), key=lambda i: (i[1][kind_of] != OWN[key], i[1][kind_of], i[1]['name'].lower())):
                k = x[kind_of]; p = perk_name(x.get('passive'))
                if vid not in keep and (k not in kinds or (perk != ALL_PERKS and p != perk)): continue
                rows.append((('' if k == OWN[key] else '[%s] ' % tag.get(k, k.upper())) + x['name'] + ('  ·  ' + p if p else ''), vid))
        elif cat == 'strat':
            rows = [(n.strip(), vid) for vid, n in sorted(it['stratagems'].items(), key=lambda x: x[1].lower())]
        else:
            sub = cat[5:]; named = it['misc'].get(sub, {}); ids = it.get('types', {}).get(sub)
            if ids:   # only ids the game lists for this kind of item; names where we know them
                rows = [(named.get(vid) or 'id %d (name not known)' % vid, vid) for vid in ids]
                rows += [(n, vid) for vid, n in named.items() if vid not in ids]
                rows.sort(key=lambda x: (x[0].startswith('id '), x[0].lower()))
            else:
                rows = [(n, vid) for vid, n in sorted(named.items(), key=lambda x: x[1].lower())]
        for vid in keep:
            if vid not in {v for _, v in rows}:
                n = savecore.item_name(it, key, vid)[0]; rows.append((n if not n.startswith('unknown id') else 'id %d (name not known)' % vid, vid))
        out = []; used = {}
        for t, vid in rows:
            if self.seen_only.get() and have_seen and vid not in seen and vid not in keep: continue
            l = lab(t, vid)
            if l in used and used[l] != vid: l = '%s  #%d%s' % (t, vid, BANG if l.endswith(BANG) else '')
            used[l] = vid; out.append((l, vid, have_seen and vid not in seen))
        return out

    def label_of(self, key, vid):
        for l, v, _ in self.combos[key].options:
            if v == vid: return l
        return str(vid)

    def current(self, silent=False):
        out = {}
        for key in self.combos:
            try: out[key] = self.combos[key].get_value()
            except ValueError as e:
                if not silent: raise ValueError('%s: %s' % (LABEL[key], e))
        return out

    def put(self, key, vid):
        """show vid in a slot's box; the list always keeps it and the value on disk, whatever the filters say"""
        self.combos[key].set_options(self.options(key, keep={vid, self.save.original[key]})); self.combos[key].set_text(self.label_of(key, vid))

    def put_all(self, slots):
        for key in self.combos:
            if key in slots: self.put(key, int(slots[key]))
        self.changed()

    def filter_default(self, slot):
        f = self.filt[slot]; return all(v.get() == (k == OWN[slot]) for k, v in f['kinds'].items()) and f['perk'].get() == ALL_PERKS

    def refill(self):
        if not self.save: return
        for s, b in self.fbtn.items(): b.configure(style='Small.TButton' if self.filter_default(s) else 'On.Small.TButton')
        self.put_all({**self.save.original, **self.current(silent=True)})

    def filter_dialog(self, slot):
        if not self.save: return
        if self.fdialog and self.fdialog.winfo_exists(): self.fdialog.destroy()      # one filter window at a time
        d = self.fdialog = tk.Toplevel(self); d.title('Filter: ' + LABEL[slot]); d.configure(bg=PANEL, padx=16, pady=14); d.transient(self.winfo_toplevel()); d.resizable(False, False)
        ttk.Label(d, text='SHOW IN THE %s LIST' % LABEL[slot].upper(), style='Head.TLabel').grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 6))
        f = self.filt[slot]; kit = slot in KIT_SLOTS
        for i, (k, lab, _) in enumerate(KINDS[slot]):
            ttk.Checkbutton(d, text=lab, variable=f['kinds'][k], command=self.refill).grid(row=1 + i // 3, column=i % 3, sticky='w', padx=(0, 14), pady=1)
        if kit:
            ttk.Label(d, text='Perk', style='Panel.TLabel').grid(row=3, column=0, sticky='w', pady=(10, 0))
            perks = [ALL_PERKS] + sorted({perk_name(k['passive']) for k in self.items['kits'].values() if k['passive']})
            c = ttk.Combobox(d, textvariable=f['perk'], values=perks, state='readonly', width=34); c.grid(row=3, column=1, columnspan=2, sticky='w', pady=(10, 0))
            c.bind('<<ComboboxSelected>>', lambda e: self.refill())
        note = ('Putting an armor in the helmet or cape slot gives its perk there.' if kit else
                'For testing: any weapon can be written to any weapon slot. The game may ignore it, reset the slot or reject the save.')
        ttk.Label(d, text=note, style='Muted.TLabel', wraplength=420, justify='left').grid(row=4, column=0, columnspan=3, sticky='w', pady=(10, 0))
        def reset():
            for k, v in f['kinds'].items(): v.set(k == OWN[slot])
            f['perk'].set(ALL_PERKS); self.refill()
        ttk.Button(d, text='DEFAULT', style='Small.TButton', command=reset).grid(row=5, column=0, sticky='w', pady=(12, 0))
        ttk.Button(d, text='CLOSE', style='Small.TButton', command=d.destroy).grid(row=5, column=2, sticky='e', pady=(12, 0))
        b = self.fbtn[slot]; d.geometry('+%d+%d' % (b.winfo_rootx() + 30, b.winfo_rooty() + 24))

    # ---------------------------------------------------------------- load / state
    def load(self):
        p = self.path.get().strip().strip('"')
        if not p or not os.path.isfile(p): messagebox.showerror('Load', 'No save file at that path.'); return
        try: self.save = savecore.Save(p, self.items)
        except Exception as e: messagebox.showerror('Load', 'This file could not be read as a Helldivers 2 save:\n\n%s' % e); return
        if not (self.save.crc_ok and self.save.hash_ok):
            messagebox.showwarning('Load', 'This file fails its own checksum, so the game would reject it as it is. It can still be read and re-saved correctly.')
        if not self.save.known_version:
            messagebox.showwarning('Load', 'This save has format 0x%x, which is newer than the ones this tool was tested with. The slots were found, '
                                   'but treat writing as untested: keep the backup at hand, or use EXPORT COPY.' % self.save.version)
        if self.save.kind != self.kind.get(): self.kind.set(self.save.kind); self.path.set(p)
        self.app.settings['source'] = self.save.kind; self.photos = {}
        if not self.main.winfo_ismapped(): self.bottom.pack(side='bottom', fill='x'); self.main.pack(fill='both', expand=True)
        self.cat_refresh(); self.reset()
        note = '' if self.save.seen else '  This profile has no usage history, so nothing can be marked (!).'
        self.app.say('Loaded %s save (format 0x%x): %s%s' % (self.save.kind, self.save.version, p, note))

    def reset(self):
        if self.save: self.put_all(self.save.original)

    def changed(self):
        if not self.save: return
        cur = self.current(silent=True); n = 0
        for key in self.combos:
            ch = key in cur and cur[key] != self.save.original[key]; n += ch; self.combos[key].mark(ch)
        self.app.say('%d slot(s) changed.' % n if n else 'No changes yet.'); self.draw()

    def changes(self):
        cur = self.current(); return {k: v for k, v in cur.items() if v != self.save.original[k]}

    # ---------------------------------------------------------------- tiles
    def photo(self, name, maxw, maxh):
        """picture `name` from the pictures folder, shrunk by a whole factor so that it fits maxw x maxh; None if there is none.
        Each file is read once and the few sizes in use are kept, so resizing the window does not reload pictures."""
        if name not in self.photos:
            p = os.path.join(self.app.folder('images'), name + '.png')
            try: self.photos[name] = {1: tk.PhotoImage(file=p)} if os.path.exists(p) else None
            except tk.TclError: self.photos[name] = None
        sizes = self.photos[name]
        if not sizes: return None
        full = sizes[1]; f = max(1, -(-full.width() // max(int(maxw), 1)), -(-full.height() // max(int(maxh), 1)))
        if f not in sizes: sizes[f] = full.subsample(f)
        return sizes[f]

    def tile(self, x, y, w, h, key, big=False):
        c = self.canvas; orig = self.save.original[key]; vid = self._cur.get(key, orig)
        name, kind = savecore.item_name(self.items, key, vid); ch = vid != orig
        odd = key in KIT_SLOTS and kind and kind.lower() != key
        unseen = bool(self.save.seen) and vid not in self.save.seen and vid != 0
        c.create_rectangle(x, y, x + w, y + h, fill=TILE, outline=YELLOW if ch else (ORANGE if odd else GREEN), width=2)
        self.rects.append((x, y, x + w, y + h, key))
        lab = LABEL[key].upper(); fits = int((w - 18 - (62 if ch else 0)) / 6.6)   # keep the slot label inside narrow boxes
        if len(lab) > fits: lab = lab[:max(3, fits - 1)].rstrip() + '.'
        c.create_text(x + 9, y + 7, text=lab, anchor='nw', fill=YELLOW if ch else MUTED, font=(FONT, 8, 'bold'))
        if ch: c.create_text(x + w - 8, y + 7, text='CHANGED', anchor='ne', fill=YELLOW, font=(FONT, 8, 'bold'))
        kit = self.items['kits'].get(vid); perk = perk_name(kit['passive']) if kit and kit['passive'] else ''
        notes = []
        if perk: notes.append((perk.upper(), TEXT if not odd else ORANGE))
        if odd: notes.append(('%s IN %s SLOT' % (kind.upper(), key.upper()), ORANGE))
        if unseen: notes.append(('(!) NOT USED BEFORE ON THIS PROFILE', RED))
        nb = 13 * len(notes)
        room = (w - 16, h - 58 - nb); img = None
        if h > 96 and vid:   # picture by id, else by name (images/titles/viper_commando.png)
            img = self.photo(str(vid), *room) or self.photo(os.path.join(key + 's', slug(name)), *room)
        if img: c.create_image(x + w / 2, y + 22 + room[1] / 2, image=img); ty = y + h - nb - 22
        elif h < 48: ty = y + h / 2 + 5      # one-line box
        else: ty = y + (h - nb) / 2 + 6
        c.create_text(x + w / 2, ty, text=name, width=w - 18, justify='center', fill=TEXT, font=(FONT, 13 if big and not img else (10 if w >= 150 else 9), 'bold'))
        if perk:   # the perk's icon, top right corner, sized to the box
            side = 64 if h > 300 else (43 if h > 150 else 26); icon = self.photo(os.path.join('perks', slug(perk)), side, side)
            if icon: c.create_image(x + w - 8, y + (24 if ch else 8), image=icon, anchor='ne')
        yy = y + h - 9 - 13 * (len(notes) - 1)
        for t, col in notes:
            c.create_text(x + w / 2, yy, text=t, fill=col, font=(FONT, 8, 'bold' if col != TEXT else 'normal')); yy += 13

    def draw(self):
        c = self.canvas; c.delete('all'); self.rects = []
        if not self.save: return
        if len(self.photos) > 60: self.photos.clear()      # after a long browsing session: drop the pictures no longer shown
        self._cur = self.current(silent=True); on = self.mission.get()
        W, H = max(c.winfo_width(), 320), max(c.winfo_height(), 360); g = 8; D = 34
        # row 1: cape | armor | helmet over title (same size) | player card (full height)
        T = (H - D - g) * (0.52 if on else 0.66)
        lw = W * 0.23; cw = W * 0.33; R = W - lw - cw - 2 * g; x = lw + cw + 2 * g
        self.tile(0, 0, lw, T, 'cape'); self.tile(lw + g, 0, cw, T, 'armor', big=True)
        hw = R * 0.60; hh = (T - g) / 2
        self.tile(x, 0, hw, hh, 'helmet'); self.tile(x, hh + g, hw, hh, 'title')
        self.tile(x + hw + g, 0, R - hw - g, T, 'card')
        # row 2: primary as wide as cape + armor, then secondary, throwable, victory pose
        y = T + g; rest = H - D - g - y; nrows = 2 if on else 1; hb = (rest - g * (nrows - 1)) / nrows
        self.tile(0, y, lw + cw + g, hb, 'primary'); bw = (R - 2 * g) / 3
        for i, k in enumerate(('secondary', 'grenade', 'pose')): self.tile(x + i * (bw + g), y, bw, hb, k)
        if on:   # mission fields: four stratagems and the booster in their own row
            y += hb + g; w5 = (W - 4 * g) / 5
            for i, k in enumerate(('strat1', 'strat2', 'strat3', 'strat4', 'booster')): self.tile(i * (w5 + g), y, w5, hb, k)
        # one-line boxes
        w2 = (W - g) / 2; self.tile(0, H - D, w2, D, 'voice'); self.tile(w2 + g, H - D, w2, D, 'body')

    def hit(self, e):
        for x0, y0, x1, y1, k in self.rects:
            if x0 <= e.x <= x1 and y0 <= e.y <= y1: return k
        return None

    def click(self, e):
        k = self.hit(e)
        if k: self.combos[k].entry.focus_set(); self.combos[k].entry.select_range(0, 'end'); self.after(60, lambda: self.combos[k].open(everything=True))

    # ---------------------------------------------------------------- write
    def describe(self, ch):
        return '\n'.join('  %s:  %s  ->  %s' % (LABEL[k], savecore.item_name(self.items, k, self.save.original[k])[0], savecore.item_name(self.items, k, v)[0]) for k, v in ch.items())

    def get_changes(self):
        if not self.save: return None
        try: ch = self.changes()
        except ValueError as e: messagebox.showerror('Loadout', str(e)); return None
        if not ch: messagebox.showinfo('Loadout', 'Nothing has been changed.'); return None
        if self.app.settings.get('warn_not_used_before', True) and self.save.seen:
            new = [k for k, v in ch.items() if v not in self.save.seen and v != 0]
            if new and not messagebox.askokcancel('Ownership unknown', NOT_USED % '\n'.join('  %s:  %s' % (LABEL[k], savecore.item_name(self.items, k, ch[k])[0]) for k in new), icon='warning'): return None
        return ch

    def export(self):
        ch = self.get_changes()
        if not ch: return
        p = filedialog.asksaveasfilename(title='Export edited save as', defaultextension='.sav', initialfile='edited_' + os.path.basename(self.save.path), filetypes=[('Helldivers 2 save', '*.sav')])
        if not p: return
        if os.path.abspath(p) == os.path.abspath(self.save.path): messagebox.showerror('Export', 'That is the loaded save itself. Use APPLY TO SAVE for that (it makes a backup).'); return
        try:
            with open(p, 'wb') as f: f.write(self.save.build(ch))
        except Exception as e: messagebox.showerror('Export', str(e)); return
        self.app.say('Exported %d change(s) to %s (%s format). The loaded save was not touched.' % (len(ch), p, self.save.kind))

    def apply(self):
        ch = self.get_changes()
        if not ch: return
        running = savecore.process_running('helldivers2.exe')
        if running: messagebox.showerror('Apply', 'Helldivers 2 is running. Close the game first.'); return
        if running is None and not messagebox.askokcancel('Apply', 'Could not check whether Helldivers 2 is running. Is the game closed?'): return
        if self.save.kind == 'cloud':
            if savecore.process_running('steam.exe'): messagebox.showerror('Apply', 'Steam is running.\n\n' + CLOUD_STEPS); return
            if not messagebox.askokcancel('Apply to cloud save', CLOUD_STEPS + '\n\nSteam Cloud disabled and Steam closed?'): return
        if not messagebox.askokcancel('Apply', 'Write these changes to\n%s ?\n\n%s\n\nThe current file is copied to the backups folder first.' % (self.save.path, self.describe(ch))): return
        try: bak = savecore.backup_and_write(self.save, self.save.build(ch), self.app.folder('backups'), ch)
        except Exception as e: messagebox.showerror('Apply', str(e)); return
        self.load(); self.app.say('Applied %d change(s). Backup: %s' % (len(ch), bak))

    # ---------------------------------------------------------------- dump
    def dump_menu(self):
        if not self.save: return
        m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=YELLOW, activeforeground='#111', font=(FONT, 10))
        for label, kind in (('Raw body (.bin)', 'bin'), ('Annotated text (.txt)', 'txt'), ('Loadout as JSON (.json)', 'json'), ('Loadout as CSV (.csv)', 'csv')):
            m.add_command(label=label, command=lambda k=kind: self.dump(k))
        m.tk_popup(self.dbtn.winfo_rootx(), self.dbtn.winfo_rooty() - 4 * 26)

    def dump(self, kind):
        d = self.app.folder('dumps'); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, '%s_%s_%s.%s' % (time.strftime('%Y%m%d-%H%M%S'), self.save.kind, os.path.splitext(os.path.basename(self.save.path))[0], kind))
        data = bytes(self.save.body) if kind == 'bin' else dict(txt=savecore.dump_text, json=savecore.dump_json, csv=savecore.dump_csv)[kind](self.save).encode('utf-8')
        with open(p, 'wb') as f: f.write(data)
        self.app.say('Dumped the loaded save (as it is on disk, without unsaved changes) to ' + p)
        return p

    # ---------------------------------------------------------------- catalogue
    def cat_dir(self): d = self.app.folder('loadouts'); os.makedirs(d, exist_ok=True); return d

    def cat_refresh(self):
        self.catbox['values'] = sorted(os.path.splitext(f)[0] for f in os.listdir(self.cat_dir()) if f.endswith('.json'))

    def cat_save(self):
        if not self.save: return
        name = ''.join(ch for ch in self.catname.get().strip() if ch.isalnum() or ch in ' -_()')[:60].strip()
        if not name: messagebox.showinfo('My loadouts', 'Type a name for this loadout in the box first.'); return
        try: cur = self.current()
        except ValueError as e: messagebox.showerror('My loadouts', str(e)); return
        p = os.path.join(self.cat_dir(), name + '.json')
        if os.path.exists(p) and not messagebox.askokcancel('My loadouts', 'Replace the saved loadout "%s"?' % name): return
        savecore.write_json(p, dict(name=name, saved=time.strftime('%Y-%m-%d %H:%M'), slots=cur, names={k: savecore.item_name(self.items, k, v)[0] for k, v in cur.items()}))
        self.cat_refresh(); self.app.say('Saved loadout "%s" to %s' % (name, p))

    def cat_load(self):
        if not self.save: return
        name = self.catname.get().strip(); p = os.path.join(self.cat_dir(), name + '.json')
        if not name or os.path.basename(name) != name or not os.path.exists(p):
            messagebox.showinfo('My loadouts', 'Pick one of your saved loadouts in the box first.'); return
        try: slots = savecore.read_json(p)['slots']
        except Exception as e: messagebox.showerror('My loadouts', 'Could not read that loadout: %s' % e); return
        self.put_all(slots); self.app.say('Loadout "%s" put into the form. Nothing is written until you Apply or Export.' % name)

    def cat_import(self):
        ps = filedialog.askopenfilenames(title='Import loadouts from save files', filetypes=[('Helldivers 2 save', '*.sav *.old *.bak'), ('All files', '*.*')])
        ok = 0; bad = []
        for p in ps:
            try:
                lo = savecore.loadout_from_save(p, self.items); name = lo['name']; q = os.path.join(self.cat_dir(), name + '.json'); n = 2
                while os.path.exists(q): q = os.path.join(self.cat_dir(), '%s (%d).json' % (name, n)); n += 1
                savecore.write_json(q, lo); ok += 1
            except Exception as e: bad.append('%s: %s' % (os.path.basename(p), e))
        self.cat_refresh()
        if bad: messagebox.showwarning('Import', 'Could not read:\n\n' + '\n'.join(bad[:12]))
        if ps: self.app.say('Imported %d loadout(s) into %s. The save files themselves were only read.' % (ok, self.cat_dir()))


MODULE = dict(name='LOADOUT', order=10, factory=lambda parent, app: LoadoutPage(parent, app))
