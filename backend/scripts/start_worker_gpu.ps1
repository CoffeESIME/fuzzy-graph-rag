# ============================================================
# CELERY WORKER - HEAVY GPU (Local LLM Inference) - Windows
# ============================================================
# This worker handles long-running tasks that require GPU/LLM:
# - Vision analysis (LLM)
# - Text summarization (LLM)
# - OCR extraction (LLM)
# - Audio transcription (Whisper)
# - Memory analysis (LLM)
#
# Uses --pool=solo to avoid multiprocessing overhead during inference
# Consumes ONLY the heavy_gpu queue
# ============================================================

Write-Host "🚀 Starting HEAVY GPU Worker..." -ForegroundColor Green
Write-Host "   Queue: heavy_gpu"
Write-Host "   Pool: solo (sequential processing)"
Write-Host "   Concurrency: 1 (one task at a time)"
Write-Host ""

Set-Location $PSScriptRoot\..

poetry run celery -A app.core.celery_app worker `
    --loglevel=info `
    --pool=solo `
    --queues=heavy_gpu `
    --hostname=worker-gpu@%h
