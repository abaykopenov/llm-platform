"""
Embeddings Router — POST /v1/embeddings
Proxies embedding requests to the best available inference node.
"""

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from schemas.common import EmbeddingRequest
from node_manager import node_manager

router = APIRouter(tags=["Embeddings"])


@router.post("/v1/embeddings")
async def create_embeddings(req: EmbeddingRequest, request: Request):
    """Create embeddings for input text (OpenAI-compatible)."""
    client: httpx.AsyncClient = request.app.state.http_client

    # Pick best node (prefer nodes with embedding model)
    node_url = node_manager.get_node_url(model=req.model)

    payload = {
        "model": req.model,
        "input": req.input if isinstance(req.input, list) else [req.input],
    }

    node_manager.track_request_start(node_url)
    try:
        resp = await client.post(
            f"{node_url}/v1/embeddings",
            json=payload,
            timeout=60.0,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(
            content={"error": {"message": f"Embedding service error: {str(e)}", "type": "server_error"}},
            status_code=502,
        )
    finally:
        node_manager.track_request_end(node_url)
