$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& ./.venv/Scripts/python.exe -m streamlit run dashboard/Home.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
