"""
Document Model — Pydantic schema for ingested documents.
"""

from typing import Optional, List

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    file_id: str = Field(..., description="Unique file identifier")
    original_name: str = Field(..., description="Original filename")
    collection: str = Field("general", description="Collection name")
    chunks_count: int = Field(0, description="Number of chunks")
    size_bytes: int = Field(0, description="File size in bytes")
    ingested_at: str = Field("", description="Ingestion timestamp")


class IngestRequest(BaseModel):
    collection: Optional[str] = Field(None, description="Target collection")


class IngestResponse(BaseModel):
    id: str = Field(..., description="File ID")
    filename: str = Field(..., description="Original filename")
    chunks_count: int = Field(0)
    collection: str = Field("general")
    status: str = Field("processed")
