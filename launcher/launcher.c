/*
 * HD2 Mod Tools - launcher.  All it does: start  hd2suite\app.py  with Python and wait for it.
 *
 *   1. python\pythonw.exe in this folder (the official Python that "Get Python runtime.bat" puts there), or
 *   2. pyw.exe (the "py" launcher of an installed Python), or
 *   3. pythonw.exe found on PATH.
 *
 * It starts:   <python> -B -I "<this folder>\hd2suite\app.py" <the arguments given to this program>
 *   -B  write no .pyc files, so the folder stays as it was unpacked
 *   -I  isolated: ignore PYTHON* environment variables and the user's site-packages
 *
 * No network, no registry, no files written, nothing loaded from anywhere else. The program itself is the
 * readable Python source in hd2suite\ ; this .exe exists so there is something to double-click.
 * Build: see build.sh (mingw-w64).
 */
#ifndef UNICODE
#define UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <stdio.h>

#define TITLE L"HD2 Mod Tools"
#define N 32768                                   /* longest path Windows can hand out */
#define LEN(a) (sizeof (a) / sizeof *(a))

static wchar_t dir[N], script[N], python[N], path[N], cmd[4 * N], msg[N + 1024];

static int is_file(const wchar_t *p) {
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

/* the part of our own command line after the program name, exactly as it was typed */
static const wchar_t *arguments(void) {
    const wchar_t *p = GetCommandLineW();
    if (*p == L'"') { p++; while (*p && *p != L'"') p++; if (*p) p++; }
    else while (*p && *p != L' ' && *p != L'\t') p++;
    while (*p == L' ' || *p == L'\t') p++;
    return p;
}

/* is there a program of this name in one of the PATH folders? its full path goes to python[].
   Only PATH is searched, not the current folder: a stray pyw.exe next to a save file must not be picked up. */
static int on_path(const wchar_t *name) {
    DWORD n = GetEnvironmentVariableW(L"PATH", path, N);
    if (n == 0 || n >= N) return 0;
    n = SearchPathW(path, name, NULL, N, python, NULL);
    return n > 0 && n < N;
}

/* start one Python; 1 = it ran (exit code in *code), 0 = it could not be started */
static int run(const wchar_t *exe, const wchar_t *first, DWORD *code) {
    STARTUPINFOW si; PROCESS_INFORMATION pi;
    int n = _snwprintf(cmd, LEN(cmd), L"\"%ls\" %ls-B -I \"%ls\" %ls", exe, first, script, arguments());
    if (n < 0 || n >= (int)LEN(cmd)) return 0;                                   /* did not fit */
    ZeroMemory(&si, sizeof si); si.cb = sizeof si;
    if (!CreateProcessW(exe, cmd, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) return 0;
    CloseHandle(pi.hThread);
    WaitForSingleObject(pi.hProcess, INFINITE);
    if (!GetExitCodeProcess(pi.hProcess, code)) *code = 1;
    CloseHandle(pi.hProcess);
    return 1;
}

static void say(UINT icon, const wchar_t *format, ...) {
    va_list a; va_start(a, format);
    _vsnwprintf(msg, LEN(msg) - 1, format, a); msg[LEN(msg) - 1] = 0;
    va_end(a);
    MessageBoxW(NULL, msg, TITLE, icon);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR line, int show) {
    DWORD n, code = 0; wchar_t *end; int ran;
    (void)inst; (void)prev; (void)line; (void)show;

    n = GetModuleFileNameW(NULL, dir, N);
    if (n == 0 || n >= N - 32) { say(MB_ICONERROR, L"Could not find out which folder this program is in."); return 2; }
    end = dir + n; while (end > dir && end[-1] != L'\\') end--; *end = 0;          /* keep "C:\...\" */

    lstrcpyW(script, dir); lstrcatW(script, L"hd2suite\\app.py");
    if (!is_file(script)) { say(MB_ICONERROR, L"This file is missing:\n\n%ls\n\nUnpack the whole folder, not only the .exe.", script); return 2; }

    lstrcpyW(python, dir); lstrcatW(python, L"python\\pythonw.exe");
    ran = is_file(python) && run(python, L"", &code);
    if (!ran) ran = on_path(L"pyw.exe") && run(python, L"-3 ", &code);
    if (!ran) ran = on_path(L"pythonw.exe") && run(python, L"", &code);

    if (!ran) {
        say(MB_ICONINFORMATION,
            L"No Python was found to run the program with.\n\n"
            L"Either start \"Get Python runtime.bat\" in this folder (it downloads the official Python from python.org "
            L"into the folder \"python\" here and installs nothing),\n\n"
            L"or install Python 3 from python.org.");
        return 2;
    }
    if (code != 0 && code != 3)                /* 3 = hd2suite failed and has already shown its own message */
        say(MB_ICONERROR, L"The program stopped with an error (code %lu).\n\nIt was started with:\n%ls\n\n"
                          L"To see the error text, start \"HD2 Mod Tools (console).bat\" in this folder. "
                          L"If hd2suite\\error.log exists, the details are in it.", code, python);
    return (int)code;
}
