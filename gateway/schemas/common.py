"""
Common Schemas — Shared Pydantic models.
"""

from typing import List, Optional, Union, Dict, Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: Dict[str, str] = Field(
        ...,
        description="Error object with 'message' and 'type'",
    )


class HealthStatus(BaseModel):
    status: str = Field(..., description="healthy, degraded, or unhealthy")
    timestamp: float = 0
    services: Dict[str, Any] = {}


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "llm-platform"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo] = []


class EmbeddingRequest(BaseModel):
    model: Optional[str] = Field(None, description="Embedding model to use")
    input: Union[str, List[str]] = Field(..., description="Text(s) to embed")


class EmbeddingData(BaseModel):
    object: str = "embedding"
    embedding: List[float] = []
    index: int = 0


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData] = []
    model: str = ""
    usage: Dict[str, int] = {"prompt_tokens": 0, "total_tokens": 0}
