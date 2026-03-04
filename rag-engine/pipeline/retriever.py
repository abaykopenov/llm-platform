"""
Retriever — Search for relevant chunks in the vector store.
"""

from typing import List, Dict, Optional

from pipeline.embedder import get_embeddings
from storage.vector_store import VectorStore


async def retrieve_chunks(
    text: str,
    collection_name: str,
    top_k: int = 5,
    file_ids: Optional[List[str]] = None,
    vector_store: VectorStore = None,
    embedding_model: str = "bge-m3",
    inference_url: str = "http://inference:8300",
) -> List[Dict]:
    """
    Retrieve relevant chunks for a query.
    1. Embed the query text
    2. Search ChromaDB for similar vectors
    3. Return top-k results with text, source, score
    """
    # 1. Get query embedding
    embeddings = await get_embeddings([text], embedding_model, inference_url)
    if not embeddings:
        return []

    query_embedding = embeddings[0]

    # 2. Build where filter for file_ids
    where_filter = None
    if file_ids:
        if len(file_ids) == 1:
            where_filter = {"file_id": file_ids[0]}
        else:
            where_filter = {"file_id": {"$in": file_ids}}

    # 3. Query vector store
    results = vector_store.query(
        collection_name=collection_name,
        query_embedding=query_embedding,
        top_k=top_k,
        where=where_filter,
    )

    return results
