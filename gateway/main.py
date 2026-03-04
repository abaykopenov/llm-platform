"""
LLM Platform — API Gateway
OpenAI-compatible API entry point.
Routes requests to Inference nodes and RAG Engine.

Supports multiple inference nodes via INFERENCE_NODES env var.
"""

import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import chat, files, models, embeddings, health
from middleware.rate_limiter import RateLimiterMiddleware
from middleware.auth import AuthMiddleware
from node_manager import node_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create shared HTTP client
    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0))
    app.state.rag_engine_url = os.getenv("RAG_ENGINE_URL", "http://rag-engine:8200")
    app.state.chromadb_url = os.getenv("CHROMADB_URL", "http://chromadb:8400")

    # ── Parse inference nodes ────────────────────────────────
    # INFERENCE_NODES takes priority, fallback to INFERENCE_URL
    nodes_str = os.getenv("INFERENCE_NODES", "")
    if nodes_str:
        node_urls = [u.strip() for u in nodes_str.split(",") if u.strip()]
    else:
        single_url = os.getenv("INFERENCE_URL", "http://localhost:11434")
        node_urls = [single_url]

    # For backward compatibility
    app.state.inference_url = node_urls[0] if node_urls else "http://localhost:11434"

    # Configure node manager
    node_manager.configure(node_urls, app.state.http_client)
    app.state.node_manager = node_manager

    print("⚡ Gateway started")
    print(f"  RAG Engine: {app.state.rag_engine_url}")
    print(f"  ChromaDB:   {app.state.chromadb_url}")
    print(f"  Inference nodes: {len(node_urls)}")
    for url in node_urls:
        print(f"    → {url}")

    # Start health monitoring
    await node_manager.start()

    yield

    # Shutdown
    await node_manager.stop()
    await app.state.http_client.aclose()
    print("Gateway stopped")


app = FastAPI(
    title="LLM Platform Gateway",
    description="OpenAI-compatible API Gateway for LLM Platform",
    version="2.0.0",
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
    status = node_manager.get_status()
    return {
        "name": "LLM Platform Gateway",
        "version": "2.0.0",
        "docs": "/docs",
        "nodes": status["healthy_nodes"],
        "total_nodes": status["total_nodes"],
        "total_models": status["total_models"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
