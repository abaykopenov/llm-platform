"""
Models Router — Model management via Ollama API.
Supports listing, pulling, and deleting models dynamically.
"""

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(tags=["Models"])


@router.get("/v1/models")
async def list_models(request: Request):
    """List available models (OpenAI-compatible)."""
    client: httpx.AsyncClient = request.app.state.http_client
    inference_url = request.app.state.inference_url

    try:
        resp = await client.get(f"{inference_url}/v1/models", timeout=10.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Failed to fetch models: {e}")

    return {"object": "list", "data": []}


@router.get("/api/llm/models")
async def api_llm_models(request: Request):
    """List installed Ollama models with details."""
    client: httpx.AsyncClient = request.app.state.http_client
    inference_url = request.app.state.inference_url

    try:
        resp = await client.get(f"{inference_url}/api/tags", timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("models", [])
    except Exception:
        pass
    return []


@router.get("/api/llm/status")
async def api_llm_status(request: Request):
    """LLM status — health check + loaded models."""
    client: httpx.AsyncClient = request.app.state.http_client
    inference_url = request.app.state.inference_url

    endpoint_info = {
        "name": "ollama-inference",
        "url": inference_url,
        "healthy": False,
        "requests_served": 0,
        "avg_tokens_per_sec": 0,
    }

    # Health check
    try:
        resp = await client.get(f"{inference_url}/api/tags", timeout=5.0)
        endpoint_info["healthy"] = resp.status_code == 200
    except Exception:
        pass

    # Installed models
    models = []
    try:
        resp = await client.get(f"{inference_url}/api/tags", timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            models = [
                {
                    "name": m.get("name", ""),
                    "size_gb": round(m.get("size", 0) / (1024**3), 1),
                    "family": m.get("details", {}).get("family", ""),
                    "parameters": m.get("details", {}).get("parameter_size", ""),
                    "quantization": m.get("details", {}).get("quantization_level", ""),
                }
                for m in data.get("models", [])
            ]
    except Exception:
        pass

    # Currently loaded models
    loaded = []
    try:
        resp = await client.get(f"{inference_url}/api/ps", timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            loaded = [
                {
                    "name": m.get("name", ""),
                    "size_gb": round(m.get("size", 0) / (1024**3), 1),
                    "vram_gb": round(m.get("size_vram", 0) / (1024**3), 1),
                }
                for m in data.get("models", [])
            ]
    except Exception:
        pass

    # Default model from installed list
    default_model = models[0]["name"] if models else "Нет моделей"

    return {
        "strategy": "ollama",
        "default_model": default_model,
        "endpoints": [endpoint_info],
        "models": models,
        "loaded_models": loaded,
    }


@router.post("/api/models/pull")
async def pull_model(request: Request):
    """
    Pull (download) a model from Ollama library.
    Body: { "name": "gemma3:4b" }
    Streams the download progress.
    """
    client: httpx.AsyncClient = request.app.state.http_client
    inference_url = request.app.state.inference_url
    data = await request.json()
    model_name = data.get("name", "")

    if not model_name:
        return JSONResponse(content={"error": "Model name required"}, status_code=400)

    async def stream_pull():
        async with client.stream(
            "POST",
            f"{inference_url}/api/pull",
            json={"name": model_name, "stream": True},
            timeout=None,  # Model downloads can take a long time
        ) as resp:
            async for line in resp.aiter_lines():
                if line:
                    yield f"data: {line}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_pull(),
        media_type="text/event-stream",
    )


@router.delete("/api/models/{model_name:path}")
async def delete_model(model_name: str, request: Request):
    """Delete an installed model."""
    client: httpx.AsyncClient = request.app.state.http_client
    inference_url = request.app.state.inference_url

    try:
        resp = await client.request(
            "DELETE",
            f"{inference_url}/api/delete",
            json={"name": model_name},
            timeout=30.0,
        )
        if resp.status_code == 200:
            return {"ok": True, "deleted": model_name}
        return JSONResponse(content={"error": resp.text}, status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/api/models/running")
async def running_models(request: Request):
    """List currently loaded (running) models in GPU memory."""
    client: httpx.AsyncClient = request.app.state.http_client
    inference_url = request.app.state.inference_url

    try:
        resp = await client.get(f"{inference_url}/api/ps", timeout=5.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"models": []}
