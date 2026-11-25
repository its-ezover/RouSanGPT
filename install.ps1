# Install (or update) RouSanGPT as a Windows app for this user. No administrator needed
# for the app itself (winget may ask for permission when it installs FFmpeg or Graphviz).
#
#   Double-click install.cmd                 install or update
#   install.cmd -ImportData <folder>         also copy chats, course database and media
#                                            from an existing RouSanGPT folder
#   install.cmd -Yes                         install missing programs without asking
#   install.cmd -DesktopShortcut             also put a shortcut on the desktop
#
# Running it again updates the app and keeps your data.
param(
    [string]$ImportData = "",
    [switch]$Yes,
    [switch]$DesktopShortcut
)
# "Continue": in Windows PowerShell 5.1, "Stop" turns any stderr text from py, pip or
# winget into a fatal error. Steps that must succeed are checked one by one below.
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

$Src = $PSScriptRoot
$Root = Join-Path $env:LOCALAPPDATA "RouSanGPT"
$App = Join-Path $Root "app"
$Venv = Join-Path $Root "venv"
$Data = Join-Path $Root "data"
$StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "RouSanGPT.lnk"
$Desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "RouSanGPT.lnk"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\RouSanGPT"
$Missing = @()

function Say($text) { Write-Host $text -ForegroundColor White }
function Ok($text) { Write-Host "  [ok] $text" -ForegroundColor Green }
function Warn($text) { Write-Host "  [!]  $text" -ForegroundColor Yellow }
function Fail($text) { Write-Host "  [x]  $text" -ForegroundColor Red }
function Ask($question) {
    if ($Yes) { return $true }
    $answer = Read-Host "$question [Y/n]"
    return ($answer -eq "" -or $answer -match "^[Yy]")
}
function Has-Winget { return [bool](Get-Command winget -ErrorAction SilentlyContinue) }
# Programs installed during this run are not on this window's PATH yet: read it again
function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ";"
}
# winget exit codes that mean "it is already there"
$WingetAlreadyThere = @(-1978335189, -1978335135)      # 0x8A15002B, 0x8A150061
function Winget-Install($id, $what) {
    if (-not (Has-Winget)) { Warn "winget is not available. Install $what yourself."; return $false }
    Say "  Installing $what with winget..."
    # "--source winget": only the winget catalog. Without it winget also asks the
    # Microsoft Store, which fails on many networks (certificate errors) and then
    # stops the whole install.
    $common = @("install", "-e", "--id", $id, "--source", "winget",
                "--accept-package-agreements", "--accept-source-agreements")
    & winget @common --scope user 2>&1 | Out-Host
    $code = $LASTEXITCODE
    if ($code -ne 0 -and $WingetAlreadyThere -notcontains $code) {
        # some packages (Graphviz) only offer a machine-wide installer
        & winget @common 2>&1 | Out-Host
        $code = $LASTEXITCODE
    }
    Refresh-Path
    return ($code -eq 0 -or $WingetAlreadyThere -contains $code)
}

# Find a program on PATH or in the usual install folders (same places as binaries.py)
function Find-Tool($exe, $places) {
    $cmd = Get-Command $exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($pattern in $places) {
        $expanded = [Environment]::ExpandEnvironmentVariables($pattern)
        $hits = @(Get-ChildItem -Path (Join-Path $expanded $exe) -ErrorAction SilentlyContinue)
        if ($hits.Count -gt 0) { return $hits[0].FullName }
    }
    return $null
}
$WinGet = "%LOCALAPPDATA%\Microsoft\WinGet"
$FfmpegPlaces = @("$WinGet\Links", "$WinGet\Packages\Gyan.FFmpeg*\*\bin", "$WinGet\Packages\BtbN.FFmpeg*\*\bin", "C:\ffmpeg\bin", "%ProgramFiles%\ffmpeg\bin")
$DotPlaces = @("%ProgramFiles%\Graphviz\bin", "%ProgramFiles(x86)%\Graphviz\bin", "$WinGet\Links")
$OfficePlaces = @("%ProgramFiles%\LibreOffice\program", "%ProgramFiles(x86)%\LibreOffice\program")
$OllamaPlaces = @("%LOCALAPPDATA%\Programs\Ollama", "%ProgramFiles%\Ollama")

