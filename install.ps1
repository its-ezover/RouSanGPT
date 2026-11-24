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
function Winget-Install($id, $what) {
    if (-not (Has-Winget)) { Warn "winget is not available. Install $what yourself."; return $false }
    Say "  Installing $what with winget..."
    & winget install -e --id $id --accept-package-agreements --accept-source-agreements --scope user 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        # some packages (Graphviz) only offer a machine-wide installer
        & winget install -e --id $id --accept-package-agreements --accept-source-agreements 2>&1 | Out-Host
    }
    return ($LASTEXITCODE -eq 0)
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
function Find-Python {
    # The py launcher knows every installed Python. 3.12 has the best package support.
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in @("3.12", "3.13", "3.11", "3.10", "3.14")) {
            $exe = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
        }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") {      # skip the Microsoft Store stub
        & $cmd.Source -c "import sys; sys.exit(sys.version_info < (3, 10))" 2>$null
        if ($LASTEXITCODE -eq 0) { return $cmd.Source }
    }
    foreach ($v in @("312", "313", "311", "310")) {
        $exe = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$v\python.exe"
        if (Test-Path $exe) { return $exe }
    }
    return $null
}
$Python = Find-Python
if (-not $Python) {
    Fail "Python 3.10 or newer is needed."
    if ((Has-Winget) -and (Ask "  Install Python 3.12 now with winget?")) {
        Winget-Install "Python.Python.3.12" "Python 3.12" | Out-Null
        $Python = Find-Python
    }
    if (-not $Python) {
        Write-Host "      Install Python 3.12 from https://www.python.org/downloads/ (or: winget install -e --id Python.Python.3.12)"
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
            Write-Host "      $($t.What): winget install -e --id $($t.Id)"
            $Missing += $t.What
        }
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
        $status = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/status" -TimeoutSec 2
        if ($status.app -eq "RouSanGPT") { return $port }
    } catch { }
    return $null
}
$port = Running-Port
if ($port) {
    Say "RouSanGPT is running. Closing it so it can be updated..."
    try { Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$port/api/quit" -TimeoutSec 5 | Out-Null } catch { }
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
Say "Installing the Python packages (the first time this takes a few minutes)"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$VenvPythonW = Join-Path $Venv "Scripts\pythonw.exe"
if ((Test-Path $VenvPython)) {
    & $VenvPython -c "import sys" 2>$null
    if ($LASTEXITCODE -ne 0) { Remove-Item -Recurse -Force $Venv }     # broken venv
}
if (-not (Test-Path $VenvPython)) {
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the Python environment."; exit 1 }
}
& $VenvPython -m pip install --quiet --upgrade pip
& $VenvPython -m pip install --quiet --upgrade -r (Join-Path $App "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Fail "Installing the Python packages failed (see above). Check the internet connection and run install.cmd again."
    exit 1
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
$cmdFile = Join-Path $Root "rousangpt-console.cmd"
Set-Content -Path $cmdFile -Encoding ASCII -Value @(
    "@echo off",
    "rem RouSanGPT with its messages shown in this window (for troubleshooting)",
    "`"$VenvPython`" -X utf8 `"$App\launcher.py`" --data-dir `"$Data`" --console %*"
)

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
