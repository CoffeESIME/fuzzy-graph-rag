# ============================================================
# FRONTEND SERVER - React + Vite (Development) - Windows
# ============================================================
# This starts the Vite dev server for the React frontend:
# - App served at http://localhost:5173
# - Hot Module Replacement (HMR) enabled
# - Auto-reload on code changes
#
# Prerequisites:
#   - Node.js installed (v18+)
#   - Dependencies installed (npm install)
#   - Backend running at http://localhost:8000
# ============================================================

Write-Host "🚀 Starting Frontend Server (React + Vite)..." -ForegroundColor Green
Write-Host "   URL: http://localhost:5173"
Write-Host "   Mode: development (HMR)"
Write-Host ""

Set-Location $PSScriptRoot\..

npm run dev
