#!/bin/bash
# ============================================================
# CELERY WORKER - HEAVY GPU (Local LLM Inference)
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

# Change to backend directory
cd "$(dirname "$0")/.."

echo "🚀 Starting HEAVY GPU Worker..."
echo "   Queue: heavy_gpu"
echo "   Pool: solo (sequential processing)"
echo "   Concurrency: 1 (one task at a time)"
echo ""

poetry run celery -A app.core.celery_app worker \
    --loglevel=info \
    --pool=solo \
    --queues=heavy_gpu \
    --hostname=worker-gpu@%h \
    --without-gossip \
    --without-mingle
