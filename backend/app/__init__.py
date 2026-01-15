from fastapi import FastAPI
from contextlib import asynccontextmanager
from shared.database import create_db_and_tables
from app.routers import router as ingest_router
from app.routers.tasks import router as tasks_router
from app.routers.graph import router as graph_router

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

# Register routers
app.include_router(ingest_router)
app.include_router(tasks_router)
app.include_router(graph_router)

@app.get("/")
def read_root():
    return {"message": "Multimodal Graph RAG v2 API is running"}
