
import os
import random
import time

from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing. Set it in the backend .env file."
    )


def _normalize_model(value: str) -> str:
    return value.strip().removeprefix("models/")


MODEL_NAME = _normalize_model(
    os.getenv("MODEL_NAME", "gemini-flash-latest")
)

VISION_MODEL = _normalize_model(
    os.getenv("VISION_MODEL", MODEL_NAME)
)

WORKFLOW_MODEL = _normalize_model(
    os.getenv("WORKFLOW_MODEL", MODEL_NAME)
)

EMBEDDING_MODEL = _normalize_model(
    os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
)

FALLBACK_MODELS = [
    _normalize_model(model)
    for model in os.getenv("GEMINI_FALLBACK_MODELS", "").split(",")
    if model.strip()
]

MAX_RETRIES = max(
    0,
    int(os.getenv("GEMINI_MAX_RETRIES", "2")),
)

client = genai.Client(api_key=API_KEY)


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, APIError):
        code = getattr(error, "code", None)
        if code in {429, 500, 502, 503, 504}:
            return True

    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "429",
            "500",
            "502",
            "503",
            "504",
            "resource exhausted",
            "temporarily unavailable",
            "service unavailable",
            "deadline exceeded",
        )
    )


def generate_content_with_fallback(
    *,
    model: str,
    contents,
    config=None,
):
    """
    Generate content using the requested model.

    Retries temporary failures, then tries explicitly configured fallback
    models. Authentication, invalid-model, and other non-retryable errors
    are raised rather than hidden.
    """
    models_to_try = []

    for candidate in [model, *FALLBACK_MODELS]:
        normalized = _normalize_model(candidate)
        if normalized and normalized not in models_to_try:
            models_to_try.append(normalized)

    if not models_to_try:
        raise RuntimeError("No Gemini generation model is configured.")

    last_error = None

    for candidate in models_to_try:
        for attempt in range(MAX_RETRIES + 1):
            try:
                return client.models.generate_content(
                    model=candidate,
                    contents=contents,
                    config=config,
                )
            except Exception as error:
                last_error = error
                print(
                    f"[GEMINI DEBUG] model={candidate}, "
                    f"attempt={attempt + 1}/{MAX_RETRIES + 1}, "
                    f"error_type={type(error).__name__}, "
                    f"error={error}",
                    flush=True,
                )

                if not _is_retryable(error):
                    raise

                if attempt < MAX_RETRIES:
                    delay = min(2 ** attempt + random.random(), 8)
                    time.sleep(delay)

        # Only continue to the next model after retryable failures
        # have exhausted the retry budget for this model.

    raise RuntimeError(
        "Gemini generation failed for all configured models. "
        "Check model availability, API quota, and backend logs."
    ) from last_error
