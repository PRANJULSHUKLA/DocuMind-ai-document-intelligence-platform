from app.constants.rag import RAGConfig


class ContextBuilder:

    @staticmethod
    def build(chunks: list[dict]) -> str:
        return ContextBuilder.build_with_sources(chunks)[0]

    @staticmethod
    def build_with_sources(chunks: list[dict]) -> tuple[str, list[dict]]:
        """Apply the budget before returning the exact evidence used for sources."""
        blocks, included = [], []
        budget = int(RAGConfig.MAX_CONTEXT_LENGTH)
        used = 0
        for chunk in chunks[:max(1, int(RAGConfig.MAX_CONTEXT_CHUNKS))]:
            text = str(chunk.get("text") or "").strip()
            if not text:
                continue
            header = (
                f"[SOURCE]\nDocument: {chunk.get('filename') or 'Unknown document'}\n"
                f"Page: {chunk.get('page_number')}\nChunk: {chunk.get('chunk_index')}\n"
                f"Relevance Score: {chunk.get('score', 0.0)}\n\n[CONTENT]\n"
            )
            footer = "\n[END SOURCE]"
            separator = 2 if blocks else 0
            if budget > 0:
                remaining = budget - used - separator - len(header) - len(footer)
                if remaining <= 0:
                    continue
                text = text[:remaining].rstrip()
            if not text:
                continue
            block = header + text + footer
            blocks.append(block)
            included.append({**chunk, "text": text})
            used += separator + len(block)
        return "\n\n".join(blocks), included
