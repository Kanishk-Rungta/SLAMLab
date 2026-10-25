#!/bin/bash
# macOS / Linux equivalent of Get-BenchPython (common.ps1): creates or updates the benchmark Python
# environment "<Benchmark>/.venv" from requirements.txt and prints its python path on stdout.
#   PY="$(bash bench_python.sh "<Benchmark>")"
FB="$1"
VENV="$FB/.venv"
REQ="$FB/requirements.txt"
MARKER="$VENV/installed_requirements.txt"

py="$VENV/bin/python"
[ -x "$py" ] || py="$VENV/Scripts/python.exe"        # (a venv made on Windows, e.g. Git Bash)

if [ ! -x "$py" ]; then
    sys_py=""
    for cand in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$cand" >/dev/null 2>&1 &&
           "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
            sys_py="$cand"; break
        fi
    done
    if [ -z "$sys_py" ]; then
        echo "Python 3.10 or newer was not found. Install it from https://www.python.org (macOS installer)" >&2
        echo "or with Homebrew: brew install python@3.12" >&2
        exit 1
    fi
    echo "Creating the benchmark Python environment with $(command -v "$sys_py") ..." >&2
    "$sys_py" -m venv "$VENV" || { echo "Could not create the Python virtual environment." >&2; exit 1; }
    py="$VENV/bin/python"
    [ -x "$py" ] || py="$VENV/Scripts/python.exe"
fi

if ! cmp -s "$REQ" "$MARKER"; then
    echo "Installing Python packages (first run only; needs internet) ..." >&2
    "$py" -m pip install --upgrade pip --quiet >&2
    "$py" -m pip install -r "$REQ" --quiet >&2 || { echo "Package installation failed (check the internet connection)." >&2; exit 1; }
    cp "$REQ" "$MARKER"
fi
echo "$py"
