# Shared helpers for every algorithm's launcher: find Webots, prepare the benchmark Python environment.
# Dot-source it:  . "$StandardEnv\tools\common.ps1"

function Find-Webots {
    $candidates = @()
    if ($env:WEBOTS_HOME) { $candidates += $env:WEBOTS_HOME }
    $candidates += @("$env:ProgramFiles\Webots", "${env:ProgramFiles(x86)}\Webots", "$env:LOCALAPPDATA\Programs\Webots")
    foreach ($c in $candidates) {
        $exe = Join-Path $c 'msys64\mingw64\bin\webots.exe'
        if ($c -and (Test-Path -LiteralPath $exe)) { return [pscustomobject]@{ Home = $c; Exe = $exe } }
    }
    throw "Webots R2025a was not found. Install it from https://cyberbotics.com (default location), or set WEBOTS_HOME."
}

function Find-SystemPython {
    # Python 3.10 or newer, preferring the Windows 'py' launcher.
    $tries = @('py -3.12', 'py -3.11', 'py -3.10', 'py -3', 'python', 'python3')
    foreach ($try in $tries) {
        $t = $try.Split(' ')
        $cmd = Get-Command $t[0] -ErrorAction SilentlyContinue
        if (!$cmd) { continue }
        $pyArgs = @($t | Select-Object -Skip 1) + @('-c', 'import sys; print(sys.executable); print(sys.version_info[0]*100+sys.version_info[1])')
        try { $out = & $t[0] @pyArgs 2>$null } catch { continue }
        if ($LASTEXITCODE -eq 0 -and $out.Count -ge 2 -and [int]$out[1] -ge 310) { return $out[0] }
    }
    throw "Python 3.10 or newer was not found. Install it from https://www.python.org (tick 'Add python.exe to PATH')."
}

function Get-BenchPython([string]$FinalBenchmark) {
    # A private virtual environment shared by all algorithms: identical package versions for everyone.
    $venv = Join-Path $FinalBenchmark '.venv'
    $py = Join-Path $venv 'Scripts\python.exe'
    $req = Join-Path $FinalBenchmark 'requirements.txt'
    $marker = Join-Path $venv 'installed_requirements.txt'
    if (!(Test-Path -LiteralPath $py)) {
        $sys = Find-SystemPython
        Write-Host "Creating the benchmark Python environment with $sys ..."
        & $sys -m venv $venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python virtual environment.' }
    }
    $wanted = Get-Content -Raw -LiteralPath $req
    $have = if (Test-Path -LiteralPath $marker) { Get-Content -Raw -LiteralPath $marker } else { '' }
    if ($wanted -ne $have) {
        Write-Host 'Installing Python packages (first run only; needs internet) ...'
        & $py -m pip install --upgrade pip --quiet
        & $py -m pip install -r $req --quiet
        if ($LASTEXITCODE -ne 0) { throw 'Package installation failed (check the internet connection).' }
        Set-Content -LiteralPath $marker -Value $wanted -NoNewline -Encoding utf8
    }
    return $py
}
