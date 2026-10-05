# Quickstart — GraphRAG

[Español (principal)](../general/QUICKSTART.md) · **English** · [Index](README.md)

This guide uses the [root Compose file](../../docker-compose.yml), which includes the app and infrastructure. The Compose file under `docs/general/` is an alternative infrastructure configuration and is not used by these commands.

## Requirements

- Docker and Compose v2, with resources for five storage/queue services, the backend, worker, and frontend.
- An external model gateway compatible with the backend, configured through `LLM_GATEWAY_URL`. Compose does not install this gateway.
- For transcription, either the CPU or GPU Whisper profile. GPU requires NVIDIA hardware and container GPU support.

## 1. Configure

Run from the repository root. PowerShell:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.docker .env }
```

Bash:

```bash
[ -f .env ] || cp .env.docker .env
```

Edit `.env` to configure PostgreSQL, Neo4j, and MinIO credentials and your gateway address. Inside a container, `localhost` refers to that container. The template uses `host.docker.internal:8765` for a gateway on the host; on Linux, check that this hostname resolves in your environment.

Compose sets the internal database hosts for the backend and worker. Do not reuse example credentials for a public deployment.

## 2. Start

```bash
docker compose up --build -d
docker compose ps
```

For transcription, use **one** of these commands instead:

```bash
docker compose --profile cpu up --build -d
# NVIDIA alternative:
docker compose --profile gpu up --build -d
```

## 3. Open and check

| Service | Host address or port |
|---|---|
| App (Nginx) | [http://localhost](http://localhost) |
| FastAPI | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Neo4j Browser / Bolt | [http://localhost:7474](http://localhost:7474) / `7687` |
| Weaviate HTTP / gRPC | `8081` / `50051` |
| MinIO API / console | `9005` / [http://localhost:8001](http://localhost:8001) |
| PostgreSQL | `5432` |
| Redis | `6379` |
| Whisper (with a profile enabled) | `8778` |

Check that the app opens and Swagger lists the endpoints. Then ingest a small file and inspect its task: loading the UI does not verify the gateway, embeddings, or processing pipeline.

```bash
docker compose logs --tail=100 backend worker
```

**GDS:** Communities and PageRank call Graph Data Science procedures. The root Compose installs APOC, but not GDS. These tools need a compatible Neo4j/GDS installation; a GDS error does not mean the corpus has no communities.

**Persistence:** the root Compose uses named Docker volumes. Stop without removing data:

```bash
docker compose down
```

If Whisper was enabled, include the same `--profile cpu` or `--profile gpu` when stopping.

## Local development

To develop the interface against the backend at `localhost:8000`:

```bash
cd search-app
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite forwards `/api/*` to the backend and strips `/api`. The Docker frontend uses Nginx on port 80.

To run the backend outside Docker too, install Poetry and a Python version compatible with `backend/pyproject.toml`. Configure `backend/.env.development` with host-accessible services (Weaviate `8081`, MinIO `localhost:9005`, Redis and PostgreSQL `localhost`, Neo4j `bolt://localhost:7687`).

In two PowerShell terminals, from `backend/`:

```powershell
poetry install
$env:ENV_STATE = 'development'
poetry run uvicorn app:app --reload --port 8000
```

```powershell
$env:ENV_STATE = 'development'
poetry run celery -A worker.celery_app worker --loglevel=info --pool=solo
```

`ENV_STATE=development` explicitly selects `.env.development`; the settings reader defaults to `dev`. In Bash, use `export ENV_STATE=development`. The Docker worker uses its Linux configuration; `--pool=solo` is useful for Windows development.

Avoid running two backends on the same port or unintentionally sharing a queue between local and Docker workers. For infrastructure only:

```bash
docker compose up -d postgres redis minio weaviate neo4j
```

Continue with the [visual user guide](USAGE_GUIDE.md).
