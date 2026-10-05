# Arranque — GraphRAG

**Español** · [English](../en/QUICKSTART.md) · [Índice](../README.md)

Esta guía usa el [Compose de la raíz](../../docker-compose.yml), que incluye la app y la infraestructura. El Compose de `docs/general/` es una configuración alternativa de infraestructura y no es el que usan estos comandos.

## Requisitos

- Docker y Compose v2, con recursos para cinco servicios de almacenamiento/cola, backend, worker y frontend.
- Un gateway de modelos externo compatible con el backend, configurado con `LLM_GATEWAY_URL`. El Compose no instala ese gateway.
- Para transcribir audio: el perfil Whisper CPU o GPU. GPU requiere NVIDIA y soporte de contenedores GPU.

## 1. Preparar la configuración

Ejecuta desde la raíz del repositorio. En PowerShell:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.docker .env }
```

En Bash:

```bash
[ -f .env ] || cp .env.docker .env
```

Edita `.env`: configura credenciales de PostgreSQL, Neo4j y MinIO y la dirección de tu gateway. Dentro de un contenedor, `localhost` apunta al propio contenedor; la plantilla usa `host.docker.internal:8765` para un gateway en el equipo anfitrión. En Linux, verifica que ese nombre se resuelva en tu entorno.

Compose establece los hosts internos de las bases de datos para backend y worker. No copies las credenciales de ejemplo a un despliegue público.

## 2. Arrancar

```bash
docker compose up --build -d
docker compose ps
```

Si necesitas transcripción, usa **uno** de estos comandos en lugar del arranque anterior:

```bash
docker compose --profile cpu up --build -d
# Alternativa con NVIDIA:
docker compose --profile gpu up --build -d
```

## 3. Abrir y comprobar

| Servicio | Dirección o puerto del equipo anfitrión |
|---|---|
| App (Nginx) | [http://localhost](http://localhost) |
| API FastAPI | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Neo4j Browser / Bolt | [http://localhost:7474](http://localhost:7474) / `7687` |
| Weaviate HTTP / gRPC | `8081` / `50051` |
| MinIO API / consola | `9005` / [http://localhost:8001](http://localhost:8001) |
| PostgreSQL | `5432` |
| Redis | `6379` |
| Whisper (si activaste un perfil) | `8778` |

Comprueba que la app abra y que Swagger muestre los endpoints. Después incorpora un archivo pequeño y revisa su tarea: ver la interfaz no confirma que el gateway, los embeddings o el procesamiento funcionen.

```bash
docker compose logs --tail=100 backend worker
```

**GDS:** Comunidades y PageRank llaman procedimientos de Graph Data Science. El Compose principal instala APOC, pero no GDS; esas herramientas requieren configurar una combinación compatible de Neo4j y GDS. No interpretes un error de GDS como ausencia de comunidades.

**Persistencia:** el Compose principal usa volúmenes Docker con nombre. Para detener sin borrar los datos:

```bash
docker compose down
```

Si activaste Whisper, incluye el mismo `--profile cpu` o `--profile gpu` al detener.

## Desarrollo local

Para trabajar en la interfaz contra el backend en `localhost:8000`:

```bash
cd search-app
npm ci
npm run dev
```

Abre [http://localhost:5173](http://localhost:5173). Vite reenvía `/api/*` al backend y elimina el prefijo `/api`. El frontend de Docker usa Nginx y sirve en el puerto 80.

Para ejecutar también el backend fuera de Docker, instala Python compatible con `backend/pyproject.toml` y Poetry. Configura `backend/.env.development` con los servicios accesibles desde el anfitrión (Weaviate `8081`, MinIO `localhost:9005`, Redis `localhost`, PostgreSQL `localhost`, Neo4j `bolt://localhost:7687`).

En dos terminales PowerShell, desde `backend/`:

```powershell
poetry install
$env:ENV_STATE = 'development'
poetry run uvicorn app:app --reload --port 8000
```

```powershell
$env:ENV_STATE = 'development'
poetry run celery -A worker.celery_app worker --loglevel=info --pool=solo
```

`ENV_STATE=development` selecciona explícitamente `.env.development`; el valor predeterminado del lector de configuración es `dev`. En Bash, usa `export ENV_STATE=development`. El worker de Docker usa su configuración Linux; `--pool=solo` es útil para desarrollo en Windows.

Evita ejecutar dos backends en el mismo puerto o workers locales y Docker consumiendo accidentalmente la misma cola. Para un entorno solo de infraestructura:

```bash
docker compose up -d postgres redis minio weaviate neo4j
```

Continúa con la [guía visual](USAGE_GUIDE.md).
