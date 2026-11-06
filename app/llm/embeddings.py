
from app.llm.gemini import client, EMBEDDING_MODEL
from app.services import pilot_budget


def generate_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Cannot generate an embedding for empty text.")

    pilot_budget.reserve('model')
    try:
        response = client.models.embed_content(model=EMBEDDING_MODEL, contents=text)
    except Exception as error:
        if pilot_budget.enabled() and getattr(error, 'code', None) == 429:
            pilot_budget.exhausted()
        raise

    if not response.embeddings:
        raise RuntimeError("Gemini returned no embeddings.")

    values = response.embeddings[0].values

    if not values:
        raise RuntimeError("Gemini returned an empty embedding vector.")

    return [float(value) for value in values]
