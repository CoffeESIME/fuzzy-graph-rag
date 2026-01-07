# Celery Worker Setup Guide

## 🚀 Quick Start

### Start Workers

**Windows (IMPORTANTE - Usar pool=solo):**
```bash
cd backend
poetry run celery -A app.core.celery_app worker --loglevel=info --pool=solo --queues=heavy_gpu,fast_cpu
```

> [!IMPORTANT]
> En Windows DEBES usar `--pool=solo` porque el pool por defecto (prefork) causa `PermissionError`.

**Development Linux/Mac (All Queues):**
```bash
cd backend
poetry run celery -A app.core.celery_app worker --loglevel=info --queues=queue_heavy,queue_fast
```

**Production (Separate Workers):**

Terminal 1 - Heavy GPU Worker:
```bash
poetry run celery -A app.core.celery_app worker \
  --loglevel=info \
  --queues=queue_heavy \
  --concurrency=2 \
  --hostname=heavy@%h
```

Terminal 2 - Fast CPU Worker:
```bash
poetry run celery -A app.core.celery_app worker \
  --loglevel=info \
  --queues=queue_fast \
  --concurrency=4 \
  --hostname=fast@%h
```

---

## 📊 Monitoring

### Flower (Web UI)
```bash
poetry run celery -A app.core.celery_app flower --port=5555
```
Then open: http://localhost:5555

### CLI Inspect
```bash
# Check active workers
poetry run celery -A app.core.celery_app inspect active

# Check registered tasks
poetry run celery -A app.core.celery_app inspect registered

# Check queue stats
poetry run celery -A app.core.celery_app inspect stats
```

---

## 🔧 Configuration Summary

| Setting | Value | Purpose |
|---------|-------|---------|
| **Broker** | `redis://localhost:6379/0` | Task queue |
| **Backend** | `redis://localhost:6379/1` | Result storage |
| **queue_heavy** | GPU tasks | OCR, Vision, Audio models |
| **queue_fast** | CPU tasks | Text, Embeddings, Metadata |
| **acks_late** | `True` | No task loss on crash |
| **prefetch_multiplier** | `1` | Fair task distribution |

---

## 📝 Task Routing

Tasks are automatically routed based on VectorType:

**Heavy GPU Queue:**
- `visual_semantic` → Uses multimodal LLMs
- `text_ocr` → Uses vision-text extraction
- `audio_clap` → Audio processing models
- `audio_transcript` → Speech-to-text models

**Fast CPU Queue:**
- `visual_siglip` → Lightweight embeddings
- `text_chunk` → Simple text processing
- `text_summary` → Text operations
- `user_memory` → Memory updates

---

## 🧪 Testing

```python
# Test task dispatch
from app.core.celery_app import app

# Send test task to heavy queue
result = app.send_task('worker.tasks.process_vector_task', 
                        args=['task-uuid'],
                        queue='queue_heavy')

# Check result
print(result.get(timeout=10))
```
