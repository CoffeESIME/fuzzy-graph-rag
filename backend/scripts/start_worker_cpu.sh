#!/bin/bash
# ============================================================
# CELERY WORKER - FAST CPU (Lightweight I/O Tasks)
# ============================================================
# This worker handles quick, parallel tasks:
# - Text chunking
# - SigLIP embeddings
# - Database operations
# - Metadata updates
#
# Uses --pool=prefork for parallel processing
# Consumes ONLY the fast_cpu queue
# ============================================================

# Change to backend directory
cd "$(dirname "$0")/.."

echo "🚀 Starting FAST CPU Worker..."
echo "   Queue: fast_cpu"
echo "   Pool: prefork (parallel processing)"
echo "   Concurrency: 4 (parallel tasks)"
echo ""

poetry run celery -A app.core.celery_app worker \
    --loglevel=info \
    --pool=prefork \
    --concurrency=4 \
    --queues=fast_cpu \
    --hostname=worker-cpu@%h \
    --without-gossip \
    --without-mingle
