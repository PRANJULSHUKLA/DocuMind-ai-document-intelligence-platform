import asyncio

from app.agents.document_intelligence import (
    DocumentIntelligenceAgent,
)
from app.agents.risk_engine import RiskEngine

from app.schemas.document_analysis import DocumentAnalysis
from app.services.document_access import get_ready_document


class DocumentAnalysisService:

    def __init__(self):

        self.agent = DocumentIntelligenceAgent()
        self.risk_engine = RiskEngine()

    async def analyze(
        self,
        file_id: str,
        workspace_id: str,
        analysis_type: str = "contract",
    ) -> DocumentAnalysis:

        # ----------------------------------------------
        # Authorize workspace ownership and require completed processing.
        # ----------------------------------------------

        document = await get_ready_document(file_id, workspace_id)

        # ----------------------------------------------
        # Extract Markdown
        # ----------------------------------------------

        markdown = document.get(
            "markdown",
            ""
        )

        if not markdown.strip():

            raise RuntimeError(
                "Processed document contains no extracted text."
            )

        # ----------------------------------------------
        # Stage 1 — AI Document Intelligence
        # ----------------------------------------------

        analysis = await asyncio.to_thread(
            self.agent.analyze,
            document=markdown,
            analysis_type=analysis_type,
        )

        # ----------------------------------------------
        # Stage 2 — Hybrid Risk Analysis
        # ----------------------------------------------

        analysis.risks = self.risk_engine.analyze(
            analysis=analysis,
            document=markdown,
        )

        # ----------------------------------------------
        # Return final structured analysis
        # ----------------------------------------------

        return analysis
