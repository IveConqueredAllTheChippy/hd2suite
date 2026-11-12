#!/usr/bin/env python3
"""
hd2suite module: SETTINGS - folders and switches in one place. Stored in settings.json next to app.py.
A folder may be absolute or relative to the tool's own folder.
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog

from theme import YELLOW

FOLDERS = [('backups', 'Backups', 'Every save is copied here before it is replaced (plus receipts.jsonl).'),
           ('loadouts', 'My loadouts', 'Your saved loadouts, one small .json file each.'),
           ('images', 'Pictures', 'Shown on the tiles: <item id>.png, or <slot>s\\<item name>.png (titles\\cadet.png); perks\\<perk name>.png.'),
           ('dumps', 'Dumps', 'Where DUMP writes .bin / .txt / .json / .csv files.')]
SWITCHES = [('show_mission_fields', 'Show mission fields (stratagems, booster) when the editor starts'),
            ('warn_not_used_before', 'Warn before writing an item that was never used on the profile')]


class SettingsPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=(18, 14))
        self.app = app; self.vars = {}
        ttk.Label(self, text='SETTINGS', style='Title.TLabel').pack(anchor='w')
        tk.Frame(self, bg=YELLOW, height=2).pack(fill='x', pady=(4, 12))
        box = ttk.Frame(self, style='Panel.TFrame', padding=16); box.pack(fill='x')
        ttk.Label(box, text='FOLDERS', style='Head.TLabel').grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 6))
        r = 1
        for key, label, hint in FOLDERS:
            v = tk.StringVar(value=app.settings.get(key, key)); self.vars[key] = v
            ttk.Label(box, text=label, style='Panel.TLabel').grid(row=r, column=0, sticky='w', padx=(0, 12))
            ttk.Entry(box, textvariable=v, width=70).grid(row=r, column=1, sticky='ew')
            ttk.Button(box, text='BROWSE', style='Small.TButton', command=lambda k=key: self.browse(k)).grid(row=r, column=2, padx=(6, 0))
            ttk.Button(box, text='OPEN', style='Small.TButton', command=lambda k=key: self.open(k)).grid(row=r, column=3, padx=(6, 0))
            ttk.Label(box, text=hint, style='Muted.TLabel').grid(row=r + 1, column=1, columnspan=3, sticky='w', pady=(0, 8)); r += 2
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text='SWITCHES', style='Head.TLabel').grid(row=r, column=0, columnspan=4, sticky='w', pady=(8, 6)); r += 1
        for key, label in SWITCHES:
            v = tk.BooleanVar(value=bool(app.settings.get(key))); self.vars[key] = v
            ttk.Checkbutton(box, text=label, variable=v).grid(row=r, column=0, columnspan=4, sticky='w', pady=1); r += 1
        ttk.Button(self, text='SAVE SETTINGS', style='Go.TButton', command=self.save).pack(anchor='w', pady=(12, 0))

    def browse(self, key):
        p = filedialog.askdirectory(title='Choose a folder', initialdir=self.app.folder(key) if os.path.isdir(self.app.folder(key)) else None)
        if p: self.vars[key].set(os.path.normpath(p))

    def open(self, key):
        self.save(quiet=True); d = self.app.folder(key); os.makedirs(d, exist_ok=True)
        if os.name == 'nt': os.startfile(d)
        self.app.say('Folder: ' + d)

    def save(self, quiet=False):
        for key, v in self.vars.items(): self.app.settings[key] = v.get().strip() if isinstance(v, tk.StringVar) else bool(v.get())
        self.app.save_settings()
        if not quiet: self.app.say('Settings saved to ' + self.app.settings_path)


MODULE = dict(name='SETTINGS', order=90, factory=lambda parent, app: SettingsPage(parent, app))
