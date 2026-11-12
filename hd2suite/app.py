#!/usr/bin/env python3
"""
hd2suite / app.py - the window shell. Tools are modules: every file in modules/ that defines

    MODULE = dict(name='LOADOUT', order=10, factory=lambda parent, app: <tk widget>)

gets a button in the left bar. The shell provides the theme (theme.py), a status line (app.say) and
settings stored in settings.json next to this file (app.settings / app.folder(name) / app.save_settings()).

test option:  app.py --open <save file>
"""
import os, sys, json, time, importlib, traceback
import tkinter as tk
from tkinter import ttk, messagebox

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import theme
from theme import PANEL, YELLOW, MUTED, TEXT, FONT

VERSION = '0.3.2'
DEFAULTS = dict(backups='backups', loadouts='loadouts', images='images', dumps='dumps',
                show_mission_fields=False, warn_not_used_before=True, source='local')


def log_error(text):
    """append to error.log next to this file (the program may run without a console) -> where it went"""
    path = os.path.join(HERE, 'error.log')
    try:
        with open(path, 'a', encoding='utf-8') as f: f.write('--- %s  hd2suite %s  Python %s\n%s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), VERSION, sys.version.split()[0], text))
    except OSError: path = '(error.log could not be written in %s)' % HERE
    if sys.stderr: print(text, file=sys.stderr)
    return path


class App(tk.Tk):
    def __init__(self, argv=()):
        super().__init__()
        self.title('Helldivers 2 - mod tools %s' % VERSION); self.minsize(1180, 740); self.geometry('1300x800')
        self.argv = list(argv); self.settings = dict(DEFAULTS); self.settings_path = os.path.join(HERE, 'settings.json')
        try:
            with open(self.settings_path, encoding='utf-8') as f: self.settings.update(json.load(f))
        except (OSError, ValueError): pass      # no settings file yet, or a broken one: defaults
        theme.apply_style(self)
        try: self.icon = tk.PhotoImage(file=os.path.join(HERE, 'icon.png')); self.iconphoto(True, self.icon)
        except tk.TclError: pass                # no icon file: Tk's own icon
        self.status = tk.StringVar(value='')
        bar = tk.Frame(self, bg=PANEL); bar.pack(side='bottom', fill='x')
        tk.Label(bar, textvariable=self.status, bg=PANEL, fg=MUTED, anchor='w', font=(FONT, 9), padx=18, pady=6).pack(fill='x')
        side = ttk.Frame(self, style='Side.TFrame', width=150); side.pack(side='left', fill='y'); side.pack_propagate(False)
        tk.Label(side, text='HD2\nMOD TOOLS', bg=PANEL, fg=TEXT, font=(FONT, 12, 'bold'), justify='left', anchor='w', padx=16, pady=14).pack(fill='x')
        tk.Frame(side, bg=YELLOW, height=2).pack(fill='x', padx=16, pady=(0, 8))
        self.content = ttk.Frame(self); self.content.pack(side='left', fill='both', expand=True)
        self.pages = {}; self.buttons = {}
        for m in self._modules():
            b = ttk.Button(side, text=m['name'], style='Nav.TButton', command=lambda n=m['name']: self.show(n)); b.pack(fill='x')
            self.buttons[m['name']] = b; self.pages[m['name']] = (m, None)
        tk.Label(side, text='v' + VERSION, bg=PANEL, fg=MUTED, font=(FONT, 8), anchor='w', padx=16).pack(side='bottom', fill='x', pady=8)
        if self.pages: self.show(next(iter(self.pages)))

    def _modules(self):
        mods = []; d = os.path.join(HERE, 'modules')
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.py') and not fn.startswith('_'):
                try: mods.append(importlib.import_module('modules.' + fn[:-3]).MODULE)
                except Exception: self.say('%s could not be loaded; details in %s' % (fn, log_error('module %s:\n%s' % (fn, traceback.format_exc()))))
        return sorted(mods, key=lambda m: m.get('order', 100))

    def report_callback_exception(self, exc, val, tb):
        """an error inside a button or key handler: write it down and say so, instead of failing silently"""
        path = log_error(''.join(traceback.format_exception(exc, val, tb)))
        messagebox.showerror('Something went wrong', '%s: %s\n\nThe details were written to\n%s' % (exc.__name__, val, path))

    def show(self, name):
        m, w = self.pages[name]
        if w is None: w = m['factory'](self.content, self); self.pages[name] = (m, w)
        for n, (_, pw) in self.pages.items():
            if pw is not None: pw.pack_forget()
            self.buttons[n].configure(style='NavOn.TButton' if n == name else 'Nav.TButton')
        w.pack(fill='both', expand=True)
        if hasattr(w, 'on_show'): w.on_show()

    # -- services for modules
    def say(self, text): self.status.set(text)

    def folder(self, key):
        p = self.settings.get(key) or DEFAULTS[key]
        return p if os.path.isabs(p) else os.path.join(HERE, p)

    def save_settings(self):
        with open(self.settings_path, 'w', encoding='utf-8') as f: json.dump(self.settings, f, indent=1)


def main():
    try: App(sys.argv[1:]).mainloop()
    except Exception:
        path = log_error(traceback.format_exc())
        if os.name == 'nt':     # started without a console: a plain Windows message box is all there is
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'HD2 Mod Tools could not start.\n\nThe details were written to\n' + path, 'HD2 Mod Tools', 0x10)
        sys.exit(3)             # 3 = failed and already said so (the launcher stays quiet on this code)


if __name__ == '__main__':
    main()
