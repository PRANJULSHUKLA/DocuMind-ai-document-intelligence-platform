from google.genai import types

from app.constants.agent import AgentConfig
from app.constants.models import GeminiModels

from app.llm.gemini import generate_content_with_fallback

from app.prompts.document_analysis import (
    DocumentAnalysisPrompt,
)

from app.schemas.document_analysis import (
    DocumentAnalysis,
)


class DocumentIntelligenceAgent:

    def __init__(self):

        self.model = GeminiModels.CHAT

    def analyze(
        self,
        document: str,
        analysis_type: str = AgentConfig.CONTRACT_ANALYSIS,
    ) -> DocumentAnalysis:

        # ==================================================
        # 1. Validate input
        # ==================================================

        if not document.strip():

            raise ValueError(
                "Document content is empty."
            )

        # ==================================================
        # 2. Protect against excessively large input
        # ==================================================

        document = document[
            :AgentConfig.MAX_DOCUMENT_LENGTH
        ]

        # ==================================================
        # 3. Build analysis prompt
        # ==================================================

        prompt = DocumentAnalysisPrompt.build(
            document=document,
            analysis_type=analysis_type,
        )

        # ==================================================
        # 4. Gemini structured generation
        # ==================================================

        response = generate_content_with_fallback(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=AgentConfig.TEMPERATURE,
                max_output_tokens=AgentConfig.MAX_OUTPUT_TOKENS,

                response_mime_type="application/json",

                response_schema=DocumentAnalysis,
            ),
        )

        # ==================================================
        # 5. Validate response
        # ==================================================

        if not response.text:

            raise RuntimeError(
                "Gemini returned an empty response."
            )

        # The Google GenAI SDK can parse a Pydantic
        # response schema directly into response.parsed.
        if response.parsed is not None:

            if isinstance(
                response.parsed,
                DocumentAnalysis,
            ):

                return response.parsed

            return DocumentAnalysis.model_validate(
                response.parsed
            )

        # ==================================================
        # 6. Fallback parsing
        # ==================================================

        try:

            return DocumentAnalysis.model_validate_json(
                response.text
            )

        except Exception as e:

            raise RuntimeError(
                "Gemini returned an incomplete or invalid "
                "structured response."
            ) from e