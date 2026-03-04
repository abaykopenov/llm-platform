"""
Vector Store — Interface to ChromaDB for vector storage and retrieval.
"""

from typing import List, Dict, Optional

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:
    chromadb = None


class VectorStore:
    """ChromaDB-backed vector store."""

    def __init__(self, chromadb_url: str = "http://chromadb:8400"):
        if chromadb is None:
            raise ImportError("chromadb is required: pip install chromadb")

        # Parse host and port from URL
        url = chromadb_url.rstrip("/")
        if "://" in url:
            url = url.split("://", 1)[1]
        parts = url.split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 8000

        self.client = chromadb.HttpClient(host=host, port=port)
        self._collections_cache = {}

    def _get_collection(self, name: str):
        """Get or create a ChromaDB collection."""
        if name not in self._collections_cache:
            self._collections_cache[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections_cache[name]

    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict],
        ids: List[str],
    ):
        """Add documents with embeddings to a collection."""
        collection = self._get_collection(collection_name)
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def query(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict] = None,
    ) -> List[Dict]:
        """Query a collection for similar documents."""
        collection = self._get_collection(collection_name)

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
        }
        if where:
            kwargs["where"] = where

        try:
            results = collection.query(**kwargs)
        except Exception:
            return []

        items = []
        if results and results.get("documents"):
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, dists):
                items.append({
                    "text": doc,
                    "source": meta.get("source", ""),
                    "file_id": meta.get("file_id", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": round(1.0 - dist, 4),  # cosine similarity
                })

        return items

    def delete_by_file_id(self, collection_name: str, file_id: str):
        """Delete all vectors belonging to a file."""
        collection = self._get_collection(collection_name)
        try:
            collection.delete(where={"file_id": file_id})
        except Exception:
            pass

    def list_collections(self) -> List[str]:
        """List all collection names."""
        try:
            collections = self.client.list_collections()
            return [c.name for c in collections]
        except Exception:
            return []

    def create_collection(self, name: str):
        """Create a new collection."""
        self._get_collection(name)