Say "RouSanGPT installer"
Write-Host "  app:  $App"
Write-Host "  data: $Data"
Write-Host ""

# ---------- 1. Python ----------
Say "Checking the programs RouSanGPT uses"
# Versions that every package has ready-made downloads for, best first. A newer
# Python may work, but some packages may not support it yet.
$GoodPythons = @("3.12", "3.13", "3.11", "3.14", "3.10")
# The new "Python install manager" behind py.exe may offer to download a missing
# version and wait for an answer: never let it do that here.
$env:PYTHON_MANAGER_AUTOMATIC_INSTALL = "false"
$env:PYTHON_MANAGER_CONFIRM = "false"
$script:OtherPython = $null

function Python-Info($exe) {
    # @(version, full path) of a working python.exe, or $null
    if (-not $exe -or -not (Test-Path $exe)) { return $null }
    $out = $null | & $exe -c "import sys; print('%d.%d' % sys.version_info[:2]); print(sys.executable)" 2>$null
    if ($LASTEXITCODE -ne 0 -or @($out).Count -lt 2) { return $null }
    return @(([string]@($out)[0]).Trim(), ([string]@($out)[1]).Trim())
}
function Find-Python {
    $candidates = @()
    # the py launcher knows every installed Python ("$null |": it must never wait for input)
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in $GoodPythons) {
            $out = $null | & py "-$v" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) { $candidates += ([string]@($out)[-1]).Trim() }
        }
    }
    # python.exe on PATH, except the Microsoft Store shortcut in WindowsApps
    $candidates += @(Get-Command python -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notlike "*\WindowsApps\*" } | ForEach-Object { $_.Source })
    # the usual install folders, any version (python.org per-user and all-users,
    # the Python install manager)
    foreach ($pattern in @((Join-Path $env:LOCALAPPDATA "Programs\Python\Python3*\python.exe"),
                           (Join-Path $env:ProgramFiles "Python3*\python.exe"),
                           (Join-Path $env:LOCALAPPDATA "Python\pythoncore-3*\python.exe"))) {
        $candidates += @(Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    }
    $byVersion = @{}
    foreach ($exe in $candidates) {
        $info = Python-Info $exe
        if ($info -and -not $byVersion.ContainsKey($info[0])) { $byVersion[$info[0]] = $info[1] }
    }
    foreach ($v in $GoodPythons) {
        if ($byVersion.ContainsKey($v)) { return $byVersion[$v] }
    }
    # only a Python newer than the tested ones: kept as a last resort
    foreach ($v in $byVersion.Keys) {
        $parts = $v.Split(".")
        if ([int]$parts[0] -eq 3 -and [int]$parts[1] -gt 14) { $script:OtherPython = $byVersion[$v] }
    }
    return $null
}
$Python = Find-Python
if (-not $Python) {
    if ($script:OtherPython) {
        Warn "Only a very new Python was found ($script:OtherPython). Some packages may not support it yet."
    } else {
        Fail "Python 3.10 to 3.14 is needed (3.12 is best)."
    }
    if ((Has-Winget) -and (Ask "  Install Python 3.12 now with winget?")) {
        Winget-Install "Python.Python.3.12" "Python 3.12" | Out-Null
        $Python = Find-Python
    }
    if (-not $Python -and $script:OtherPython) {
        Warn "Trying with $script:OtherPython."
        $Python = $script:OtherPython
    }
    if (-not $Python) {
        Write-Host "      Install Python 3.12 from https://www.python.org/downloads/ (or: winget install -e --id Python.Python.3.12 --source winget)"
        Write-Host "      then run install.cmd again."
        exit 1
    }
}
$PyVersion = & $Python -c "import platform; print(platform.python_version())"
Ok "Python $PyVersion ($Python)"

