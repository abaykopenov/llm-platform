"""
Chunk Model — Pydantic schema for text chunks.
"""

from typing import Optional

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    text: str = Field(..., description="Chunk text content")
    index: int = Field(0, description="Chunk index in the source document")
    source: str = Field("", description="Source filename")
    file_id: str = Field("", description="Parent file ID")
    score: float = Field(0.0, description="Relevance score (0-1)")


class QueryRequest(BaseModel):
    text: str = Field(..., description="Query text")
    collection: Optional[str] = Field(None, description="Collection to search")
    top_k: int = Field(5, ge=1, le=50, description="Number of results")
    file_ids: Optional[list] = Field(None, description="Filter by file IDs")


class QueryResponse(BaseModel):
    results: list = Field(default_factory=list, description="List of matching chunks")
