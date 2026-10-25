param(
    [ValidateRange(1,10)][int]$Robots = 10,
    [string]$Scenario = 'baseline',
    [int]$Seconds = 0,
    [int]$IdleSeconds = 1800,
    [int]$LiveMapSeconds = 300,
    [switch]$Gui,
    [switch]$NoBrowser,
    [string]$EvaluateRun = '',
    [switch]$PrepareOnly,
    [switch]$BuildOnly,
    [switch]$RebuildImage
)
$ErrorActionPreference = 'Stop'
$finalBenchmark = Split-Path -Parent $PSScriptRoot
. (Join-Path $finalBenchmark 'Standard Environment\tools\common.ps1')
$python = Get-BenchPython $finalBenchmark
$arguments = @('--robots', $Robots, '--scenario', $Scenario, '--seconds', $Seconds,
               '--idle-seconds', $IdleSeconds, '--live-map-seconds', $LiveMapSeconds)
if ($Gui) { $arguments += '--gui' }
if ($NoBrowser) { $arguments += '--no-browser' }
if ($EvaluateRun) { $arguments += @('--evaluate-run', $EvaluateRun) }
if ($PrepareOnly) { $arguments += '--prepare-only' }
if ($BuildOnly) { $arguments += '--build-only' }
if ($RebuildImage) { $arguments += '--rebuild-image' }
& $python (Join-Path $PSScriptRoot 'run_d2slam.py') @arguments
exit $LASTEXITCODE