# ---------- 2. Other programs ----------
$Tools = @(
    @{ Exe = "ffmpeg.exe"; Places = $FfmpegPlaces; Id = "Gyan.FFmpeg"; What = "FFmpeg"; Use = "videos, animations and voice input"; Required = $true },
    @{ Exe = "dot.exe"; Places = $DotPlaces; Id = "Graphviz.Graphviz"; What = "Graphviz"; Use = "network diagrams"; Required = $true },
    @{ Exe = "soffice.exe"; Places = $OfficePlaces; Id = "TheDocumentFoundation.LibreOffice"; What = "LibreOffice"; Use = "old .ppt files (optional)"; Required = $false },
    @{ Exe = "ollama.exe"; Places = $OllamaPlaces; Id = "Ollama.Ollama"; What = "Ollama"; Use = "the local model, works offline (optional)"; Required = $false }
)
$ToInstall = @()
foreach ($t in $Tools) {
    $found = Find-Tool $t.Exe $t.Places
    if ($found) { Ok "$($t.What) ($($t.Use))" }
    elseif ($t.Required) { Fail "$($t.What) is missing: $($t.Use) will not work."; $ToInstall += $t }
    else { Warn "Optional: $($t.What), for $($t.Use)." }
}
if ($ToInstall.Count -gt 0) {
    $names = ($ToInstall | ForEach-Object { $_.What }) -join " and "
    if ((Has-Winget) -and (Ask "  Install $names now with winget?")) {
        foreach ($t in $ToInstall) {
            if ((Winget-Install $t.Id $t.What) -and (Find-Tool $t.Exe $t.Places)) { Ok "$($t.What) installed" }
            else { Fail "$($t.What) could not be installed."; $Missing += $t.What }
        }
    } else {
        foreach ($t in $ToInstall) {
            Write-Host "      $($t.What): winget install -e --id $($t.Id) --source winget"
            $Missing += $t.What
        }
    }
}

# Microsoft Visual C++ runtime: onnxruntime (used by the course search) needs a
# recent one, and without it the app cannot start ("DLL load failed"). Checked here,
# before the packages, so it is fixed in the same run.
function VCRuntime-Ok {
    $dll = Join-Path $env:WINDIR "System32\msvcp140.dll"
    if (-not (Test-Path $dll)) { return $false }
    $v = (Get-Item $dll).VersionInfo
    return ($v.FileMajorPart -gt 14 -or ($v.FileMajorPart -eq 14 -and $v.FileMinorPart -ge 40))
}
function Install-VCRuntime {
    $id = "Microsoft.VCRedist.2015+.x64"
    if (-not (Has-Winget)) { return $false }
    Say "  Installing the Microsoft Visual C++ runtime with winget (Windows may ask for permission)..."
    # "install" does nothing when an older version is there; "upgrade" updates it
    & winget install -e --id $id --source winget --accept-package-agreements --accept-source-agreements 2>&1 | Out-Host
    if (-not (VCRuntime-Ok)) {
        & winget upgrade -e --id $id --source winget --accept-package-agreements --accept-source-agreements 2>&1 | Out-Host
    }
    return (VCRuntime-Ok)
}
if (VCRuntime-Ok) { Ok "Microsoft Visual C++ runtime" }
else {
    Fail "The Microsoft Visual C++ runtime is missing or too old: the app cannot start without it."
    if ((Has-Winget) -and (Ask "  Install it now with winget?")) {
        if (Install-VCRuntime) { Ok "Microsoft Visual C++ runtime installed" }
        else { Warn "It could not be installed now; the installer checks again after the Python packages." }
    } else {
        Write-Host "      Download it from https://aka.ms/vs/17/release/vc_redist.x64.exe"
    }
}

$Edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($Edge) { Ok "App window: Microsoft Edge (app mode)" }
else { Warn "Microsoft Edge was not found: the app opens in Chrome, Firefox or your default browser." }
Write-Host ""

# ---------- 3. Is the app running? ----------
function Running-Port {
    $info = Join-Path $Data "server.json"
    if (-not (Test-Path $info)) { return $null }
    try {
        $port = (Get-Content $info -Raw | ConvertFrom-Json).port
        $status = Invoke-RestMethod -UseBasicParsing -Uri "http://127.0.0.1:$port/api/status" -TimeoutSec 2
        if ($status.app -eq "RouSanGPT") { return $port }
    } catch { }
    return $null
}
$port = Running-Port
if ($port) {
    Say "RouSanGPT is running. Closing it so it can be updated..."
    try { Invoke-RestMethod -UseBasicParsing -Method Post -Uri "http://127.0.0.1:$port/api/quit" -TimeoutSec 5 | Out-Null } catch { }
    for ($i = 0; $i -lt 30 -and (Running-Port); $i++) { Start-Sleep -Seconds 1 }
    if (Running-Port) { Fail "Please close the RouSanGPT window and run the installer again."; exit 1 }
}

# ---------- 4. Copy the program ----------
Say "Installing the program"
try {
    New-Item -ItemType Directory -Force -Path $Root, $Data -ErrorAction Stop | Out-Null
    $NewApp = Join-Path $Root "app.new"
    if (Test-Path $NewApp) { Remove-Item -Recurse -Force $NewApp -ErrorAction Stop }
    New-Item -ItemType Directory -Force -Path $NewApp -ErrorAction Stop | Out-Null
    Get-ChildItem -Path $Src -Filter *.py | Where-Object { @("test_api.py", "hello.py", "voice_samples.py") -notcontains $_.Name } |
        ForEach-Object { Copy-Item $_.FullName $NewApp -ErrorAction Stop }
    Copy-Item -Recurse (Join-Path $Src "web"), (Join-Path $Src "icons") $NewApp -ErrorAction Stop
    Copy-Item (Join-Path $Src "requirements.txt"), (Join-Path $Src "README.md") $NewApp -ErrorAction Stop
    if (Test-Path (Join-Path $Src "bin")) { Copy-Item -Recurse (Join-Path $Src "bin") $NewApp -ErrorAction Stop }
    if (Test-Path $App) { Remove-Item -Recurse -Force $App -ErrorAction Stop }
    Move-Item $NewApp $App -ErrorAction Stop
    Copy-Item (Join-Path $Src "uninstall.ps1") (Join-Path $Root "uninstall.ps1") -Force -ErrorAction Stop
} catch {
    Fail "Could not copy the program: $($_.Exception.Message)"
    exit 1
}
Ok "Program copied (your .env, chats and course files are not part of the program)"

