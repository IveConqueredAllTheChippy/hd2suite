<#
get_python_runtime.ps1 - puts the official Python (from python.org) into the folder "python" next to this script,
so that HD2 Mod Tools also runs on a PC that has no Python installed.

Nothing is installed: no registry entry, no PATH change, no administrator rights. To undo it, delete the folder "python".

What it does, in this order (every step is printed while it runs):
  1. download the 64-bit Windows package of Python from python.org ($Url below),
     or use that file if you already put it next to this script
  2. compare its SHA-256 with $Sha256 below - the value python.org publishes for this file in its own index,
     https://www.python.org/ftp/python/index-windows.json
  3. unpack it into a temporary folder here, leaving out the parts a program does not need ($LeaveOut below)
  4. check the digital signature of python.exe, pythonw.exe and python3*.dll:
     it has to be valid and made by the Python Software Foundation
  5. try it: start it, open and close a Tk window, run hd2suite\tests\check.py with it
  6. rename the temporary folder to "python" and write python\ORIGIN.txt (what it is and where it came from)
If a step fails, the temporary folder is removed again and no folder "python" is made.

Works with Windows PowerShell 5.1 (part of Windows 10 / 11) and with PowerShell 7.
#>
param(
    [string]$Url    = 'https://www.python.org/ftp/python/3.14.10/python-3.14.10-amd64.zip',
    [string]$Sha256 = 'cc28026a650970cc1570bb127312f1f9634eb67abfe157ae6ca1acbbc627d091'
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'      # the progress bar of Windows PowerShell makes downloads many times slower

# parts of the package that are not unpacked (documentation, headers and libraries for C programmers, IDLE, pip, demos)
$LeaveOut = 'Doc/', 'include/', 'libs/', 'Scripts/', 'Tools/', 'Lib/idlelib/', 'Lib/turtledemo/', 'Lib/test/',
            'Lib/ensurepip/', 'Lib/site-packages/pip'
$Signer   = 'O=Python Software Foundation'

$here    = $PSScriptRoot
$target  = Join-Path $here 'python'
$temp    = Join-Path $here 'python.unpacking'
$zipName = Split-Path -Leaf ([uri]$Url).AbsolutePath
$zip     = Join-Path $here $zipName
$ownZip  = $false                             # true when this run downloaded the file (then it also removes it)
$ownTemp = $false                             # true when this run made the temporary folder

function Step($text) { Write-Host ''; Write-Host $text -ForegroundColor Yellow }

function LeftOut($name) {
    foreach ($prefix in $LeaveOut) { if ($name.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { return $true } }
    return $false
}

try {
    if (Test-Path -LiteralPath $target) { throw "The folder '$target' is already there. To fetch Python again, rename or delete that folder first." }
    if (Test-Path -LiteralPath $temp)   { throw "A folder '$temp' is left over from an earlier run. Delete it and start again." }

    Step "1. Package: $Url"
    if (Test-Path -LiteralPath $zip) {
        Write-Host "   $zipName is already in this folder; using that file instead of downloading."
    } else {
        Write-Host "   downloading to $zip ..."
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $ownZip = $true
        try { Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing }
        catch { throw "The download failed: $($_.Exception.Message)  You can also download that file with a browser, put it next to this script and start it again." }
    }
    Write-Host ("   {0:N1} MB" -f ((Get-Item -LiteralPath $zip).Length / 1MB))

    Step '2. SHA-256 of the package'
    $hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLower()
    Write-Host "   expected  $($Sha256.ToLower())"
    Write-Host "   this file $hash"
    if ($hash -ne $Sha256.ToLower()) { throw 'The file is not the one this script expects (SHA-256 differs). Nothing was unpacked.' }

    Step "3. Unpacking into $temp"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $root = [IO.Path]::GetFullPath($temp) + [IO.Path]::DirectorySeparatorChar
    [void][IO.Directory]::CreateDirectory($temp); $ownTemp = $true
    $archive = [IO.Compression.ZipFile]::OpenRead($zip)
    $kept = 0; $skipped = 0
    try {
        foreach ($entry in $archive.Entries) {
            $name = $entry.FullName.Replace('\', '/')
            if (LeftOut $name) { $skipped++; continue }
            $path = [IO.Path]::GetFullPath((Join-Path $temp $name))
            if (-not $path.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { throw "The package has an entry that points outside its folder: $name" }
            if ($name.EndsWith('/')) { [void][IO.Directory]::CreateDirectory($path); continue }
            [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path))
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $path, $false)
            $kept++
        }
    } finally { $archive.Dispose() }
    Write-Host "   $kept files unpacked, $skipped left out ($($LeaveOut -join ' '))"

    Step '4. Digital signatures'
    $must = @('python.exe', 'pythonw.exe' | ForEach-Object { Join-Path $temp $_ }) + @(Get-ChildItem -LiteralPath $temp -Filter 'python3*.dll' | ForEach-Object { $_.FullName })
    $subject = ''
    foreach ($file in $must) {
        if (-not (Test-Path -LiteralPath $file)) { throw "The package has no $(Split-Path -Leaf $file) at its top level; this script does not know that layout." }
        $sig = Get-AuthenticodeSignature -LiteralPath $file
        if ("$($sig.Status)" -ne 'Valid' -or "$($sig.SignerCertificate.Subject)" -notmatch [regex]::Escape($Signer)) {
            throw "$(Split-Path -Leaf $file): signature is '$($sig.Status)', signer '$($sig.SignerCertificate.Subject)'. Expected a valid signature of the Python Software Foundation."
        }
        $subject = $sig.SignerCertificate.Subject
        Write-Host "   $(Split-Path -Leaf $file): valid, $subject"
    }
    $binaries = @(Get-ChildItem -LiteralPath $temp -Recurse -File | Where-Object { '.exe', '.dll', '.pyd' -contains $_.Extension.ToLower() })
    $unsigned = @($binaries | Where-Object { "$((Get-AuthenticodeSignature -LiteralPath $_.FullName).Status)" -ne 'Valid' } | ForEach-Object { $_.FullName.Substring($root.Length) })
    Write-Host "   all program files (.exe .dll .pyd): $($binaries.Count), with a valid signature: $($binaries.Count - $unsigned.Count)"
    if ($unsigned) { Write-Host "   without one: $($unsigned -join ', ')" }

    Step '5. Trying it'
    $python = Join-Path $temp 'python.exe'
    & $python -B -I -c "import sys, json, zlib, struct, ctypes, tkinter, tkinter.ttk; r = tkinter.Tk(); r.destroy(); print('   Python', sys.version.split()[0], 'starts, Tk', tkinter.TkVersion, 'opens a window')"
    if ($LASTEXITCODE -ne 0) { throw "This Python does not start or cannot open a window (exit code $LASTEXITCODE)." }
    & $python -B -I ([IO.Path]::Combine($here, 'hd2suite', 'tests', 'check.py'))
    if ($LASTEXITCODE -ne 0) { throw "hd2suite\tests\check.py failed with this Python (exit code $LASTEXITCODE)." }

    Step "6. Finishing: $target"
    $origin = @(
        "This folder is the official Python for Windows from python.org, unpacked by get_python_runtime.ps1 on $(Get-Date -Format 'yyyy-MM-dd').",
        'It is used only by HD2 Mod Tools in the folder above. Nothing was installed; to remove it, delete this folder.',
        '',
        "package    $Url",
        "sha-256    $hash  (checked before unpacking)",
        "signature  python.exe, pythonw.exe, python3*.dll: valid, $subject",
        "program files (.exe .dll .pyd): $($binaries.Count), with a valid signature: $($binaries.Count - $unsigned.Count)",
        "without a signature: $(if ($unsigned) { $unsigned -join ', ' } else { 'none' })",
        "left out   $($LeaveOut -join ' ')  ($skipped files; not needed to run a program)",
        'Every file that is here is unchanged from the package.'
    )
    Set-Content -LiteralPath (Join-Path $temp 'ORIGIN.txt') -Value $origin -Encoding UTF8
    # Windows refuses to rename a folder while any file in it is still open. Right after unpacking and running the new
    # python.exe that is common for a few seconds (a virus scanner reading the new files, or a handle this PowerShell
    # has not released yet), so: release what is ours, then keep trying for up to 30 seconds.
    for ($try = 1; ; $try++) {
        try { Rename-Item -LiteralPath $temp -NewName 'python'; break }
        catch {
            if ($try -ge 60) { throw }
            if ($try -eq 1) {
                Write-Host '   the new files are still in use (often a virus scanner looking at them); waiting, up to 30 seconds ...'
                [GC]::Collect(); [GC]::WaitForPendingFinalizers()
            }
            Start-Sleep -Milliseconds 500
        }
    }
    Write-Host '   "HD2 Mod Tools.exe" now uses this Python. What it is and where it came from: python\ORIGIN.txt' -ForegroundColor Green
    $code = 0
} catch {
    Write-Host ''
    Write-Host "STOPPED: $($_.Exception.Message)" -ForegroundColor Red
    if ($ownTemp -and (Test-Path -LiteralPath $temp)) {
        if (Test-Path -LiteralPath (Join-Path $temp 'ORIGIN.txt')) { Write-Host "The unpacked files are complete but could not be renamed: rename '$temp' to 'python' by hand." }
        else { Remove-Item -LiteralPath $temp -Recurse -Force; Write-Host 'The temporary folder was removed again. No folder "python" was made.' }
    }
    $code = 1
} finally {
    if ($ownZip -and (Test-Path -LiteralPath $zip)) { Remove-Item -LiteralPath $zip -Force }      # only the file this run downloaded
}
exit $code
