# ============================================================
# CELERY WORKER - FAST CPU (Lightweight I/O Tasks) - Windows
# ============================================================
# This worker handles quick, parallel tasks:
# - Text chunking
# - SigLIP embeddings
# - Database operations
# - Metadata updates
#
# Uses --pool=prefork for parallel processing (Note: prefork has issues on Windows, use solo)
# Consumes ONLY the fast_cpu queue
# ============================================================

Write-Host "🚀 Starting FAST CPU Worker..." -ForegroundColor Green
Write-Host "   Queue: fast_cpu"
Write-Host "   Pool: solo (Windows limitation)"
Write-Host "   Note: prefork doesn't work well on Windows, using solo instead"
Write-Host ""

Set-Location $PSScriptRoot\..

# Note: On Windows, prefork pool has issues. Using solo pool instead.
# For true parallelism on Windows, run multiple instances of this script.
poetry run celery -A app.core.celery_app worker `
    --loglevel=info `
    --pool=solo `
    --queues=fast_cpu `
    --hostname=worker-cpu@%h
