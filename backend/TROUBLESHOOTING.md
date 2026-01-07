# Troubleshooting: Worker No Procesa Tareas

## 🔍 Diagnóstico del Problema

Si no ves logs del worker ni llamadas a la API de LLM Gateway, sigue estos pasos:

---

## 1. Verificar que el Worker esté Corriendo

**Comando para iniciar:**
```bash
cd backend
poetry run celery -A app.core.celery_app worker --loglevel=debug --pool=solo --queues=queue_heavy,queue_fast
```

> [!IMPORTANT]
> Usa `--loglevel=debug` en lugar de `--loglevel=info` para ver TODOS los logs

**Output esperado al arrancar:**
```
[2026-01-06 16:20:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2026-01-06 16:20:00,000: INFO/MainProcess] celery@hostname ready.
[tasks]
  . worker.tasks.process_vector_task
```

---

## 2. Verificar que las Tareas se Despacharon

**En el terminal del worker, deberías ver:**

Cuando se despacha una tarea:
```
[2026-01-06 16:21:00,000: INFO/MainProcess] Task worker.tasks.process_vector_task[task-id] received
[2026-01-06 16:21:00,100: INFO/MainProcess] Starting processing for VectorStatus: uuid-here
[2026-01-06 16:21:00,150: INFO/MainProcess] Processing Asset ... | VectorType: visual_siglip | Privacy: strict_local
```

**Si NO ves esto:**
- ❌ El worker no está recibiendo las tareas
- Posibles causas:
  1. Worker no está corriendo
  2. Worker escuchando colas diferentes
  3. Redis no está corriendo

---

## 3. Verificar Redis Está Corriendo

```bash
# En Windows PowerShell
docker ps | Select-String redis

# Si no hay output, inicia Redis:
docker start redis
# O si no existe:
docker run -d -p 6379:6379 --name redis redis:7
```

**Test manual de Redis:**
```bash
redis-cli ping
# Debe responder: PONG
```

---

## 4. Problema: Worker Arranca pero No Procesa

### Causa Común: La tarea falla inmediatamente

**Ver errores completos:**
```bash
# Reinicia el worker con logging máximo
poetry run celery -A app.core.celery_app worker --loglevel=debug --pool=solo --queues=queue_heavy,queue_fast
```

**Errores comunes:**

#### A. ModuleNotFoundError
```
ModuleNotFoundError: No module named 'worker.tasks'
```

**Solución:**
```bash
# Verifica que worker/__init__.py existe
ls worker/__init__.py

# Debe contener:
from .tasks import process_vector_task
__all__ = ['process_vector_task']
```

#### B. ImportError al cargar dependencies
```
ImportError: cannot import name 'get_minio_client'
```

**Solución:**
```bash
# Verifica shared/clients.py existe
ls shared/clients.py
```

#### C. Database Connection Error
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solución:**
```bash
# Verifica PostgreSQL está corriendo
docker ps | Select-String postgres
```

---

## 5. Problema: Tasks Fallan Silenciosamente

Si el worker recibe la tarea pero falla sin logs visibles:

### Habilitar logging completo en tasks.py

**Edita `worker/tasks.py` línea 21:**
```python
# Cambiar de:
logger = logging.getLogger(__name__)

# A:
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
```

### Ver stack trace completo

En `worker/tasks.py`, dentro del `except Exception as exc:` (línea ~272):

```python
except Exception as exc:
    # Agregar ANTES de actualizar status:
    import traceback
    logger.error(f"FULL TRACEBACK:")
    logger.error(traceback.format_exc())
    
    # Resto del código...
    if vector_status:
        vector_status.status = JobStatus.FAILED
        ...
```

---

## 6. Test Manual: Despachar Tarea Directamente

**Script de prueba (`scripts/test_dispatch.py`):**
```python
from app.core.celery_app import app

# Enviar tarea de prueba
result = app.send_task(
    'worker.tasks.process_vector_task',
    args=['fake-uuid-123'],  # UUID que NO existe
    queue='queue_fast'
)

print(f"Task sent: {result.id}")
print(f"State: {result.state}")

# Esperar resultado
try:
    output = result.get(timeout=10)
    print(f"Result: {output}")
except Exception as e:
    print(f"Error: {e}")
```

**Ejecutar:**
```bash
poetry run python scripts/test_dispatch.py
```

**Esperado:**
- Debería fallar con "VectorStatus fake-uuid-123 not found"
- Pero verás el log "Starting processing for VectorStatus: fake-uuid-123"

---

## 7. Verificar el Flujo Completo

### Checklist Pre-Dispatch

Antes de hacer dispatch desde Streamlit, verifica:

1. ✅ PostgreSQL corriendo → `docker ps | Select-String postgres`
2. ✅ Redis corriendo → `redis-cli ping`
3. ✅ MinIO corriendo → `docker ps | Select-String minio`
4. ✅ Worker Celery corriendo → Ver terminal del worker
5. ✅ Backend FastAPI corriendo → `http://localhost:8000/docs`
6. ✅ Frontend Streamlit corriendo → `http://localhost:8501`

### Logs a Monitorear

**Terminal 1 - Worker:**
```
[INFO] Task worker.tasks.process_vector_task[...] received
[INFO] Starting processing for VectorStatus: ...
[INFO] Processing Asset ... | VectorType: ... | Privacy: ...
[INFO] Downloaded 12345 bytes from MinIO: ...
[LLAMADA HTTP A LLM GATEWAY AQUÍ]
[INFO] Stored ... in Weaviate: ...
[INFO] Successfully completed VectorStatus ...
```

**Terminal 2 - Backend FastAPI:**
```
INFO: 127.0.0.1:... - "POST /tasks/dispatch HTTP/1.1" 200 OK
```

**Terminal 3 - Frontend Streamlit:**
```
✅ X task(s) dispatched successfully!
```

---

## 8. Comando de Diagnóstico Automático

```bash
poetry run python scripts/diagnose_worker.py
```

Este script verifica:
- ✅ Celery configuration
- ✅ Redis connection
- ✅ Worker tasks import
- ✅ Logging configuration
- ✅ Task dispatch test

---

## 9. Reset Completo

Si nada funciona:

```bash
# 1. Detener todo
# Ctrl+C en todos los terminales

# 2. Limpiar Redis
redis-cli FLUSHALL

# 3. Reiniciar Worker con logs máximos
cd backend
poetry run celery -A app.core.celery_app worker --loglevel=debug --pool=solo --queues=queue_heavy,queue_fast

# 4. En otro terminal, test manual
poetry run python scripts/test_dispatch.py
```

---

## 10. Contacto para Debug

Si sigues sin ver logs, comparte:

1. **Output completo del worker al arrancar** (primeras 20 líneas)
2. **Output de `poetry run python scripts/diagnose_worker.py`**
3. **Error en el terminal del worker** (si hay)
