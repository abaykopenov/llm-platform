"""
RAG Engine — File ingestion, vectorization, and retrieval service.
Provides endpoints for file processing and semantic search.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from storage.vector_store import VectorStore
from storage.file_store import FileStore

CHROMADB_URL = os.getenv("CHROMADB_URL", "http://chromadb:8400")
INFERENCE_URL = os.getenv("INFERENCE_URL", "http://inference:8300")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
DEFAULT_COLLECTION = os.getenv("DEFAULT_COLLECTION", "general")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/data/uploads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize stores
    app.state.vector_store = VectorStore(chromadb_url=CHROMADB_URL)
    app.state.file_store = FileStore(
        upload_dir=UPLOAD_DIR,
        default_collection=DEFAULT_COLLECTION,
    )
    app.state.embedding_model = EMBEDDING_MODEL
    app.state.inference_url = INFERENCE_URL
    app.state.chunk_size = CHUNK_SIZE
    app.state.chunk_overlap = CHUNK_OVERLAP
    app.state.default_collection = DEFAULT_COLLECTION

    print(f"🔍 RAG Engine started")
    print(f"  ChromaDB:  {CHROMADB_URL}")
    print(f"  Inference: {INFERENCE_URL}")
    print(f"  Model:     {EMBEDDING_MODEL}")
    yield
    print("RAG Engine stopped")


app = FastAPI(
    title="LLM Platform RAG Engine",
    description="File ingestion, vectorization, and retrieval",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Import and include routes ────────────────────────────────
from routes import router
app.include_router(router)


@app.get("/")
async def root():
    return {"name": "LLM Platform RAG Engine", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/stats")
async def stats(request=None):
    """RAG Engine statistics."""
    file_store: FileStore = app.state.file_store
    files = file_store.list_files()
    return {
        "total_files": len(files),
        "embedding_model": app.state.embedding_model,
        "chunk_size": app.state.chunk_size,
        "default_collection": app.state.default_collection,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8200, reload=True)
