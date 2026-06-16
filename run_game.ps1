# ============================================================
#  GRANDLINE PIRATES — PowerShell Launcher
#  Double-click this file or run it in PowerShell to start.
# ============================================================

$Host.UI.RawUI.WindowTitle = "Grandline Pirates Launcher"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host ""
Write-Host "  ██████╗ ██████╗  █████╗ ███╗   ██╗██████╗ ██╗     ██╗███╗   ██╗███████╗" -ForegroundColor Cyan
Write-Host "  ██╔════╝ ██╔══██╗██╔══██╗████╗  ██║██╔══██╗██║     ██║████╗  ██║██╔════╝" -ForegroundColor Cyan
Write-Host "  ██║  ███╗██████╔╝███████║██╔██╗ ██║██║  ██║██║     ██║██╔██╗ ██║█████╗  " -ForegroundColor Cyan
Write-Host "  ██║   ██║██╔══██╗██╔══██║██║╚██╗██║██║  ██║██║     ██║██║╚██╗██║██╔══╝  " -ForegroundColor Cyan
Write-Host "  ╚██████╔╝██║  ██║██║  ██║██║ ╚████║██████╔╝███████╗██║██║ ╚████║███████╗" -ForegroundColor Cyan
Write-Host "   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝╚══════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  ██████╗ ██╗██████╗  █████╗ ████████╗███████╗███████╗" -ForegroundColor Yellow
Write-Host "  ██╔══██╗██║██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██╔════╝" -ForegroundColor Yellow
Write-Host "  ██████╔╝██║██████╔╝███████║   ██║   █████╗  ███████╗" -ForegroundColor Yellow
Write-Host "  ██╔═══╝ ██║██╔══██╗██╔══██║   ██║   ██╔══╝  ╚════██║" -ForegroundColor Yellow
Write-Host "  ██║     ██║██║  ██║██║  ██║   ██║   ███████╗███████║" -ForegroundColor Yellow
Write-Host "  ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚══════╝" -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host "  Checking your system..." -ForegroundColor White
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host ""

# ── STEP 1: Check Python ─────────────────────────────────────────────────────
$pythonCmd = $null

foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") {
            $pythonCmd = $cmd
            Write-Host "  [OK] Found Python: $ver" -ForegroundColor Green
            break
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Host "  [!!] Python 3 not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Would you like to install Python automatically?" -ForegroundColor Yellow
    Write-Host "  (Requires internet connection and winget)" -ForegroundColor Gray
    $choice = Read-Host "  Install Python now? (Y/N)"

    if ($choice -match "^[Yy]") {
        Write-Host ""
        Write-Host "  Installing Python 3 via winget..." -ForegroundColor Cyan
        try {
            winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
            Write-Host ""
            Write-Host "  [OK] Python installed! Restarting launcher..." -ForegroundColor Green
            Write-Host "  Please close and re-run this script." -ForegroundColor Yellow
        } catch {
            Write-Host "  [!!] winget failed. Please install Python manually from:" -ForegroundColor Red
            Write-Host "       https://www.python.org/downloads/" -ForegroundColor Cyan
        }
    } else {
        Write-Host ""
        Write-Host "  Please install Python 3 from https://www.python.org/downloads/" -ForegroundColor Cyan
        Write-Host "  Then re-run this launcher." -ForegroundColor White
    }
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}

# ── STEP 2: Check / install pygame ───────────────────────────────────────────
Write-Host "  Checking pygame..." -ForegroundColor White

$pygameCheck = & $pythonCmd -c "import pygame; print(pygame.version.ver)" 2>&1
if ($LASTEXITCODE -eq 0 -and $pygameCheck -match "^\d") {
    Write-Host "  [OK] pygame $pygameCheck already installed." -ForegroundColor Green
} else {
    Write-Host "  [..] pygame not found — installing..." -ForegroundColor Yellow
    & $pythonCmd -m pip install pygame --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] pygame installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "  [!!] Failed to install pygame." -ForegroundColor Red
        Write-Host "  Try running:  pip install pygame" -ForegroundColor Cyan
        Write-Host ""
        Read-Host "  Press Enter to exit"
        exit 1
    }
}

# ── STEP 3: Check game file ───────────────────────────────────────────────────
$gameFile = Join-Path $scriptDir "main.py"

if (-not (Test-Path $gameFile)) {
    Write-Host ""
    Write-Host "  [!!] Game file not found: main.py" -ForegroundColor Red
    Write-Host "  Make sure it is in the same folder as this script:" -ForegroundColor Yellow
    Write-Host "  $scriptDir" -ForegroundColor Gray
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}

Write-Host "  [OK] Game file found." -ForegroundColor Green

# ── STEP 4: Check optional assets ────────────────────────────────────────────
Write-Host ""
Write-Host "  Checking optional assets..." -ForegroundColor White

$assets = @(
    @{ file = "assets\images\Sea_BG.png";                 label = "Ocean background" },
    @{ file = "assets\audio\magiksolo-pirate-tavern-full-version-167990.mp3"; label = "Battle music" },
    @{ file = "assets\audio\MusicBGMenu.mp3";          label = "Menu music" },
    @{ file = "assets\fonts\PressStart2P-Regular.ttf"; label = "Pixel font" },
    @{ file = "assets\images\everything.jpg";             label = "Menu background" },
    @{ file = "assets\audio\Hover.mp3";                label = "Hover sound" },
    @{ file = "assets\audio\Click.Wav";                label = "Click sound" }
)

foreach ($a in $assets) {
    $path = Join-Path $scriptDir $a.file
    if (Test-Path $path) {
        Write-Host ("  [OK] " + $a.label + " (" + $a.file + ")") -ForegroundColor Green
    } else {
        Write-Host ("  [--] " + $a.label + " not found — will use built-in fallback") -ForegroundColor DarkYellow
    }
}

# ── STEP 5: Launch! ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host "  All checks passed!  Launching Grandline Pirates..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host ""

Set-Location $scriptDir
& $pythonCmd $gameFile

# ── After game exits ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Game closed. Thanks for playing Grandline Pirates!" -ForegroundColor Cyan
Write-Host ""
Read-Host "  Press Enter to exit"
