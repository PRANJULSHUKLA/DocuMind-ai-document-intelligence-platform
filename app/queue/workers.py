
import asyncio
import logging
import time
from pathlib import Path

from bson import ObjectId
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


def process_file(file_id: str, file_path: str) -> None:
    """
    RQ entry point.

    The upload endpoint creates the MongoDB record and queues this
    function with (file_id, file_path).
    """
    _WORKER_LOOP.run_until_complete(
        _process_file_async(file_id, file_path)
    )


async def _process_file_async(
    file_id: str,
    file_path: str,
) -> None:
    start_time = time.perf_counter()
    object_id = ObjectId(file_id)
    source_path = Path(file_path).resolve()
    filename = source_path.name
    temporary_images = []
    pages = []

    try:
        if not source_path.is_file():
            raise FileNotFoundError(
                f"Uploaded PDF does not exist: {source_path}"
            )

        if source_path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF files can be processed.")

        await files_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": FileStatus.PROCESSING,
                    "processing_error": None,
                }
            },
        )

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
            {"_id": object_id},
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
                f"{source_path}_page_{index}.jpg"
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
            {"_id": object_id},
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
            {"_id": object_id},
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

        await files_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "status": FileStatus.COMPLETED,
                    "markdown": full_markdown,
                    "total_pages": len(page_markdowns),
                    "total_chunks": len(page_chunks),
                    "processing_time": processing_time,
                    "processing_error": None,
                }
            },
        )

        logger.info(
            "Document %s completed: %s pages, %s chunks, %.2f seconds",
            file_id,
            len(page_markdowns),
            len(page_chunks),
            processing_time,
        )

    except Exception as exc:
        logger.exception(
            "Document processing failed for %s",
            file_id,
        )

        try:
            await files_collection.update_one(
                {"_id": object_id},
                {
                    "$set": {
                        "status": FileStatus.FAILED,
                        "processing_error": (
                            f"{type(exc).__name__}: {exc}"
                        )[:1000],
                    }
                },
            )
        except Exception:
            logger.exception(
                "Could not update failure status for %s",
                file_id,
            )

        # Keep the exception visible to RQ so the job is recorded as failed.
        raise

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
                    "Could not remove temporary image %s",
                    image_path,
                )
