# One-click installer for Discord Quest Runner (Windows).
#   Install:    irm https://raw.githubusercontent.com/IamOumarIbrahim/discord-quest-simulator/main/install.ps1 | iex
#   Uninstall:  & ([scriptblock]::Create((irm https://raw.githubusercontent.com/IamOumarIbrahim/discord-quest-simulator/main/install.ps1))) -Uninstall
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'

$Raw      = 'https://raw.githubusercontent.com/IamOumarIbrahim/discord-quest-simulator/main'
$AppDir   = Join-Path $env:LOCALAPPDATA 'DiscordQuestRunner'
$Cache    = Join-Path $env:LOCALAPPDATA 'discord-quest-runner'
$Shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'Discord Quest Runner.lnk'

if ($Uninstall) {
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -like "*$AppDir*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Remove-Item $AppDir, $Cache, $Shortcut -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall' |
        Where-Object { $_.PSChildName -like 'DiscordQuestRunner_*' } | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host 'Uninstalled.'
    return
}

# Find a Python that has tkinter and get its pythonw.exe (no console window).
$pythonw = $null
$probe = 'import sys, tkinter; print(sys.executable)'
$candidates = @(
    @{ Cmd = 'py';     Args = @('-3', '-c', $probe) },
    @{ Cmd = 'python'; Args = @('-c', $probe) }
)
foreach ($c in $candidates) {
    if (-not (Get-Command $c.Cmd -ErrorAction SilentlyContinue)) { continue }
    $exe = & $c.Cmd @($c.Args) 2>$null
    if ($LASTEXITCODE -eq 0 -and $exe) {
        $w = Join-Path (Split-Path $exe) 'pythonw.exe'
        if (Test-Path $w) { $pythonw = $w; break }
    }
}
if (-not $pythonw) {
    Write-Host 'Python 3 with tkinter was not found.'
    Write-Host 'Install it from https://www.python.org/downloads/ (keep "tcl/tk" ticked) or run:'
    Write-Host '  winget install Python.Python.3.12'
    Write-Host 'then run this installer again.'
    return
}

New-Item -ItemType Directory -Force $AppDir | Out-Null
$script = Join-Path $AppDir 'quest_runner.py'
$local  = if ($PSCommandPath) { Join-Path (Split-Path $PSCommandPath) 'quest_runner.py' } else { $null }
if ($local -and (Test-Path $local)) { Copy-Item $local $script -Force }
else { Invoke-WebRequest "$Raw/quest_runner.py" -OutFile $script -UseBasicParsing }

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($Shortcut)
$lnk.TargetPath = $pythonw
$lnk.Arguments = "`"$script`""
$lnk.WorkingDirectory = $AppDir
$lnk.Description = 'Pick games and complete Discord quests'
$lnk.Save()

Write-Host "Installed. Open 'Discord Quest Runner' from the Start menu."
