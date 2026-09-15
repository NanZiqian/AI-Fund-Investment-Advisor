$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    $taskPython = Get-Command python -ErrorAction SilentlyContinue
    if ($taskPython) {
        & $taskPython.Source -m venv .venv
    } else {
        $taskBundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
        if (-not (Test-Path -LiteralPath $taskBundledPython)) { throw '请先安装 Python 3.12+' }
        & $taskBundledPython -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw '创建虚拟环境失败' }
}
& ./.venv/Scripts/python.exe -m pip install uv
if ($LASTEXITCODE -ne 0) { throw '安装依赖失败' }
& ./.venv/Scripts/uv.exe sync --locked --extra dev --inexact
if ($LASTEXITCODE -ne 0) { throw '安装锁定依赖失败' }
& ./.venv/Scripts/python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw '数据库迁移失败' }
Write-Output '环境已准备好。启动：./scripts/dashboard.ps1'
