$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not $env:CONDA_PREFIX) {
    throw 'Activate the Conda environment first: conda activate ai-fund-advisor'
}
& python -m streamlit run dashboard/Home.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
