# Build the Windows setup program: dist\RouSanGPT-Setup.exe
#
# The setup contains everything the app needs, so students install nothing else:
# Python, the Python packages, FFmpeg, Graphviz and the course-search model.
# Runs on Windows with PowerShell 7 (pwsh), Inno Setup 6 and a Python of the same
# version as -PythonVersion (major.minor). GitHub Actions runs it for every change
# (.github/workflows/windows-setup.yml).
#
#   pwsh windows\build.ps1 [-Version 1.2.0] [-HostPython python]
param(
    [string]$Version = (Get-Date -Format "yyyy.M.d"),
    [string]$PythonVersion = "3.13.12",
    [string]$GraphvizVersion = "16.1.2",
    [string]$HostPython = "python"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Repo = Split-Path $PSScriptRoot -Parent
$Build = Join-Path $Repo "build"
$Downloads = Join-Path $Build "downloads"
$Stage = Join-Path $Build "RouSanGPT"          # becomes the install folder
$Py = Join-Path $Stage "python"
$App = Join-Path $Stage "app"
$Bin = Join-Path $App "bin"

function Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Check-Exit($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" } }
function Get-File($url, $name) {
    $path = Join-Path $Downloads $name
    if (-not (Test-Path $path)) {
        Write-Host "    downloading $url"
        Invoke-WebRequest -Uri $url -OutFile "$path.part"
        Move-Item "$path.part" $path
    }
    return $path
}
function Expand-To-Temp($zip) {
    $dir = Join-Path $Build ("unzip-" + [IO.Path]::GetFileNameWithoutExtension($zip))
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
    Expand-Archive $zip $dir
    return $dir
}

if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force -Path $Downloads, $Stage, $App, $Bin | Out-Null

# ---------- 1. Python (the official "embeddable" Python: no installer, no registry) ----------
Step "Python $PythonVersion"
$short = ($PythonVersion.Split(".")[0..1]) -join "."
$hostVersion = (& $HostPython -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
if ($hostVersion -ne $short) { throw "-HostPython is Python $hostVersion; Python $short is needed to install the packages" }
Expand-Archive (Get-File "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" "python-$PythonVersion-embed-amd64.zip") $Py
# Where the bundled Python looks for modules: its own, the packages and the app
$tag = $short.Replace(".", "")
Set-Content -Path (Join-Path $Py "python$tag._pth") -Encoding ascii -Value @(
    "python$tag.zip", ".", "Lib\site-packages", "..\app", "import site")

# The Microsoft Visual C++ runtime, next to python.exe: the packages (onnxruntime)
# need a recent one, and many computers have none or an old one. Kept here, the app
# never needs administrator rights or a separate runtime installer.
foreach ($dll in @("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "msvcp140_atomic_wait.dll",
                   "msvcp140_codecvt_ids.dll", "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll")) {
    $source = Join-Path $env:WINDIR "System32\$dll"
    if (Test-Path $source) { Copy-Item $source $Py -Force }
    elseif ($dll -like "msvcp140*.dll" -and $dll -ne "msvcp140_atomic_wait.dll" -and $dll -ne "msvcp140_codecvt_ids.dll") {
        throw "$dll was not found on the build machine"
    }
}

# ---------- 2. Python packages ----------
Step "Python packages"
$sitePackages = Join-Path $Py "Lib\site-packages"
& $HostPython -m pip install --disable-pip-version-check --no-warn-script-location --prefer-binary `
    --target $sitePackages -r (Join-Path $Repo "requirements.txt")
Check-Exit "pip install"
# command-line launchers made for the build machine's Python: not used by the app
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue (Join-Path $sitePackages "bin")

# ---------- 3. The program ----------
Step "RouSanGPT"
Get-ChildItem -Path $Repo -Filter *.py | Where-Object { @("test_api.py", "hello.py", "voice_samples.py") -notcontains $_.Name } |
    ForEach-Object { Copy-Item $_.FullName $App }
Copy-Item -Recurse (Join-Path $Repo "web"), (Join-Path $Repo "icons") $App
Copy-Item (Join-Path $Repo "requirements.txt"), (Join-Path $Repo "README.md") $App
Copy-Item (Join-Path $PSScriptRoot "rousangpt-console.cmd") $Stage

# ---------- 4. FFmpeg and Graphviz (found by binaries.py in app\bin) ----------
Step "FFmpeg"
$ffmpegDir = Expand-To-Temp (Get-File "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" "ffmpeg-release-essentials.zip")
Copy-Item (Get-ChildItem -Recurse -Path $ffmpegDir -Filter ffmpeg.exe | Select-Object -First 1).FullName $Bin
Copy-Item (Get-ChildItem -Recurse -Path $ffmpegDir -Filter LICENSE | Select-Object -First 1).FullName (Join-Path $Bin "FFmpeg-LICENSE.txt")

Step "Graphviz $GraphvizVersion"
$gvZip = "windows_10_cmake_Release_Graphviz-$GraphvizVersion-win64.zip"
$gvDir = Expand-To-Temp (Get-File "https://gitlab.com/api/v4/projects/4207231/packages/generic/graphviz-releases/$GraphvizVersion/$gvZip" $gvZip)
$gvBin = (Get-ChildItem -Recurse -Path $gvDir -Filter dot.exe | Select-Object -First 1).Directory.FullName
Copy-Item (Join-Path $gvBin "dot.exe") $Bin
Copy-Item (Join-Path $gvBin "*.dll") $Bin
& (Join-Path $Bin "dot.exe") -c                 # registers the plugins (writes bin\config6)
Check-Exit "dot -c"

# ---------- 5. Check everything with the bundled Python, save the search model ----------
Step "Checking the bundle"
$env:ROUSANGPT_DATA_DIR = Join-Path $Build "check-data"
if (Test-Path $env:ROUSANGPT_DATA_DIR) { Remove-Item -Recurse -Force $env:ROUSANGPT_DATA_DIR }
& (Join-Path $Py "python.exe") -X utf8 (Join-Path $PSScriptRoot "check_bundle.py") $App
Check-Exit "check_bundle.py"
Remove-Item Env:\ROUSANGPT_DATA_DIR

# ---------- 6. The setup program ----------
Step "Setup program (Inno Setup)"
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { throw "Inno Setup 6 is needed (https://jrsoftware.org/isdl.php, or: choco install innosetup)" }
& $iscc "/DAppVersion=$Version" (Join-Path $PSScriptRoot "RouSanGPT.iss")
Check-Exit "Inno Setup"
$setup = Get-Item (Join-Path $Repo "dist\RouSanGPT-Setup.exe")
Write-Host ("Done: {0} ({1:N0} MB)" -f $setup.FullName, ($setup.Length / 1MB)) -ForegroundColor Green
