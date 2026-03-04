"""
Models Router — Model management across all inference nodes.
Aggregates models from all nodes, supports pull/delete for Ollama nodes.
"""

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from node_manager import node_manager

router = APIRouter(tags=["Models"])


@router.get("/v1/models")
async def list_models(request: Request):
    """List available models from all nodes (OpenAI-compatible)."""
    models = node_manager.get_all_models()
    return {
        "object": "list",
        "data": [
            {
                "id": m["name"],
                "object": "model",
                "owned_by": m.get("family", "local"),
                "node": m.get("node", ""),
            }
            for m in models
        ],
    }


@router.get("/api/llm/models")
async def api_llm_models(request: Request):
    """List installed models with details from all nodes."""
    return node_manager.get_all_models()


@router.get("/api/llm/status")
async def api_llm_status(request: Request):
    """LLM cluster status — all nodes, their models, health."""
    cluster = node_manager.get_status()
    all_models = node_manager.get_all_models()
    all_loaded = node_manager.get_all_loaded()

    endpoints = [
        {
            "name": n["name"],
            "url": n["url"],
            "healthy": n["healthy"],
            "server_type": n["server_type"],
            "models_count": n["models_count"],
            "active_requests": n["active_requests"],
            "total_requests": n["total_requests"],
            "error": n.get("error", ""),
        }
        for n in cluster["nodes"]
    ]

    default_model = all_models[0]["name"] if all_models else "Нет моделей"

    return {
        "strategy": "multi-node",
        "default_model": default_model,
        "endpoints": endpoints,
        "models": all_models,
        "loaded_models": all_loaded,
        "cluster": {
            "total_nodes": cluster["total_nodes"],
            "healthy_nodes": cluster["healthy_nodes"],
            "total_models": cluster["total_models"],
        },
    }


@router.get("/api/nodes")
async def api_nodes(request: Request):
    """Get detailed info about all inference nodes."""
    return node_manager.get_status()


@router.post("/api/nodes/refresh")
async def refresh_nodes(request: Request):
    """Force refresh all nodes health and models."""
    await node_manager.check_all_nodes()
    return node_manager.get_status()


@router.post("/api/models/pull")
async def pull_model(request: Request):
    """
    Pull (download) a model. Works with Ollama nodes.
    Body: { "name": "gemma3:4b", "node": "node-1" (optional) }
    """
    client: httpx.AsyncClient = request.app.state.http_client
    data = await request.json()
    model_name = data.get("name", "")
    target_node = data.get("node", "")

    if not model_name:
        return JSONResponse(content={"error": "Model name required"}, status_code=400)

    # Find target Ollama node
    node = None
    for n in node_manager.nodes:
        if target_node and n.name != target_node:
            continue
        if n.healthy and n.server_type == "ollama":
            node = n
            break

    if not node:
        return JSONResponse(
            content={"error": "Нет доступных Ollama-узлов для загрузки моделей"},
            status_code=400,
        )

    async def stream_pull():
        async with client.stream(
            "POST",
            f"{node.url}/api/pull",
            json={"name": model_name, "stream": True},
            timeout=None,
        ) as resp:
            async for line in resp.aiter_lines():
                if line:
                    yield f"data: {line}\n\n"
        yield "data: [DONE]\n\n"
        # Refresh node models after pull
        await node_manager.check_all_nodes()

    return StreamingResponse(
        stream_pull(),
        media_type="text/event-stream",
    )


@router.delete("/api/models/{model_name:path}")
async def delete_model(model_name: str, request: Request):
    """Delete an installed model from an Ollama node."""
    client: httpx.AsyncClient = request.app.state.http_client

    # Find which node has this model
    target_node = None
    for n in node_manager.nodes:
        if n.server_type == "ollama" and n.healthy:
            if any(m.get("name") == model_name for m in n.models):
                target_node = n
                break

    if not target_node:
        # Try first available Ollama node
        for n in node_manager.nodes:
            if n.server_type == "ollama" and n.healthy:
                target_node = n
                break

    if not target_node:
        return JSONResponse(content={"error": "Нет доступного Ollama-узла"}, status_code=400)

    try:
        resp = await client.request(
            "DELETE",
            f"{target_node.url}/api/delete",
            json={"name": model_name},
            timeout=30.0,
        )
        if resp.status_code == 200:
            await node_manager.check_all_nodes()
            return {"ok": True, "deleted": model_name, "node": target_node.name}
        return JSONResponse(content={"error": resp.text}, status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/api/models/running")
async def running_models(request: Request):
    """List currently loaded (running) models across all nodes."""
    return {"models": node_manager.get_all_loaded()}
