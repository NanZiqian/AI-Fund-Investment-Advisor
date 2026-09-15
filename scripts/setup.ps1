$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not $env:CONDA_PREFIX) {
    throw 'Activate the Conda environment first: conda activate ai-fund-advisor'
}
& python -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed' }
& python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
Write-Output 'Environment ready. Start the dashboard with: ./scripts/dashboard.ps1'
