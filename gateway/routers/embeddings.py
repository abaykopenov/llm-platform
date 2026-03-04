"""
Embeddings Router — POST /v1/embeddings
Proxies embedding requests to Inference service.
"""

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from schemas.common import EmbeddingRequest

router = APIRouter(tags=["Embeddings"])


@router.post("/v1/embeddings")
async def create_embeddings(req: EmbeddingRequest, request: Request):
    """Create embeddings for input text (OpenAI-compatible)."""
    client: httpx.AsyncClient = request.app.state.http_client
    inference_url = request.app.state.inference_url

    payload = {
        "model": req.model,
        "input": req.input if isinstance(req.input, list) else [req.input],
    }

    try:
        resp = await client.post(
            f"{inference_url}/v1/embeddings",
            json=payload,
            timeout=60.0,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(
            content={"error": {"message": f"Embedding service error: {str(e)}", "type": "server_error"}},
            status_code=502,
        )
