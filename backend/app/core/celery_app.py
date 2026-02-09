"""
Celery Application Configuration
=================================

This module configures the Celery application for asynchronous task processing
in the GraphRAG Multimodal system.

Architecture:
- Broker: Redis (db=0) - Message queue for task distribution
- Backend: Redis (db=1) - Result storage for task states
- Queues:
  - queue_heavy: GPU-intensive tasks (Vision, OCR, Audio models)
  - queue_fast: CPU-light tasks (Text processing, embeddings, metadata)
"""

from celery import Celery
from config.settings import get_settings

# Load settings
settings = get_settings()

# ==========================================
# CELERY APP INSTANCE
# ==========================================

app = Celery(
    'graphrag_workers',
    broker=settings.CELERY_BROKER_URL,
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1",  # Use db=1 for results
    include=['worker.tasks']  # Auto-discover tasks from worker module
)

# ==========================================
# CELERY CONFIGURATION
# ==========================================

app.conf.update(
    # Task Execution Settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Reliability & Fault Tolerance
    task_acks_late=True,  # Acknowledge task AFTER completion (prevents task loss on crash)
    worker_prefetch_multiplier=1,  # Fetch one task at a time (prevents worker hoarding heavy tasks)
    
    # Result Backend Settings
    result_expires=3600,  # Keep results for 1 hour
    result_backend_transport_options={
        'master_name': 'mymaster',  # For Redis Sentinel (optional)
    },
    
    # Queue Routing - Heavy GPU vs Fast CPU separation
    task_routes={
        # ===========================================
        # HEAVY GPU QUEUE - Long-running LLM inference
        # ===========================================
        # These tasks call local LLM models and can take 5-15 minutes
        'worker.tasks.process_vector_task': {'queue': 'heavy_gpu'},  # Main dispatcher - routes to LLM
        'worker.tasks.process_visual_semantic': {'queue': 'heavy_gpu'},
        'worker.tasks.process_text_ocr': {'queue': 'heavy_gpu'},
        'worker.tasks.process_text_summary': {'queue': 'heavy_gpu'},  # LLM summarization
        'worker.tasks.process_audio_clap': {'queue': 'heavy_gpu'},
        'worker.tasks.process_audio_transcript': {'queue': 'heavy_gpu'},  # Whisper
        'worker.tasks.process_user_memory': {'queue': 'heavy_gpu'},  # LLM memory analysis
        
        # ===========================================
        # FAST CPU QUEUE - Quick I/O tasks
        # ===========================================
        # These are lightweight embedding/db operations
        'worker.tasks.process_visual_siglip': {'queue': 'fast_cpu'},
        'worker.tasks.process_text_chunk': {'queue': 'fast_cpu'},
    },
    
    # Queue Definitions
    task_queues={
        'heavy_gpu': {
            'exchange': 'heavy_gpu',
            'routing_key': 'heavy',
        },
        'fast_cpu': {
            'exchange': 'fast_cpu',
            'routing_key': 'fast',
        },
    },
    
    # Default time limits for all tasks (can be overridden per-task)
    task_soft_time_limit=600,  # 10 minutes soft limit
    task_time_limit=660,       # 11 minutes hard limit
    
    # Monitoring & Logging
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Retry Policy
    task_default_retry_delay=30,  # 30 seconds
    task_max_retries=3,
)

# ==========================================
# NAMED QUEUES (for apply_async)
# ==========================================

QUEUE_HEAVY = 'queue_heavy'
QUEUE_FAST = 'queue_fast'

# ==========================================
# WORKER STARTUP
# ==========================================

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Configure periodic tasks (cron-like scheduling).
    
    Example:
    sender.add_periodic_task(300.0, cleanup_old_results.s(), name='cleanup every 5min')
    """
    pass  # Add periodic tasks here if needed


if __name__ == '__main__':
    # Start worker with:
    # celery -A app.core.celery_app worker --loglevel=info --queues=queue_heavy,queue_fast
    app.start()
