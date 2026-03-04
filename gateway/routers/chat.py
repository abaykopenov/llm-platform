"""
Chat Completions Router — POST /v1/chat/completions
Proxies to the best available inference node with optional RAG context injection.
Uses NodeManager for load balancing across multiple nodes.
"""

import json
from typing import Optional

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from schemas.chat import ChatCompletionRequest, ChatCompletionResponse
from node_manager import node_manager

router = APIRouter(tags=["Chat"])


@router.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, request: Request):
    """OpenAI-compatible chat completions endpoint with optional RAG."""
    client: httpx.AsyncClient = request.app.state.http_client
    rag_engine_url = request.app.state.rag_engine_url

    # Pick the best node for this model
    node_url = node_manager.get_node_url(model=req.model)

    messages = [m.model_dump() for m in req.messages]

    # ─── RAG Context Injection ────────────────────────────────
    file_ids = None
    rag_top_k = 5
    if req.extra_body:
        file_ids = req.extra_body.get("file_ids")
        rag_top_k = req.extra_body.get("rag_top_k", 5)

    if file_ids:
        last_user_content = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_content = m["content"]
                break

        if last_user_content:
            try:
                rag_resp = await client.post(
                    f"{rag_engine_url}/query",
                    json={
                        "text": last_user_content,
                        "top_k": rag_top_k,
                        "file_ids": file_ids,
                    },
                )
                if rag_resp.status_code == 200:
                    chunks = rag_resp.json().get("results", [])
                    if chunks:
                        context_parts = [c["text"] for c in chunks]
                        context = "\n\n".join(context_parts)
                        rag_system = {
                            "role": "system",
                            "content": (
                                "Используй следующий контекст из документов для ответа.\n"
                                "Если контекст не содержит нужную информацию, ответь на основе "
                                "своих знаний, но укажи это.\n\n"
                                f"=== КОНТЕКСТ ===\n{context}\n=== КОНЕЦ КОНТЕКСТА ==="
                            ),
                        }
                        insert_idx = 0
                        for i, m in enumerate(messages):
                            if m.get("role") == "system":
                                insert_idx = i + 1
                                break
                        messages.insert(insert_idx, rag_system)
            except Exception as e:
                print(f"RAG query failed: {e}")

    # ─── Build inference request ──────────────────────────────
    payload = {
        "model": req.model,
        "messages": messages,
        "stream": req.stream,
    }
    if req.temperature is not None:
        payload["temperature"] = req.temperature
    if req.max_tokens is not None:
        payload["max_tokens"] = req.max_tokens
    if req.top_p is not None:
        payload["top_p"] = req.top_p

    # Track request on the node
    node_manager.track_request_start(node_url)

    # ─── Streaming ────────────────────────────────────────────
    if req.stream:
        async def stream_generator():
            try:
                async with client.stream(
                    "POST",
                    f"{node_url}/v1/chat/completions",
                    json=payload,
                    timeout=300.0,
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            yield f"{line}\n"
                    yield "data: [DONE]\n\n"
            finally:
                node_manager.track_request_end(node_url)

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    # ─── Non-streaming ────────────────────────────────────────
    try:
        resp = await client.post(
            f"{node_url}/v1/chat/completions",
            json=payload,
            timeout=300.0,
        )
        return resp.json()
    finally:
        node_manager.track_request_end(node_url)


@router.post("/api/chat")
async def api_chat(request: Request):
    """
    Legacy chat endpoint compatible with the built-in Web UI.
    Accepts {messages, collection, stream} and proxies to the best inference node.
    """
    client: httpx.AsyncClient = request.app.state.http_client
    rag_engine_url = request.app.state.rag_engine_url

    data = await request.json()
    messages = data.get("messages", [])
    collection = data.get("collection", "")
    stream = data.get("stream", False)
    model = data.get("model")
    temperature = data.get("temperature")
    max_tokens = data.get("max_tokens")

    # Pick the best node
    node_url = node_manager.get_node_url(model=model)

    sources = []

    # RAG context injection via collection name
    if collection and messages:
        last_user_content = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_content = m["content"]
                break

        if last_user_content:
            try:
                rag_resp = await client.post(
                    f"{rag_engine_url}/query",
                    json={
                        "text": last_user_content,
                        "collection": collection,
                        "top_k": 5,
                    },
                    timeout=30.0,
                )
                if rag_resp.status_code == 200:
                    chunks = rag_resp.json().get("results", [])
                    if chunks:
                        context_parts = []
                        for i, c in enumerate(chunks, 1):
                            source_name = c.get("metadata", {}).get("source", "unknown")
                            context_parts.append(f"[Источник {i}: {source_name}]\n{c['text']}")
                            sources.append({
                                "index": i,
                                "source": source_name,
                                "file_id": c.get("metadata", {}).get("file_id", ""),
                                "chunk_index": c.get("metadata", {}).get("chunk_index", 0),
                                "relevance": round(c.get("score", 0), 3) if c.get("score") else None,
                            })

                        context = "\n\n".join(context_parts)
                        rag_system = {
                            "role": "system",
                            "content": (
                                "Ты — помощник, отвечающий на вопросы на основе предоставленных документов.\n"
                                "ПРАВИЛА:\n"
                                "1. Используй ТОЛЬКО информацию из контекста ниже для ответа.\n"
                                "2. В конце ответа ОБЯЗАТЕЛЬНО укажи источники в формате: 📎 Источники: [1] имя_файла, [2] имя_файла\n"
                                "3. Если контекст не содержит ответа, честно скажи: «В загруженных документах я не нашёл ответа на этот вопрос».\n"
                                "4. Отвечай на том же языке, что и вопрос.\n\n"
                                f"=== КОНТЕКСТ ИЗ ДОКУМЕНТОВ ===\n{context}\n=== КОНЕЦ КОНТЕКСТА ==="
                            ),
                        }
                        messages.insert(0, rag_system)
            except Exception as e:
                print(f"RAG query error: {e}")

    payload = {"model": model, "messages": messages, "stream": stream}
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    node_manager.track_request_start(node_url)

    if stream:
        async def stream_gen():
            try:
                async with client.stream(
                    "POST",
                    f"{node_url}/v1/chat/completions",
                    json=payload,
                    timeout=300.0,
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            yield f"{line}\n"
                    yield "data: [DONE]\n\n"
                if sources:
                    yield f"data: {json.dumps({'sources': sources})}\n\n"
            finally:
                node_manager.track_request_end(node_url)

        return StreamingResponse(
            stream_gen(),
            media_type="text/event-stream",
        )

    try:
        resp = await client.post(
            f"{node_url}/v1/chat/completions",
            json=payload,
            timeout=300.0,
        )
        result = resp.json()
        if sources:
            result["sources"] = sources
        return result
    finally:
        node_manager.track_request_end(node_url)
