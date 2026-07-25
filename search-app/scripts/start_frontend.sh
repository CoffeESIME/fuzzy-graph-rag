#!/bin/bash
# ============================================================
# FRONTEND SERVER - React + Vite (Development)
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

# Change to search-app directory
cd "$(dirname "$0")/.."

echo "🚀 Starting Frontend Server (React + Vite)..."
echo "   URL: http://localhost:5173"
echo "   Mode: development (HMR)"
echo ""

npm run dev
