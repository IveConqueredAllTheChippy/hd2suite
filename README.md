HD2 Mod Tools 0.3.2  (hd2suite)
===============================
A loadout editor for the Helldivers 2 profile save, testament_new.sav: armor, helmet, cape, weapons, stratagems,
booster, body type, voice, victory pose, player card and title, picked from lists with pictures.
Unofficial and fan-made; see CREDITS.txt. Use it at your own risk and read RISKS below first.


START
  Double-click  "HD2 Mod Tools.exe".

  The program is written in Python. If this folder has a subfolder "python", that one is used and nothing else is
  needed. If it has not, either:
    a) Python 3 (3.9 or newer, with tkinter; the normal install from python.org has that) is installed on this PC, or
    b) double-click "Get Python runtime.bat" once. It downloads the official Python from python.org (32 MB) into
       the folder "python" here, checks it, and installs nothing. Delete that folder to undo it.

  "Windows protected your PC" on the first start: the .exe is not code-signed. Either choose More info -> Run anyway,
  or start "HD2 Mod Tools (console).bat" instead, which does the same thing without the .exe.

  Keep the folder somewhere you can write to (Desktop, Documents, a games drive), not in Program Files:
  backups and settings are stored inside it.


WHAT IS IN THIS FOLDER
  HD2 Mod Tools.exe             the launcher. All it does is run  python hd2suite\app.py  and wait.
                                Its source is launcher\launcher.c (about 100 lines).
  HD2 Mod Tools (console).bat   the same start with a console window, to read error messages
  Get Python runtime.bat        only if there is no folder "python" (see START); runs get_python_runtime.ps1, plain text
  hd2suite\                     the program itself: Python source you can read, item lists (data\) and pictures (images\)
  launcher\                     source of the .exe, its icon, and build.sh to rebuild it
  python\                       the official Python from python.org, unchanged; python\ORIGIN.txt says where it
                                came from and how it was checked. Missing = see START.
  SHA256SUMS.txt                SHA-256 of every file of this release (not of python\: those files carry Python's
                                own digital signatures)
  CREDITS.txt


WHAT IT DOES, AND WHAT IT DOES NOT
  - It reads and writes one kind of file: the save, testament_new.sav
        local copy   %APPDATA%\Arrowhead\Helldivers2\saves\<number>_testament_new.sav
        Steam cloud  <Steam>\userdata\<your id>\553850\remote\testament_new.sav
  - Before it replaces a save, it copies the current one to hd2suite\backups\ and adds a line to
    backups\receipts.jsonl (what was changed, when, where the backup is). It then reads the new file back.
  - It does not write while the game is running, or to the cloud copy while Steam is running.
  - It does not touch the game's own files, does not read or change the running game's memory, and contains no
    network code. Apart from the save you choose, it only writes inside its own folder (settings.json, backups\,
    loadouts\, dumps\, error.log) unless you point those folders elsewhere in SETTINGS.
  - The only download in this folder is "Get Python runtime", and only when you start it.


RISKS
  - The game checks the save. If it does not accept a save, it throws it away and starts a default profile.
    Your backups are in hd2suite\backups\: copy one back (game and Steam closed) to return to it.
  - Ownership is decided by the server, not by the save. Writing an item the account does not own has usually
    ended with the game resetting the save. "(!)" in a list means "never used on this profile, so unknown".
  - The cloud copy needs the steps the program shows (Steam Cloud off, Steam closed), or Steam overwrites it.
  - FILTER on the weapon slots lets you put any weapon in any slot. That is there for experiments.


CHECKING THIS COPY
  - Compare files with SHA256SUMS.txt, for example:   certutil -hashfile "HD2 Mod Tools.exe" SHA256
  - Rebuild the .exe from launcher\ with build.sh (mingw-w64 gcc 13): no timestamp is written, so the result is
    the same file, byte for byte.
  - Self-check of the save code, no window, changes nothing:   python\python.exe hd2suite\tests\check.py
    (or  py -3 hd2suite\tests\check.py ). Give it a folder with .sav files to test those too; they are only read.

If something goes wrong: hd2suite\error.log has the details, and the console .bat shows them as they happen.
