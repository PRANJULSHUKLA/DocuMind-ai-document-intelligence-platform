
import os

from dotenv import load_dotenv

load_dotenv()


class RAGConfig:
    # Retrieval
    TOP_K = 4
    MAX_CONTEXT_CHUNKS = 4
    MIN_SIMILARITY_SCORE = 0.65

    # MongoDB Atlas Vector Search
    VECTOR_INDEX_NAME = "vector_index"
    VECTOR_SEARCH_CANDIDATES = 50

    # Shared generation limit.
    # Keep this high because structured workflow generation also uses it.
    MAX_OUTPUT_TOKENS = 8192

    # Chat-only limit. This must not affect workflow or document analysis.
    CHAT_MAX_OUTPUT_TOKENS = 2048

    # Generation settings
    TEMPERATURE = 0.2

    # Context limit in characters
    MAX_CONTEXT_LENGTH = 8000

    # Workflow model
    WORKFLOW_MODEL = os.getenv(
        "WORKFLOW_MODEL",
        os.getenv("MODEL_NAME", "gemini-3.8-flash"),
    ).removeprefix("models/")