# ---------- 5. Python packages ----------
Say "Installing the Python packages (the first time this takes a minute or two)"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$VenvPythonW = Join-Path $Venv "Scripts\pythonw.exe"
if (Test-Path $Venv) {
    # start again when the environment is broken or made with another Python version
    $venvInfo = Python-Info $VenvPython
    $wanted = Python-Info $Python
    if (-not $venvInfo -or -not $wanted -or $venvInfo[0] -ne $wanted[0]) {
        Remove-Item -Recurse -Force $Venv -ErrorAction SilentlyContinue
    }
}
if (-not (Test-Path $VenvPython)) {
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) { Fail "Could not create the Python environment."; exit 1 }
}
$Requirements = Join-Path $App "requirements.txt"
$PipOptions = @("--disable-pip-version-check", "--prefer-binary", "--progress-bar", "on")
# uv downloads and installs the packages in parallel: several times faster than pip,
# which fetches and unpacks them one at a time. pip only installs uv itself (one file).
# UV_NATIVE_TLS: trust the Windows certificate store, like pip does, so networks that
# inspect HTTPS still work. If uv fails for any reason, pip does the job instead.
$env:UV_NATIVE_TLS = "true"
$env:UV_CACHE_DIR = Join-Path $Root "uv-cache"
$installed = $false
$Uv = Join-Path $Venv "Scripts\uv.exe"
if (-not (Test-Path $Uv)) {
    & $VenvPython -m pip install --quiet @PipOptions uv 2>&1 | Out-Null
}
if (Test-Path $Uv) {
    & $Uv pip install --python $VenvPython --upgrade -r $Requirements
    $installed = ($LASTEXITCODE -eq 0)
    if (-not $installed) { Warn "The fast installer (uv) failed; trying again with pip (slower)." }
}
if (-not $installed) {
    & $VenvPython -m pip install @PipOptions --upgrade -r $Requirements
    $installed = ($LASTEXITCODE -eq 0)
}
Remove-Item Env:\UV_NATIVE_TLS, Env:\UV_CACHE_DIR -ErrorAction SilentlyContinue
if (-not $installed) {
    Fail "Installing the Python packages failed (see above). Check the internet connection and run install.cmd again."
    exit 1
}

# Load the packages once: a missing Microsoft Visual C++ runtime only shows up here
# ("DLL load failed"), and the app would otherwise fail without a word. The Python
# error text is kept quiet and only shown when it cannot be fixed.
$CheckImports = "import chromadb, onnxruntime, fastapi, uvicorn, google.genai, pptx, pypdf, matplotlib, PIL, numpy, edge_tts, psutil, truststore"
$script:LoadError = ""
function Packages-Load {
    # stored, not shown; "$_" keeps only the text of each line (PowerShell 5.1 would
    # otherwise dress Python's error lines up as a red "NativeCommandError")
    $out = $null | & $VenvPython -X utf8 -c $CheckImports 2>&1
    $script:LoadError = (@($out) | ForEach-Object { "$_" }) -join "`n"
    return ($LASTEXITCODE -eq 0)
}
if (-not (Packages-Load)) {
    if ($script:LoadError -match "DLL load failed") {
        Warn "Some Python packages need the Microsoft Visual C++ runtime."
        if ((Has-Winget) -and (Ask "  Install or update the Microsoft Visual C++ runtime now with winget?")) {
            Install-VCRuntime | Out-Null
        } else {
            Write-Host "      Download it from https://aka.ms/vs/17/release/vc_redist.x64.exe"
        }
    }
    # a fresh install can take a moment before Windows loads it everywhere
    $loaded = $false
    for ($i = 0; $i -lt 3 -and -not $loaded; $i++) {
        if ($i -gt 0) { Start-Sleep -Seconds 3 }
        $loaded = Packages-Load
    }
    if (-not $loaded) {
        Write-Host $script:LoadError
        Fail "The Python packages do not load (see the message above)."
        if ($script:LoadError -match "DLL load failed") {
            Write-Host "      Install the Visual C++ runtime (https://aka.ms/vs/17/release/vc_redist.x64.exe),"
            Write-Host "      restart the computer if it asks to, and run install.cmd again."
        } else {
            Write-Host "      Run install.cmd again; if it happens again, see Troubleshooting in README.md."
        }
        exit 1
    }
}
Ok "Python packages installed"

