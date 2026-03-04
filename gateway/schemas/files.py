"""
File Schemas — Pydantic models for file operations.
"""

from typing import Optional, List

from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    id: str = Field(..., description="Unique file ID")
    filename: str = Field(..., description="Original filename")
    bytes: int = Field(0, description="File size in bytes")
    purpose: str = Field("rag", description="File purpose")
    status: str = Field("processed", description="Processing status")
    chunks_count: int = Field(0, description="Number of chunks created")
    collection: str = Field("general", description="Collection name")


class FileInfo(BaseModel):
    file_id: str
    original_name: str
    chunks_count: int = 0
    collection: str = "general"
    ingested_at: str = ""
    size_bytes: int = 0


class FileListResponse(BaseModel):
    data: List[FileInfo] = []
    object: str = "list"
