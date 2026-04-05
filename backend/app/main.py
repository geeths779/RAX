from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise shared clients (DB, Neo4j, Qdrant)
    # Person 1 will wire db/session, neo4j_client, qdrant_client here
    yield
    # Shutdown: close connections


settings = get_settings()

app = FastAPI(
    title="RAX — Resume Analysis eXpert",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
