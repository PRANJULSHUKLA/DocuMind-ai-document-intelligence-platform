from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FileSchema(BaseModel):

    filename: str

    status: str
    workspace_id: str

    document_type: Literal[
        "resume",
        "contract",
        "invoice",
        "boarding_pass",
        "identity",
        "research_paper",
        "general"
    ] = "general"

    language: str = "unknown"

    total_pages: int = 0

    total_chunks: int = 0

    processing_time: float = 0.0

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    processing_version: str = "1.0"
