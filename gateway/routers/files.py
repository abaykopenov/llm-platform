"""
Files Router — /v1/files endpoints
Proxies file operations to RAG Engine service.
"""

from typing import Optional

import httpx
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Files"])


@router.post("/v1/files")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    collection: Optional[str] = Form("general"),
):
    """Upload a file for RAG processing."""
    client: httpx.AsyncClient = request.app.state.http_client
    rag_url = request.app.state.rag_engine_url

    file_content = await file.read()

    resp = await client.post(
        f"{rag_url}/ingest",
        files={"file": (file.filename, file_content, file.content_type or "application/octet-stream")},
        data={"collection": collection},
        timeout=120.0,
    )

    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@router.get("/v1/files")
async def list_files(
    request: Request,
    collection: Optional[str] = None,
):
    """List all uploaded files."""
    client: httpx.AsyncClient = request.app.state.http_client
    rag_url = request.app.state.rag_engine_url

    params = {}
    if collection:
        params["collection"] = collection

    resp = await client.get(f"{rag_url}/files", params=params)
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@router.get("/v1/files/{file_id}")
async def get_file(file_id: str, request: Request):
    """Get file info by ID."""
    client: httpx.AsyncClient = request.app.state.http_client
    rag_url = request.app.state.rag_engine_url

    resp = await client.get(f"{rag_url}/files/{file_id}")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@router.delete("/v1/files/{file_id}")
async def delete_file(file_id: str, request: Request):
    """Delete a file and its vectors."""
    client: httpx.AsyncClient = request.app.state.http_client
    rag_url = request.app.state.rag_engine_url

    resp = await client.delete(f"{rag_url}/files/{file_id}")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


# ─── Legacy endpoints (Web UI compatibility) ─────────────────

@router.post("/api/upload")
async def api_upload(
    request: Request,
    file: UploadFile = File(...),
    collection: Optional[str] = Form("general"),
):
    """Legacy upload endpoint for the built-in Web UI."""
    client: httpx.AsyncClient = request.app.state.http_client
    rag_url = request.app.state.rag_engine_url

    file_content = await file.read()
    resp = await client.post(
        f"{rag_url}/ingest",
        files={"file": (file.filename, file_content, file.content_type or "application/octet-stream")},
        data={"collection": collection},
        timeout=120.0,
    )
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@router.get("/api/files")
async def api_list_files(request: Request):
    """Legacy list files endpoint."""
    client: httpx.AsyncClient = request.app.state.http_client
    rag_url = request.app.state.rag_engine_url
    resp = await client.get(f"{rag_url}/files")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@router.delete("/api/files/{file_id}")
async def api_delete_file(file_id: str, request: Request):
    """Legacy delete file endpoint."""
    client: httpx.AsyncClient = request.app.state.http_client
    rag_url = request.app.state.rag_engine_url
    resp = await client.delete(f"{rag_url}/files/{file_id}")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@router.get("/api/collections")
async def api_list_collections(request: Request):
    """Legacy list collections endpoint."""
    client: httpx.AsyncClient = request.app.state.http_client
    rag_url = request.app.state.rag_engine_url
    resp = await client.get(f"{rag_url}/collections")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)


@router.post("/api/collections")
async def api_create_collection(request: Request):
    """Legacy create collection endpoint."""
    client: httpx.AsyncClient = request.app.state.http_client
    rag_url = request.app.state.rag_engine_url
    data = await request.json()
    resp = await client.post(f"{rag_url}/collections", json=data)
    return JSONResponse(content=resp.json(), status_code=resp.status_code)
