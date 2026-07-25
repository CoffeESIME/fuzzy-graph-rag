#!/bin/bash
# ============================================================
# BACKEND SERVER - FastAPI + Uvicorn (Development)
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

# Change to backend directory
cd "$(dirname "$0")/.."

echo "🚀 Starting Backend Server (FastAPI)..."
echo "   URL: http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo "   Mode: development (auto-reload)"
echo ""

poetry run uvicorn app:app --reload --port 8000
