# ⚡ Quickstart — Infraestructura GraphRAG

Levanta todos los servicios de base de datos en un solo comando.

## Requisitos

- Docker Desktop (o Docker Engine + Compose v2)
- ~6 GB de RAM disponible
- ~10 GB de disco para datos persistentes

## Pasos

```bash
# 1. Copia el archivo de entorno
cp .env.example .env

# 2. Edita las contraseñas en .env (opcional para desarrollo local)

# 3. Levanta todos los servicios
docker compose -f docs/general/docker-compose.yml up -d

# 4. Verifica que estén corriendo
docker compose -f docs/general/docker-compose.yml ps
```

## Servicios y puertos

| Servicio | Puerto local | Consola web | Descripción |
|----------|-------------|-------------|-------------|
| **Neo4j** | `7687` (bolt) | `localhost:7474` | Grafo principal + APOC + GDS |
| **Weaviate** | `8081` | — | Base de datos vectorial |
| **MinIO** | `9005` (API) | `localhost:8001` | Almacenamiento de archivos |
| **Redis** | `6379` | — | Cola Celery |
| **PostgreSQL** | `5432` | — | Metadata y orquestación |

## Variables de entorno

El archivo `.env` debe existir en el mismo directorio donde ejecutas el comando. Ver `.env.example` incluido en este directorio.

```env
NEO4J_PASSWORD=tu_password_neo4j
POSTGRES_PASSWORD=tu_password_postgres
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=tu_password_minio
```

## Detener los servicios

```bash
# Detener sin borrar datos
docker compose -f docs/general/docker-compose.yml down

# Detener Y borrar todos los volúmenes (⚠️ borra los datos)
docker compose -f docs/general/docker-compose.yml down -v
```

## Notas

- Los datos persisten en `./data_dev/` (creado automáticamente).
- Neo4j incluye los plugins **APOC** y **Graph Data Science (GDS)** — requeridos por el backend.
- Weaviate se configura sin vectorizadores propios (`DEFAULT_VECTORIZER_MODULE: none`); los embeddings los genera el backend.
