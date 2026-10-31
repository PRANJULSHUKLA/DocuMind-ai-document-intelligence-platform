from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChunkSchema(BaseModel):
    # Document information
    file_id: str
    workspace_id: str
    filename: str
    page_number: int
    chunk_index: int

    # Chunk metadata
    chunk_length: int

    document_type: Literal[
        "resume",
        "contract",
        "invoice",
        "boarding_pass",
        "identity",
        "research_paper",
        "general",
    ] = "general"

    language: str = "unknown"

    # Embedding metadata
    embedding_model: str = "gemini-embedding-001"
    embedding_dimension: int

    # Content
    text: str
    embedding: list[float]

    # Audit
    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    processing_version: str = "1.0"
    processing_run_id: str | None = None
