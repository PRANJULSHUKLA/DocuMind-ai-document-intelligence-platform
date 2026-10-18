
from app.llm.gemini import client, EMBEDDING_MODEL


def generate_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Cannot generate an embedding for empty text.")

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
    )

    if not response.embeddings:
        raise RuntimeError("Gemini returned no embeddings.")

    values = response.embeddings[0].values

    if not values:
        raise RuntimeError("Gemini returned an empty embedding vector.")

    return [float(value) for value in values]
