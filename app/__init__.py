from fastapi import FastAPI
from contextlib import asynccontextmanager
from shared.database import create_db_and_tables

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

@app.get("/")
def read_root():
    return {"message": "Multimodal Graph RAG v2 API is running"}
