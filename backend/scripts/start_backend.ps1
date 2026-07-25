# ============================================================
# BACKEND SERVER - FastAPI + Uvicorn (Development) - Windows
# ============================================================
# This starts the FastAPI backend server with hot-reload:
# - API served at http://localhost:8000
# - Interactive docs at http://localhost:8000/docs
# - Auto-reload on code changes
#
# Prerequisites:
#   - Poetry installed (pip install poetry)
#   - Dependencies installed (poetry install)
#   - Infrastructure running (docker compose up -d)
#   - .env.development configured (see docs/general/QUICKSTART.md)
# ============================================================

Write-Host "🚀 Starting Backend Server (FastAPI)..." -ForegroundColor Green
Write-Host "   URL: http://localhost:8000"
Write-Host "   Docs: http://localhost:8000/docs"
Write-Host "   Mode: development (auto-reload)"
Write-Host ""

Set-Location $PSScriptRoot\..

poetry run uvicorn app:app --reload --port 8000
