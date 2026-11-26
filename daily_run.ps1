param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$pythonPath = Join-Path $projectDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw 'Create .venv and install requirements.txt before running the daily task.'
}
if (-not $DryRun -and -not (Test-Path -LiteralPath (Join-Path $projectDir '.env') -PathType Leaf)) {
    throw 'Configure .env before running the paid daily task.'
}

$logDir = Join-Path $projectDir 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir ('daily-' + (Get-Date -Format 'yyyy-MM-dd') + '.log')
$arguments = @('pilot.py', '--mode', 'full', '--depth', '20', '--pages', '100',
    '--budget', '0.60', '--serp-reserve', '0.004', '--llm-reserve', '0.005')
if (-not $DryRun) { $arguments += @('--allow-paid', '--confirm-full') }

Push-Location -LiteralPath $projectDir
try {
    "`n--- $(Get-Date -Format o) ---" | Out-File -FilePath $logPath -Append -Encoding utf8
    & $pythonPath @arguments *>&1 | Out-File -FilePath $logPath -Append -Encoding utf8
    $runExit = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $runExit
