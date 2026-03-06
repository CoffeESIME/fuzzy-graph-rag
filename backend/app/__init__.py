# Copyright (C) 2026 Fabian Romero Hernandez
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License v3.0.
#
# This project is part of an independent academic research on Fuzzy Logic-based
# Multimodal Graph RAG systems (hechoconcafeina).
# Full license: https://www.gnu.org/licenses/agpl-3.0

import logging

# Silence verbose third-party loggers (botocore/MinIO HTTP traces)
for _lib in ('botocore', 'boto3', 'urllib3', 's3transfer'):
    logging.getLogger(_lib).setLevel(logging.WARNING)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from shared.database import create_db_and_tables
from app.routers import router as ingest_router
from app.routers.tasks import router as tasks_router
from app.routers.graph import router as graph_router
from app.routers.sidecar import router as sidecar_router
from app.routers.inbox import router as inbox_router
from app.routers.lyrics import router as lyrics_router
from app.routers.search import router as search_router
from app.routers.analysis import router as analysis_router
from app.routers.enrichment import router as enrichment_router
from app.routers.enrichment_health import router as enrichment_health_router
from app.routers.chat import router as chat_router
from app.routers.explore import router as explore_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    create_db_and_tables()
    yield
    # Shutdown

app = FastAPI(
    title="Multimodal Graph RAG v2",
    lifespan=lifespan
)

# CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "*"  # Allow all for development flexibility
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ingest_router)
app.include_router(tasks_router)
app.include_router(graph_router)
app.include_router(sidecar_router)
app.include_router(inbox_router)
app.include_router(lyrics_router)
app.include_router(search_router)
app.include_router(analysis_router)
app.include_router(enrichment_router)
app.include_router(enrichment_health_router)
app.include_router(chat_router)
app.include_router(explore_router)

@app.get("/")
def read_root():
    return {"message": "Multimodal Graph RAG v2 API is running"}