# ---------- 6. Import existing data ----------
if ($ImportData) {
    if (-not (Test-Path $ImportData)) { Fail "Folder not found: $ImportData"; exit 1 }
    $From = (Resolve-Path $ImportData).Path
    Say "Importing data from $From"
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    foreach ($item in @("course_db", "chats.db", "formula_tools.json", "materials", "videos", "animations", "diagrams", "quizzes")) {
        $source = Join-Path $From $item
        if (-not (Test-Path $source)) { continue }
        $target = Join-Path $Data $item
        if ((Test-Path $target) -and (@(Get-ChildItem $target -Force -ErrorAction SilentlyContinue).Count -gt 0 -or (Test-Path $target -PathType Leaf))) {
            Rename-Item $target "$item.before-import-$stamp"
            Warn "$item already existed; kept the old copy as $item.before-import-$stamp"
        } elseif (Test-Path $target) {
            Remove-Item -Recurse -Force $target
        }
        Copy-Item -Recurse $source $target
        Ok "Imported $item"
    }
    $envFile = Join-Path $From ".env"
    if ((Test-Path $envFile) -and (Select-String -Path $envFile -Pattern "^GEMINI_API_KEY=." -Quiet)) {
        if (Ask "  Use the Gemini API key from $envFile in the app?") {
            $env:ROUSANGPT_DATA_DIR = $Data
            & $VenvPython -X utf8 -c "import sys; sys.path.insert(0, sys.argv[2]); from dotenv import dotenv_values; import settings; settings.save({'gemini_api_key': (dotenv_values(sys.argv[1]).get('GEMINI_API_KEY') or '').strip()})" $envFile $App
            if ($LASTEXITCODE -eq 0) { Ok "API key saved in the app's settings (only on this computer)" }
            Remove-Item Env:\ROUSANGPT_DATA_DIR
        }
    }
}

# ---------- 7. Shortcuts and "Apps & features" ----------
Say "Adding RouSanGPT to the Start menu"
$Icon = Join-Path $App "icons\rousangpt.ico"
$Arguments = "-X utf8 `"$App\launcher.py`" --data-dir `"$Data`""
$shell = New-Object -ComObject WScript.Shell
$links = @($StartMenu)
if ($DesktopShortcut) { $links += $Desktop }
foreach ($path in $links) {
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath = $VenvPythonW              # pythonw: no console window
    $lnk.Arguments = $Arguments
    $lnk.WorkingDirectory = $App
    $lnk.IconLocation = "$Icon,0"
    $lnk.Description = "RouSanGPT - Computer Networks tutor"
    $lnk.Save()
}
Ok "Start menu: RouSanGPT"
if ($DesktopShortcut) { Ok "Desktop shortcut" }

# A console version, handy when something goes wrong
# (UTF-8 without BOM and "chcp 65001", so a user name with Arabic or other non-English
# letters in the path still works; ASCII would turn those letters into "?")
$cmdFile = Join-Path $Root "rousangpt-console.cmd"
$cmdLines = @(
    "@echo off",
    "chcp 65001 >nul",
    "rem RouSanGPT with its messages shown in this window (for troubleshooting)",
    "`"$VenvPython`" -X utf8 `"$App\launcher.py`" --data-dir `"$Data`" --console %*",
    "pause"
)
[IO.File]::WriteAllText($cmdFile, ($cmdLines -join "`r`n") + "`r`n", (New-Object Text.UTF8Encoding $false))

New-Item -Path $UninstallKey -Force | Out-Null
$props = @{
    DisplayName = "RouSanGPT"
    DisplayIcon = $Icon
    Publisher = "RouSanGPT"
    DisplayVersion = "1.0"
    InstallLocation = $Root
    UninstallString = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Root\uninstall.ps1`""
}
foreach ($k in $props.Keys) { Set-ItemProperty -Path $UninstallKey -Name $k -Value $props[$k] }
Set-ItemProperty -Path $UninstallKey -Name NoModify -Value 1 -Type DWord
Set-ItemProperty -Path $UninstallKey -Name NoRepair -Value 1 -Type DWord
Ok "Listed in Settings > Apps (for uninstalling)"

# ---------- Summary ----------
Write-Host ""
Say "RouSanGPT is installed."
Write-Host "  Open it from the Start menu (type RouSanGPT)."
Write-Host "  Your data is in: $Data"
if ($Missing.Count -gt 0) {
    Write-Host ""
    Warn "Still missing: $($Missing -join ', '). The rest of the app works."
}
exit 0
