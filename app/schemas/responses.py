from pydantic import BaseModel, Field
from datetime import datetime


class FileMetadataResponse(BaseModel):
    id: str = Field(alias="_id")
    filename: str
    status: str
    document_type: str = "general"
    language: str = "unknown"
    total_pages: int = 0
    total_chunks: int = 0
    processing_time: float = 0.0
    created_at: datetime | None = None
    processing_version: str = "1.0"


class Source(BaseModel):
    file_id: str | None = None
    source_id: str | None = None
    processing_run_id: str | None = None
    content_sha256: str | None = None
    excerpt: str | None = None


    filename: str | None = Field(
        default=None,
        description="Source document filename",
    )

    page_number: int | None = Field(
        default=None,
        description="Page number containing the retrieved content",
    )

    chunk_index: int = Field(
        ...,
        description="Chunk used to generate the answer",
    )

    score: float = Field(
        ...,
        description="Vector similarity score of the retrieved chunk",
    )


class ChatResponse(BaseModel):

    answer: str = Field(
        ...,
        description="Grounded answer generated from the uploaded document",
    )

    sources: list[Source] = Field(
        default_factory=list,
        description="Document pages and chunks used to generate the answer",
    )

    retrieval_time_ms: float = Field(
        ...,
        description="Time spent retrieving relevant document chunks",
    )

    generation_time_ms: float = Field(
        ...,
        description="Time spent generating the answer",
    )

    total_time_ms: float = Field(
        ...,
        description="Total RAG pipeline execution time",
    )
