"""
LLM Platform — API Gateway
OpenAI-compatible API entry point.
Routes requests to Inference and RAG Engine services.
"""

import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import chat, files, models, embeddings, health
from middleware.rate_limiter import RateLimiterMiddleware
from middleware.auth import AuthMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create shared HTTP client
    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
    app.state.inference_url = os.getenv("INFERENCE_URL", "http://inference:8300")
    app.state.rag_engine_url = os.getenv("RAG_ENGINE_URL", "http://rag-engine:8200")
    app.state.chromadb_url = os.getenv("CHROMADB_URL", "http://chromadb:8400")
    print("⚡ Gateway started")
    print(f"  Inference:  {app.state.inference_url}")
    print(f"  RAG Engine: {app.state.rag_engine_url}")
    print(f"  ChromaDB:   {app.state.chromadb_url}")
    yield
    # Shutdown
    await app.state.http_client.aclose()
    print("Gateway stopped")


app = FastAPI(
    title="LLM Platform Gateway",
    description="OpenAI-compatible API Gateway for LLM Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Middleware ────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter
rpm = int(os.getenv("RATE_LIMIT_RPM", "60"))
app.add_middleware(RateLimiterMiddleware, requests_per_minute=rpm)

# Auth (optional)
api_keys_str = os.getenv("API_KEYS", "")
if api_keys_str:
    api_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]
    app.add_middleware(AuthMiddleware, api_keys=api_keys)

# ─── Routers ──────────────────────────────────────────────────
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(models.router)
app.include_router(embeddings.router)
app.include_router(health.router)


@app.get("/")
async def root():
    return {
        "name": "LLM Platform Gateway",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
