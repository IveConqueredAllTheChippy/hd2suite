#!/usr/bin/env python3
"""
hd2suite / theme.py - shared look and widgets for every tool in the suite, so new modules look the same.

  apply_style(root)      dark ttk theme with the yellow accent
  AutoCombo(parent, ..)  text box with a live suggestion list under it (type to filter, Up/Down, Enter, Esc)
  Colours: BG PANEL TILE LINE YELLOW GREEN ORANGE RED TEXT MUTED, font family FONT
"""
import os
import tkinter as tk
from tkinter import ttk

BG, PANEL, TILE, LINE, FIELD = '#0a0b0d', '#131518', '#16191d', '#2b3036', '#1b1e22'
YELLOW, GREEN, ORANGE, RED, TEXT, MUTED = '#ffe900', '#2bd96b', '#ff9a2e', '#ff5a4d', '#e8e8e8', '#8b919a'
FONT = 'Segoe UI' if os.name == 'nt' else 'DejaVu Sans'


def apply_style(root):
    s = ttk.Style(root); s.theme_use('clam'); root.configure(bg=BG)
    s.configure('.', background=BG, foreground=TEXT, font=(FONT, 10))
    s.configure('TFrame', background=BG); s.configure('Panel.TFrame', background=PANEL); s.configure('Side.TFrame', background=PANEL)
    s.configure('TLabel', background=BG, foreground=TEXT); s.configure('Panel.TLabel', background=PANEL)
    s.configure('Muted.TLabel', background=PANEL, foreground=MUTED, font=(FONT, 9))
    s.configure('MutedBG.TLabel', background=BG, foreground=MUTED, font=(FONT, 9))
    s.configure('Head.TLabel', background=PANEL, foreground=YELLOW, font=(FONT, 10, 'bold'))
    s.configure('Title.TLabel', background=BG, foreground=TEXT, font=(FONT, 17, 'bold'))
    s.configure('TButton', background=LINE, foreground=TEXT, borderwidth=0, padding=(12, 7), font=(FONT, 10, 'bold'))
    s.map('TButton', background=[('active', '#3a4048'), ('disabled', '#1b1e22')], foreground=[('disabled', '#555b63')])
    s.configure('Go.TButton', background=YELLOW, foreground='#111111')
    s.map('Go.TButton', background=[('active', '#fff25a')])
    s.configure('Small.TButton', padding=(7, 3), font=(FONT, 8, 'bold'))
    s.configure('On.Small.TButton', padding=(7, 3), font=(FONT, 8, 'bold'), background='#4a4500', foreground=YELLOW)
    s.configure('Nav.TButton', background=PANEL, foreground=MUTED, anchor='w', padding=(16, 10), font=(FONT, 10, 'bold'))
    s.map('Nav.TButton', background=[('active', '#1c1f23')])
    s.configure('NavOn.TButton', background='#1c1f23', foreground=YELLOW, anchor='w', padding=(16, 10), font=(FONT, 10, 'bold'))
    s.configure('TRadiobutton', background=BG, foreground=TEXT, font=(FONT, 10, 'bold'))
    s.map('TRadiobutton', background=[('active', BG)], indicatorcolor=[('selected', YELLOW), ('!selected', LINE)])
    for n, bgc in (('TCheckbutton', PANEL), ('BG.TCheckbutton', BG)):
        s.configure(n, background=bgc, foreground=TEXT)
        s.map(n, background=[('active', bgc)], indicatorcolor=[('selected', YELLOW), ('!selected', LINE)])
    for n in ('TCombobox', 'TEntry'):
        s.configure(n, fieldbackground=FIELD, background=LINE, foreground=TEXT, bordercolor=LINE, lightcolor=LINE,
                    darkcolor=LINE, arrowcolor=YELLOW, insertcolor=TEXT, padding=2)
    s.map('TCombobox', fieldbackground=[('readonly', FIELD)], foreground=[('readonly', TEXT)])
    root.option_add('*TCombobox*Listbox.background', FIELD); root.option_add('*TCombobox*Listbox.foreground', TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground', YELLOW); root.option_add('*TCombobox*Listbox.selectForeground', '#111')
    return s


class AutoCombo(tk.Frame):
    """Entry + live suggestion list. options: list of (label, value, dim) ; dim=True draws the row muted.
    get_value() -> value for the typed text (exact label, a raw number, or a unique partial match) or raises ValueError."""
    ROWS = 12

    def __init__(self, parent, width=44, on_change=None, bg=PANEL):
        super().__init__(parent, bg=bg)
        self.var = tk.StringVar(); self.on_change = on_change; self.options = []; self.shown = []; self.pop = None
        self.border = tk.Frame(self, bg=LINE); self.border.pack(fill='x', expand=True)
        inner = tk.Frame(self.border, bg=FIELD); inner.pack(fill='x', padx=1, pady=1)
        self.entry = tk.Entry(inner, textvariable=self.var, width=width, bg=FIELD, fg=TEXT, insertbackground=TEXT, relief='flat',
                              font=(FONT, 10), highlightthickness=0)
        self.entry.pack(side='left', fill='x', expand=True, ipady=1, padx=(5, 0))
        self.arrow = tk.Label(inner, text='▾', bg=FIELD, fg=YELLOW, font=(FONT, 10), padx=6, cursor='hand2'); self.arrow.pack(side='right')
        self.arrow.bind('<Button-1>', lambda e: self.toggle())
        e = self.entry
        e.bind('<KeyRelease>', self._key); e.bind('<Down>', lambda ev: self._move(1)); e.bind('<Up>', lambda ev: self._move(-1))
        e.bind('<Return>', lambda ev: self._accept()); e.bind('<Escape>', lambda ev: self.close())
        e.bind('<FocusOut>', lambda ev: self.after(150, self._blur)); e.bind('<Next>', lambda ev: self._move(self.ROWS)); e.bind('<Prior>', lambda ev: self._move(-self.ROWS))

    # -- data
    def set_options(self, options):
        self.options = list(options)
        if self.pop: self._fill(self._filtered())

    def set_text(self, label): self.var.set(label)

    def mark(self, changed): self.border.configure(bg=YELLOW if changed else LINE)

    def get_value(self):
        t = self.var.get().strip()
        for l, v, _ in self.options:
            if l == t: return v
        if t.isdigit() and int(t) < 2 ** 32: return int(t)
        hits = {v for l, v, _ in self.options if t and t.lower() in l.lower()}
        if len(hits) == 1: return hits.pop()
        raise ValueError('"%s" is not an item in the list or a numeric id' % t)

    # -- popup
    def _filtered(self, everything=False):
        t = self.var.get().strip().lower()
        if everything or not t or any(l.lower() == t for l, _, _ in self.options): return self.options
        return [o for o in self.options if t in o[0].lower()]

    def open(self, everything=False):
        if not self.pop:
            self.pop = tk.Toplevel(self); self.pop.overrideredirect(True); self.pop.configure(bg=YELLOW)
            fr = tk.Frame(self.pop, bg=FIELD); fr.pack(fill='both', expand=True, padx=1, pady=1)
            sb = tk.Scrollbar(fr, orient='vertical', troughcolor=FIELD, bg=LINE, width=12, relief='flat')
            self.lb = tk.Listbox(fr, bg=FIELD, fg=TEXT, selectbackground=YELLOW, selectforeground='#111', activestyle='none', relief='flat',
                                 highlightthickness=0, font=(FONT, 10), exportselection=False, yscrollcommand=sb.set)
            sb.config(command=self.lb.yview); self.sb = sb; self.lb.pack(side='left', fill='both', expand=True)
            self.lb.bind('<ButtonRelease-1>', lambda e: self._accept()); self.lb.bind('<Motion>', lambda e: self._hover(e))
        self._fill(self._filtered(everything))

    def _fill(self, rows):
        self.shown = rows; lb = self.lb; lb.delete(0, 'end')
        for i, (l, v, dim) in enumerate(rows):
            lb.insert('end', ' ' + l)
            if dim: lb.itemconfig(i, fg=MUTED)
        if not rows: lb.insert('end', ' (no match - a number is taken as a raw item id)'); lb.itemconfig(0, fg=MUTED)
        h = min(self.ROWS, max(1, len(rows))); lb.configure(height=h)
        if len(rows) > self.ROWS: self.sb.pack(side='right', fill='y')
        else: self.sb.pack_forget()
        self.update_idletasks()
        x = self.border.winfo_rootx(); y = self.border.winfo_rooty() + self.border.winfo_height()
        w = max(self.border.winfo_width(), 360); ph = lb.winfo_reqheight() + 2      # the list's own height: row height depends on font and display scaling
        if y + ph > self.winfo_screenheight() - 40: y = self.border.winfo_rooty() - ph
        self.pop.geometry('%dx%d+%d+%d' % (w, ph, x, y)); self.pop.deiconify(); self.pop.lift()
        cur = self.var.get().strip()
        for i, (l, v, d) in enumerate(rows):
            if l == cur: lb.selection_set(i); lb.see(i); break

    def close(self):
        if self.pop: self.pop.destroy(); self.pop = None

    def toggle(self):
        if self.pop: self.close()
        else: self.entry.focus_set(); self.open(everything=True)

    def _hover(self, e):
        i = self.lb.nearest(e.y)
        if 0 <= i < len(self.shown): self.lb.selection_clear(0, 'end'); self.lb.selection_set(i)

    def _key(self, e):
        if e.keysym in ('Up', 'Down', 'Return', 'Escape', 'Tab', 'Next', 'Prior', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R'): return
        self.open()

    def _move(self, d):
        if not self.pop: self.open(everything=True); return 'break'
        if not self.shown: return 'break'
        sel = self.lb.curselection(); i = (sel[0] + d) if sel else (0 if d > 0 else len(self.shown) - 1)
        i = max(0, min(len(self.shown) - 1, i)); self.lb.selection_clear(0, 'end'); self.lb.selection_set(i); self.lb.see(i)
        return 'break'

    def _accept(self):
        if self.pop and self.shown:
            sel = self.lb.curselection()
            if sel: self.var.set(self.shown[sel[0]][0])
            elif len(self.shown) == 1: self.var.set(self.shown[0][0])
        self.close(); self.entry.icursor('end')
        if self.on_change: self.on_change()
        return 'break'

    def _blur(self):
        try: f = self.focus_get()
        except KeyError: f = None
        if self.pop and f is not None and str(f).startswith(str(self.pop)): return
        self.close()
        if self.on_change: self.on_change()
