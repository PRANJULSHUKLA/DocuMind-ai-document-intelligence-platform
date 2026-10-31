
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from pymongo import ReturnDocument
from pdf2image import convert_from_path

from app.constants.status import FileStatus
from app.db.collections.files import files_collection
from app.db.collections.chunks import chunks_collection
from app.llm.vision import image_to_markdown
from app.llm.embeddings import generate_embedding
from app.llm.gemini import EMBEDDING_MODEL
from app.schemas.chunk import ChunkSchema
from app.utils.chunker import create_chunks


logger = logging.getLogger("documind.worker")

# RQ calls this synchronous function for each job. Keep one event loop
# for this worker process so async MongoDB operations use a consistent loop.
_WORKER_LOOP = asyncio.new_event_loop()


def process_file(file_id: str, file_path: str, attempt: int | None = None) -> None:
    """
    RQ entry point.

    The upload endpoint creates the MongoDB record and queues this
    function with (file_id, file_path).
    """
    _WORKER_LOOP.run_until_complete(
        _process_file_async(file_id, file_path, attempt)
    )


async def _process_file_async(
    file_id: str,
    file_path: str,
    attempt: int | None = None,
) -> None:
    start_time = time.perf_counter()
    object_id = ObjectId(file_id)
    source_path = Path(file_path).resolve()
    filename = source_path.name
    temporary_images = []
    pages = []
    run_id = uuid4().hex
    owned = {"_id": object_id, "processing_run_id": run_id}
    if attempt is not None:
        owned["enqueue_attempt"] = attempt
    claimed = False

    try:
        # A bounded lease prevents duplicate jobs from ingesting the same file.
        # It outlives the RQ timeout (1200s), then permits crash recovery.
        now = datetime.now(timezone.utc)
        document = await files_collection.find_one_and_update(
            {
                "_id": object_id,
                "status": {"$ne": FileStatus.COMPLETED},
                # Existing two-argument jobs still work for legacy records. A
                # delayed job from a superseded attempt cannot claim a new run.
                "enqueue_attempt": attempt if attempt is not None else {"$exists": False},
                "$or": [
                    {"processing_lease_until": {"$exists": False}},
                    {"processing_lease_until": {"$lte": now}},
                ],
            },
            {
                "$set": {
                    "status": FileStatus.PROCESSING,
                    "processing_error": None,
                    "enqueue_state": "confirmed",
                    "processing_run_id": run_id,
                    "processing_lease_until": now + timedelta(seconds=1260),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            existing = await files_collection.find_one({"_id": object_id})
            if existing is None:
                raise FileNotFoundError("Document record no longer exists.")
            logger.info("Skipping completed or already claimed document %s", file_id)
            return
        claimed = True
        workspace_id = document.get("workspace_id")
        if not workspace_id:
            raise ValueError("Document has no workspace assignment.")
        if not source_path.is_file():
            raise FileNotFoundError("Uploaded PDF is missing.")
        if source_path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF files can be processed.")

        logger.info("Starting document processing: %s", file_id)

        # -----------------------------------------------------
        # Stage 1: Convert the PDF into images
        # -----------------------------------------------------
        pages = convert_from_path(
            str(source_path),
            dpi=150,
            thread_count=2,
        )

        if not pages:
            raise ValueError("The PDF contains no readable pages.")

        logger.info(
            "PDF conversion complete: %s pages",
            len(pages),
        )

        await files_collection.update_one(
            owned,
            {
                "$set": {
                    "status": FileStatus.EXTRACTING_TEXT,
                    "total_pages": len(pages),
                }
            },
        )

        # -----------------------------------------------------
        # Stage 2: OCR each page with Gemini Vision
        # -----------------------------------------------------
        page_markdowns = []

        for index, page in enumerate(pages):
            page_number = index + 1

            image_path = Path(
                f"{source_path}_page_{run_id}_{index}.jpg"
            )
            temporary_images.append(image_path)

            page.save(str(image_path), format="JPEG")

            try:
                markdown = image_to_markdown(str(image_path))
            finally:
                # Release the in-memory image after OCR.
                page.close()

            markdown = (markdown or "").strip()

            if not markdown:
                logger.warning(
                    "OCR returned empty text for page %s",
                    page_number,
                )

            page_markdowns.append(
                {
                    "page_number": page_number,
                    "markdown": markdown,
                }
            )

            logger.info(
                "OCR completed for page %s/%s",
                page_number,
                len(pages),
            )

        full_markdown = "\n\n".join(
            page["markdown"] for page in page_markdowns
            if page["markdown"]
        ).strip()

        if not full_markdown:
            raise ValueError(
                "No text could be extracted from this PDF."
            )

        # -----------------------------------------------------
        # Stage 3: Chunk the extracted text
        # -----------------------------------------------------
        await files_collection.update_one(
            owned,
            {
                "$set": {
                    "status": FileStatus.CREATING_KNOWLEDGE_BASE,
                    "markdown": full_markdown,
                }
            },
        )

        page_chunks = []

        for page_data in page_markdowns:
            page_number = page_data["page_number"]
            markdown = page_data["markdown"]

            if not markdown:
                continue

            chunks = create_chunks(markdown)

            for chunk in chunks:
                text = str(chunk).strip()

                if text:
                    page_chunks.append(
                        {
                            "page_number": page_number,
                            "text": text,
                        }
                    )

        if not page_chunks:
            raise ValueError(
                "Text was extracted, but no usable chunks were created."
            )

        logger.info(
            "Created %s chunks for document %s",
            len(page_chunks),
            file_id,
        )

        # -----------------------------------------------------
        # Stage 4: Generate embeddings and save chunks
        # -----------------------------------------------------
        await files_collection.update_one(
            owned,
            {
                "$set": {
                    "status": FileStatus.CREATING_CHUNK_EMBEDDINGS,
                    "total_chunks": len(page_chunks),
                }
            },
        )

        for index, chunk_data in enumerate(page_chunks):
            text = chunk_data["text"]
            page_number = chunk_data["page_number"]

            embedding = generate_embedding(text)

            if not embedding:
                raise RuntimeError(
                    f"Embedding generation returned an empty vector "
                    f"for chunk {index}."
                )

            chunk_document = ChunkSchema(
                file_id=file_id,
                workspace_id=workspace_id,
                filename=filename,
                page_number=page_number,
                chunk_index=index,
                chunk_length=len(text),
                document_type="general",
                language="unknown",
                embedding_model=EMBEDDING_MODEL,
                embedding_dimension=len(embedding),
                text=text,
                embedding=embedding,
                processing_run_id=run_id,
            )

            await chunks_collection.insert_one(
                chunk_document.model_dump()
            )

            logger.info(
                "Saved embedding for chunk %s/%s",
                index + 1,
                len(page_chunks),
            )

        # -----------------------------------------------------
        # Stage 5: Mark the document completed
        # -----------------------------------------------------
        processing_time = round(
            time.perf_counter() - start_time,
            2,
        )

        published = await files_collection.update_one(
            owned,
            {
                "$set": {
                    "status": FileStatus.COMPLETED,
                    "markdown": full_markdown,
                    "total_pages": len(page_markdowns),
                    "total_chunks": len(page_chunks),
                    "processing_time": processing_time,
                    "processing_error": None,
                    "active_processing_run_id": run_id,
                },
                "$unset": {"processing_lease_until": ""},
            },
        )
        if not published.matched_count:
            raise RuntimeError("Document processing lease was superseded.")

        # Publication above is atomic. Retrieval only sees the published run.
        try:
            await chunks_collection.delete_many({
                "file_id": file_id, "processing_run_id": {"$ne": run_id},
            })
        except Exception as cleanup_error:
            logger.warning("Old chunk cleanup failed: %s", type(cleanup_error).__name__)

        logger.info(
            "Document %s completed: %s pages, %s chunks, %.2f seconds",
            file_id,
            len(page_markdowns),
            len(page_chunks),
            processing_time,
        )

    except Exception as exc:
        logger.error("Document processing failed: file_id=%s error_type=%s", file_id, type(exc).__name__)

        if claimed:
            try:
                await chunks_collection.delete_many({"file_id": file_id, "processing_run_id": run_id})
            except Exception as cleanup_error:
                logger.warning("Staged chunk cleanup failed: %s", type(cleanup_error).__name__)
            try:
                await files_collection.update_one(
                    owned,
                    {
                        "$set": {
                            "status": FileStatus.FAILED,
                            "processing_error": "Document processing failed. Please retry or contact support.",
                        },
                        "$unset": {"processing_lease_until": ""},
                    },
                )
            except Exception as update_error:
                logger.error("Could not update failure status: file_id=%s error_type=%s", file_id, type(update_error).__name__)

        # Keep the exception visible to RQ so the job is recorded as failed.
        raise RuntimeError("Document processing failed. Check worker diagnostics.") from None

    finally:
        # Some images may not have reached the OCR loop if conversion
        # or processing failed early. Close any remaining image handles.
        for page in pages:
            try:
                page.close()
            except Exception:
                pass

        for image_path in temporary_images:
            try:
                image_path.unlink(missing_ok=True)
            except Exception:
                logger.warning(
                    "Could not remove temporary image for document %s",
                    file_id,
                )
