"""
RAG Engine Routes — File ingestion, query, management endpoints.
"""

import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse

from pipeline.file_parser import parse_file, get_supported_extensions
from pipeline.chunker import chunk_text
from pipeline.embedder import get_embeddings
from pipeline.retriever import retrieve_chunks
from storage.vector_store import VectorStore
from storage.file_store import FileStore

router = APIRouter()


@router.post("/ingest")
async def ingest_file(
    request: Request,
    file: UploadFile = File(...),
    collection: Optional[str] = Form(None),
):
    """Ingest a file: parse → chunk → embed → store in ChromaDB."""
    vector_store: VectorStore = request.app.state.vector_store
    file_store: FileStore = request.app.state.file_store
    model = request.app.state.embedding_model
    inference_url = request.app.state.inference_url
    chunk_size = request.app.state.chunk_size
    chunk_overlap = request.app.state.chunk_overlap
    col_name = collection or request.app.state.default_collection

    # Save uploaded file to temp
    ext = os.path.splitext(file.filename or "")[1].lower()
    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 1. Parse file to text
        text = parse_file(tmp_path)
        if not text or not text.strip():
            return JSONResponse(
                content={"error": "Could not extract text from file"},
                status_code=400,
            )

        # 2. Chunk text
        chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if not chunks:
            return JSONResponse(
                content={"error": "No chunks produced from file"},
                status_code=400,
            )

        # 3. Get embeddings
        texts = [c["text"] for c in chunks]
        embeddings = await get_embeddings(texts, model, inference_url)

        # 4. Store file metadata
        file_meta = file_store.save_file(
            file_data=content,
            original_name=file.filename or "unknown",
            collection=col_name,
            chunks_count=len(chunks),
        )

        # 5. Store vectors in ChromaDB
        vector_store.add_documents(
            collection_name=col_name,
            documents=texts,
            embeddings=embeddings,
            metadatas=[
                {
                    "file_id": file_meta["file_id"],
                    "source": file.filename or "unknown",
                    "chunk_index": c["index"],
                }
                for c in chunks
            ],
            ids=[f"{file_meta['file_id']}_chunk_{c['index']}" for c in chunks],
        )

        return {
            "id": file_meta["file_id"],
            "filename": file.filename,
            "chunks_count": len(chunks),
            "collection": col_name,
            "status": "processed",
            **file_meta,
        }

    except Exception as e:
        return JSONResponse(
            content={"error": f"Ingestion failed: {str(e)}"},
            status_code=500,
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/query")
async def query_documents(request: Request):
    """Query the vector store for relevant chunks."""
    data = await request.json()
    text = data.get("text", "")
    top_k = data.get("top_k", 5)
    collection = data.get("collection", request.app.state.default_collection)
    file_ids = data.get("file_ids")

    if not text:
        return JSONResponse(
            content={"error": "Query text is required"},
            status_code=400,
        )

    vector_store: VectorStore = request.app.state.vector_store
    model = request.app.state.embedding_model
    inference_url = request.app.state.inference_url

    try:
        results = await retrieve_chunks(
            text=text,
            collection_name=collection,
            top_k=top_k,
            file_ids=file_ids,
            vector_store=vector_store,
            embedding_model=model,
            inference_url=inference_url,
        )
        return {"results": results}
    except Exception as e:
        return JSONResponse(
            content={"error": f"Query failed: {str(e)}"},
            status_code=500,
        )


@router.get("/files")
async def list_files(
    request: Request,
    collection: Optional[str] = None,
):
    """List all ingested files."""
    file_store: FileStore = request.app.state.file_store
    files = file_store.list_files(collection=collection)
    return files


@router.get("/files/{file_id}")
async def get_file(file_id: str, request: Request):
    """Get file info by ID."""
    file_store: FileStore = request.app.state.file_store
    info = file_store.get_file(file_id)
    if info is None:
        return JSONResponse(content={"error": "File not found"}, status_code=404)
    return info


@router.delete("/files/{file_id}")
async def delete_file(file_id: str, request: Request):
    """Delete a file and its vectors from ChromaDB."""
    file_store: FileStore = request.app.state.file_store
    vector_store: VectorStore = request.app.state.vector_store

    # Delete from file store
    file_info = file_store.get_file(file_id)
    if file_info is None:
        return JSONResponse(content={"error": "File not found"}, status_code=404)

    collection = file_info.get("collection", request.app.state.default_collection)

    # Delete vectors from ChromaDB
    vector_store.delete_by_file_id(collection, file_id)

    # Delete file metadata
    file_store.delete_file(file_id)

    return {"ok": True, "deleted": file_id}


@router.get("/collections")
async def list_collections(request: Request):
    """List all collections."""
    vector_store: VectorStore = request.app.state.vector_store
    collections = vector_store.list_collections()
    if not collections:
        collections = [request.app.state.default_collection]
    return collections


@router.post("/collections")
async def create_collection(request: Request):
    """Create a new collection."""
    data = await request.json()
    name = data.get("name", "")
    if not name:
        return JSONResponse(content={"error": "Name required"}, status_code=400)

    vector_store: VectorStore = request.app.state.vector_store
    vector_store.create_collection(name)
    return {"ok": True, "name": name}
