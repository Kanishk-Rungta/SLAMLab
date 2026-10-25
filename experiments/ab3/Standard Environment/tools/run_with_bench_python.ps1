# Runs a Python launcher with the benchmark environment (Benchmark\.venv, created/updated from
# requirements.txt on first use). Used by the .cmd entry points of the native-algorithm packages.
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_with_bench_python.ps1 <script.py> [args...]
param([Parameter(Mandatory=$true)][string]$Script, [Parameter(ValueFromRemainingArguments=$true)]$Rest)
$ErrorActionPreference = 'Stop'
$SE = Split-Path -Parent $PSScriptRoot
$FB = Split-Path -Parent $SE
. (Join-Path $PSScriptRoot 'common.ps1')
$py = Get-BenchPython $FB
$env:PATH = (Split-Path -Parent $py) + ';' + $env:PATH
& $py $Script @Rest
exit $LASTEXITCODE
