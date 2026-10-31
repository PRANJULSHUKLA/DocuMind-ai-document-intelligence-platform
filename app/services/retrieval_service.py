import asyncio

from app.constants.rag import RAGConfig

from app.db.collections.chunks import chunks_collection

from app.llm.embeddings import generate_embedding
from app.services.document_access import get_ready_document


class RetrievalService:

    async def retrieve_chunks(
        self,
        file_id: str,
        question: str,
        workspace_id: str,
        limit: int = RAGConfig.TOP_K,
        query_embedding: list | None = None,
    ) -> list[dict]:

        # --------------------------------------------------
        # Generate Query Embedding
        # --------------------------------------------------

        document = await get_ready_document(file_id, workspace_id)
        if query_embedding is None:
            query_embedding = await asyncio.to_thread(generate_embedding, question)
        filters = {"file_id": file_id, "workspace_id": workspace_id}
        if document.get("active_processing_run_id"):
            filters["processing_run_id"] = document["active_processing_run_id"]

        # --------------------------------------------------
        # Atlas Vector Search
        # --------------------------------------------------

        pipeline = [
            {
                "$vectorSearch": {
                    "index": RAGConfig.VECTOR_INDEX_NAME,
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": RAGConfig.VECTOR_SEARCH_CANDIDATES,
                    "limit": limit,
                    "filter": filters,
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "processing_run_id": 1,
                    "content_sha256": 1,
                    "file_id": 1,
                    "filename": 1,
                    "page_number": 1,
                    "chunk_index": 1,
                    "chunk_length": 1,
                    "document_type": 1,
                    "language": 1,
                    "text": 1,
                    "score": {
                        "$meta": "vectorSearchScore"
                    },
                }
            },
            {"$match": {"score": {"$gte": RAGConfig.MIN_SIMILARITY_SCORE}}},
        ]

        # --------------------------------------------------
        # Execute Pipeline
        # --------------------------------------------------

        cursor = await chunks_collection.aggregate(pipeline)

        documents = await cursor.to_list(length=limit)

        # --------------------------------------------------
        # Format Response
        # --------------------------------------------------

        return [
            {
                "_id": document.get("_id"),
                "processing_run_id": document.get("processing_run_id"),
                "content_sha256": document.get("content_sha256"),
                "file_id": document.get("file_id"),
                "filename": document.get("filename"),
                "page_number": document.get("page_number"),
                "chunk_index": document.get("chunk_index"),
                "chunk_length": document.get("chunk_length"),
                "document_type": document.get("document_type"),
                "language": document.get("language"),
                "text": document.get("text"),
                "score": round(document.get("score", 0.0), 4),
            }
            for document in documents
        ]
