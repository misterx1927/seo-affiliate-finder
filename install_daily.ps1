param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(?:[01]\d|2[0-3]):[0-5]\d$')]
    [string]$Time,
    [switch]$Preview
)

$ErrorActionPreference = 'Stop'
$taskName = 'SEO Affiliate Finder - daily'
$runner = Join-Path $PSScriptRoot 'daily_run.ps1'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runner -PathType Leaf) -or
    -not (Test-Path -LiteralPath $pythonPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.env') -PathType Leaf)) {
    throw 'Set up .venv, requirements and .env before scheduling.'
}
if ($Preview) {
    Write-Output "A paid daily run would be scheduled at $Time local time. Estimated budget: USD 0.60 per run."
    exit 0
}
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    throw "Task '$taskName' already exists, it was not replaced."
}
$timeValue = [datetime]::Today.Add([timespan]::ParseExact($Time, 'hh\:mm', $null))
$command = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $runner + '"'
$action = New-ScheduledTaskAction -Execute (Join-Path $PSHOME 'powershell.exe') -Argument $command -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $timeValue
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Paid daily SEO analysis, logs in project logs folder.' | Out-Null
Write-Output "Scheduled '$taskName' at $Time local time for the current user."
