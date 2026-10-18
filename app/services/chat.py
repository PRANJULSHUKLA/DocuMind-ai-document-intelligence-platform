from google.genai import types

from app.constants.models import GeminiModels
from app.llm.gemini import generate_content_with_fallback


class GeminiChat:
    @staticmethod
    def generate(prompt: str) -> str:
        response = generate_content_with_fallback(
            model=GeminiModels.CHAT,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4096,
            ),
        )

        return (response.text or "").strip()