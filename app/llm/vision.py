
import base64
import time

import requests

from app.llm.gemini import API_KEY, VISION_MODEL

PROMPT = """
You are an intelligent OCR engine.

Extract all visible text from this document page.

Rules:
- Preserve headings, tables, lists, and meaningful formatting.
- Do not summarize or interpret the page.
- Return only Markdown.
"""


def image_to_markdown(
    image_path: str,
    max_retries: int = 3,
) -> str:
    with open(image_path, "rb") as image_file:
        image_base64 = base64.b64encode(
            image_file.read()
        ).decode("ascii")

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{VISION_MODEL}:generateContent"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_base64,
                        }
                    },
                ]
            }
        ]
    }

    headers = {
        "x-goog-api-key": API_KEY,
        "Content-Type": "application/json",
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=120,
            )

            if response.status_code in {429, 500, 502, 503, 504}:
                if attempt < max_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue

            if not response.ok:
                raise RuntimeError(
                    f"Gemini vision API returned HTTP {response.status_code}: "
                    f"{response.text[:2000]}"
                )
            data = response.json()

            candidates = data.get("candidates") or []
            if not candidates:
                raise RuntimeError(
                    "Gemini Vision returned no candidates."
                )

            parts = (
                candidates[0]
                .get("content", {})
                .get("parts", [])
            )

            extracted_text = "\n".join(
                part["text"]
                for part in parts
                if isinstance(part, dict) and part.get("text")
            ).strip()

            if not extracted_text:
                raise RuntimeError(
                    "Gemini Vision returned empty OCR output."
                )

            return extracted_text

        except requests.exceptions.RequestException:
            if attempt >= max_retries:
                raise
            time.sleep(min(2 ** attempt, 8))

    raise RuntimeError(
        "Gemini Vision failed after multiple attempts."
    )
