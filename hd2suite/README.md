# hd2suite 0.3.2 - Helldivers 2 mod tools (window)

Start: `python app.py` (Python 3.9+ with tkinter, nothing else), or the launcher one folder up.
It only reads and writes `testament_new.sav`. It never touches the game's own files, never talks to the running game,
and has no network code.

## Files
| File | Role |
|---|---|
| `app.py` | window shell: left bar, status line, settings.json, loads every `modules/*.py` |
| `theme.py` | colours, ttk styles, `AutoCombo` (text box with a live suggestion list) |
| `modules/loadout.py` | LOADOUT: the save editor |
| `modules/settings.py` | SETTINGS: folders and switches |
| `savecore.py` | no-window logic: find / read / write saves, item lists, backups, dumps |
| `testament.py` | the save container: LZ4 chunks, crc32, body hash (also a command line tool) |
| `data/items.json` | names by id: kits, weapons, stratagems, `misc` (one list per character slot), `other` (kind unknown) |
| `data/item_types.json` | which ids the game has for each character slot (from the game's public item list) |
| `data/icon_names.json`, `data/cards_poses_from_game_dll.json` | reference only (how the pictures were matched); not read by the program |
| `images/` | pictures for the tiles (see below) |
| `icon.png` | the window's icon |
| `tests/check.py` | self-check without a window: LZ4, crc32, body hash, container, item lists, and any saves you give it (read only) |

A new tool = one file in `modules/` with `MODULE = dict(name='NAME', order=50, factory=lambda parent, app: Widget(parent, app))`.
The shell gives it `app.say(text)`, `app.settings`, `app.folder(key)`, `app.save_settings()` and the shared theme.

## LOADOUT
- Local / Cloud, path found automatically or typed / browsed, then LOAD.
- Each slot: type to filter, Up / Down / PageUp / PageDown, Enter to pick, Esc to close. A number is used as a raw id.
  Clicking a tile opens that slot's list.
- Character slots (booster, body type, voice, victory pose, player card, title) list only ids of their own kind.
  Victory pose also lists emotes. Ids without a known name show as `id N (name not known)`; a name ending in ` ?` was
  placed by its position in the game's list and is not confirmed.
- FILTER on helmet / armor / cape: which kinds to list and one perk. An armor in the helmet or cape slot gives its perk there.
- FILTER on primary / secondary / throwable: any weapon kind, including support weapons and backpacks. For testing: the
  game may ignore such a value, reset the slot or reject the save.
- "(!)" marks an item that never appears in this save's own item lists and is not equipped. That is NOT an ownership
  check (ownership is server side), and items you own but never used are marked too. A warning is shown before writing
  such an item (switch in SETTINGS). A blank profile has no history, so nothing is marked.
- SHOW / HIDE MISSION FIELDS: stratagems and booster (only used when rejoining a mission).
- APPLY TO SAVE (backup + receipt first; refuses while the game runs, and for cloud while Steam runs), EXPORT COPY, RESET.
- DUMP: raw body .bin, annotated .txt, loadout .json or .csv, written to the dumps folder.
- My loadouts: SAVE / LOAD by name; IMPORT .SAV turns any number of save files into presets (the files are only read).

## Pictures
A tile shows `images/<item id>.png`; if there is none, `images/<slot>s/<item name>.png` (for example
`images/titles/free_of_thought.png`). Perk icons: `images/perks/<perk name>.png`.
All of them were made from the game's own files:
armors and helmets rendered in 3D, capes composited flat from their mask and colour table (or the matching player card),
weapon / stratagem / perk / booster / title icons, player cards and emote thumbnails extracted.
Missing: victory pose pictures, emblems on the flat capes, one helmet, two capes.

## Files it writes
`settings.json`, `backups/` (every replaced save + `receipts.jsonl`), `loadouts/`, `dumps/`, `error.log` - all next to
`app.py` unless SETTINGS points the folders elsewhere - and the save you apply to. A save is replaced through a
temporary file and read back; an earlier backup is never overwritten.

Errors: anything unexpected goes to `error.log` and a message box. Exit code 3 = the window could not start and said so.

## State of testing (0.3.2)
- `tests/check.py`: LZ4 against the reference library (`lz4` package, when installed), MurmurHash64A against the
  public C implementation's values, container round trips, item lists. Python 3.10, 3.12 and 3.14.
- Window: every list, filter, build and dump over 13 real saves (formats 0xfe, 0x100, 0x107); APPLY with backup,
  receipt and read-back. Linux with Tk 8.6 (Python 3.12, 3.14), and the official Windows Python 3.14.10 with
  Tk 9.0 under Wine.
- Windows, 2026-11-12, on the author's PC: the launcher .exe starts the program; a save written by 0.3.2 was loaded
  by the game (0.3.2 always packs with its own LZ4 code, never the `lz4` package, so every copy writes the same
  bytes); "Get Python runtime" downloaded, checked (39 of 39 program files validly signed) and tried the official
  Python. One profile, one PC: keep your backups.

## Known limits
- Emote wheel: not stored in testament_new.sav or the local config files, so it cannot be edited here.
- Names: 16 titles, 71 player cards, 26 poses / emotes, 10 boosters and 3 voice packs have an id but no name yet.
- A save format newer than 0x107 is opened if the slots can be found, with a warning that writing it is untested.
