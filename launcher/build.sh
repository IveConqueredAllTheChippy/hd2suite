#!/bin/sh
# Builds "HD2 Mod Tools.exe" from launcher.c with mingw-w64 (Linux, WSL or MSYS2: package mingw-w64 / gcc-mingw-w64-x86-64).
# No timestamp is written into the file, so the same compiler version gives the same bytes: compare with SHA256SUMS.txt.
set -e
cd "$(dirname "$0")"
x86_64-w64-mingw32-windres launcher.rc -O coff -o launcher.res
x86_64-w64-mingw32-gcc -O2 -Wall -Wextra -municode -mwindows -s -Wl,--no-insert-timestamp -o "HD2 Mod Tools.exe" launcher.c launcher.res
rm launcher.res
x86_64-w64-mingw32-gcc --version | head -1
sha256sum "HD2 Mod Tools.exe"
