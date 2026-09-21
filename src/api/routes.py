"""FastAPI route definitions."""

import json
import hashlib
import asyncio
import uuid
from fastapi import APIRouter, WebSocket, UploadFile, File, Form, HTTPException, BackgroundTasks
import structlog

from src.api.schemas import (
    ConnectRequest,
    ConnectResponse,
    GoogleAuthRequest,
    GoogleAuthResponse,
    HealthResponse,
    FileUploadResponse,
    DocumentListResponse,
    DocumentDeleteResponse,
    ChatRequest,
    ChatResponse,
    ApiKeyUpdateRequest,
    ApiKeyStatusResponse,
    StorageUsageResponse,
)
from src.api.websocket_handler import handle_websocket, manager
from src.database.repository import ChatRepository, DocumentRegistryRepo
from src.database.csv_tables import load_csv_to_postgres, drop_user_table
from src.rag.chunker import extract_text, chunk_document, chunk_document_hierarchical, extract_structured, chunk_structured_document
from src.rag.metadata import generate_document_summary
from src.rag.vectorstore import vectorstore, _content_hash
from src.rag.embeddings import embedder
from src.graph.answer_cache import invalidate_user_cache
from src.config.settings import settings
from qdrant_client.models import PointStruct

logger = structlog.get_logger(__name__)

router = APIRouter()

MAX_FILE_SIZE = 30 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".docx", ".md", ".csv", ".log", ".pdf"}

# Track in-progress background uploads: user_id -> {filename: status}
_upload_status: dict[str, dict[str, str]] = {}


def _file_hash(content: bytes) -> str:
    """Compute SHA256 hash of file content for deduplication."""
    return hashlib.sha256(content).hexdigest()[:16]


@router.post("/connect", response_model=ConnectResponse)
async def connect_user(req: ConnectRequest):
    """Register or reconnect a user. Returns JWT token."""
    from src.api.auth import create_token

    existed, _ = await ChatRepository.get_or_create_user(req.user_id)
    history = []
    if existed:
        history = await ChatRepository.load_history(req.user_id)

    token = create_token(req.user_id)

    return ConnectResponse(
        user_id=req.user_id,
        existing_user=existed,
        history=history,
        message="Welcome back!" if existed else "New session created.",
        token=token,
    )


# ─── Auth ────────────────────────────────────────────────────────────────────

@router.post("/auth/google", response_model=GoogleAuthResponse)
async def google_auth(req: GoogleAuthRequest):
    """
    Authenticate a user using their Google ID token from Google Identity Services.
    - Verifies the Google token signature with Google's public certs
    - Creates or retrieves the user in PostgreSQL
    - Returns our internal JWT + chat history
    """
    from src.api.auth import verify_google_token, create_token

    # Verify the Google token
    google_user = await verify_google_token(req.id_token)

    if not google_user["email_verified"]:
        raise HTTPException(status_code=401, detail="Google email not verified.")

    # Get or create user in our database (only email + name stored, no password)
    try:
        existed, user = await ChatRepository.get_or_create_google_user(
            google_id=google_user["google_id"],
            email=google_user["email"],
            display_name=google_user["name"],
            avatar_url=google_user["picture"],
        )
    except Exception as e:
        logger.error("google_user_create_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    # Load chat history if returning user
    history = []
    if existed:
        history = await ChatRepository.load_history(user.id)

    # Issue our JWT (contains user_id and email, no password)
    token = create_token(user.id, email=google_user["email"])

    logger.info("google_auth_success", user_id=user.id, email=google_user["email"], new_user=not existed)

    # Check if user already has an API key configured
    has_key, masked = await ChatRepository.get_user_api_key_status(user.id)
    is_admin = settings.is_super_admin(google_user["email"])

    return GoogleAuthResponse(
        user_id=user.id,
        email=google_user["email"],
        display_name=google_user["name"],
        avatar_url=google_user["picture"],
        existing_user=existed,
        token=token,
        history=[{"role": m["role"], "content": m["content"], "agent_name": m.get("agent_name")} for m in history],
        message="Welcome back!" if existed else "Account created successfully!",
        has_api_key=has_key,
        masked_key=masked,
        is_super_admin=is_admin,
    )


# ─── Storage Quota Endpoint ───────────────────────────────────────────────────

@router.get("/user/{user_id}/storage-usage", response_model=StorageUsageResponse)
async def get_storage_usage(user_id: str):
    """Return storage quota and usage details for a user."""
    used_bytes = await DocumentRegistryRepo.get_user_storage_bytes(user_id)
    user_obj = await ChatRepository.get_user(user_id)
    is_admin = settings.is_super_admin(user_obj.email if user_obj else None)
    quota = settings.user_storage_quota_mb

    return StorageUsageResponse(
        user_id=user_id,
        used_bytes=used_bytes,
        used_mb=round(used_bytes / (1024 * 1024), 2),
        quota_mb=quota,
        is_unlimited=(quota == 0 or is_admin),
        is_super_admin=is_admin,
    )


# ─── User API Key Management (BYOK) ──────────────────────────────────────────

@router.get("/user/{user_id}/api-key", response_model=ApiKeyStatusResponse)
async def get_user_api_key_status_endpoint(user_id: str):
    """Return user's API key status and masked preview."""
    has_key, masked = await ChatRepository.get_user_api_key_status(user_id)
    return ApiKeyStatusResponse(
        user_id=user_id,
        has_api_key=has_key,
        masked_key=masked,
        message="Active" if has_key else "No API key configured",
    )


@router.post("/user/{user_id}/api-key", response_model=ApiKeyStatusResponse)
async def save_user_api_key_endpoint(user_id: str, req: ApiKeyUpdateRequest):
    """Validate user API key with Google AI Studio, encrypt with AES/Fernet, and store in DB."""
    from src.config.security import validate_gemini_api_key, mask_api_key

    is_valid, err = validate_gemini_api_key(req.api_key)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err or "Invalid Google Gemini API key.")

    await ChatRepository.set_user_api_key(user_id, req.api_key)
    masked = mask_api_key(req.api_key)
    logger.info("byok_key_saved", user_id=user_id, masked=masked)
    return ApiKeyStatusResponse(
        user_id=user_id,
        has_api_key=True,
        masked_key=masked,
        message="API key validated and securely saved.",
    )


@router.delete("/user/{user_id}/api-key", response_model=ApiKeyStatusResponse)
async def delete_user_api_key_endpoint(user_id: str):
    """Remove user's stored API key."""
    await ChatRepository.set_user_api_key(user_id, None)
    logger.info("byok_key_deleted", user_id=user_id)
    return ApiKeyStatusResponse(
        user_id=user_id,
        has_api_key=False,
        masked_key="",
        message="API key removed.",
    )


@router.post("/auth/google/callback")
async def google_callback(credential: str = Form(...)):
    """
    Google redirects here after sign-in (ux_mode=redirect).
    Receives the credential via POST form, then redirects to Streamlit with the token.
    """
    from fastapi.responses import RedirectResponse

    # Redirect to Streamlit frontend with the credential as a query param
    redirect_url = f"http://localhost:8501/?credential={credential}"
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/auth/google/login")
async def google_login_page():
    """
    Serves a Google Sign-In page. User clicks the button here,
    Google authenticates, then redirects back to /auth/google/callback.
    """
    from fastapi.responses import HTMLResponse

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sign In - Agentic AI Chat</title>
        <script src="https://accounts.google.com/gsi/client" async defer></script>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                background: white;
                padding: 48px;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 400px;
            }}
            h1 {{ color: #333; margin-bottom: 8px; }}
            p {{ color: #666; margin-bottom: 32px; }}
            .g_id_signin {{ display: inline-block; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Agentic AI Chat</h1>
            <p>Sign in with your Google account to continue</p>

            <div id="g_id_onload"
                 data-client_id="{settings.google_client_id}"
                 data-login_uri="http://localhost:8000/auth/google/callback"
                 data-auto_prompt="false"
                 data-ux_mode="redirect">
            </div>
            <div class="g_id_signin"
                 data-type="standard"
                 data-size="large"
                 data-theme="filled_blue"
                 data-text="sign_in_with"
                 data-shape="rectangular"
                 data-logo_alignment="left"
                 data-width="300">
            </div>

            <p style="margin-top: 24px; font-size: 12px; color: #999;">
                We only store your email and name. No passwords.
            </p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.post("/upload", response_model=FileUploadResponse)
async def upload_document(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    force: bool = Form(default=False),
    is_shared: bool = Form(default=False),
    background_tasks: BackgroundTasks = None,
):
    """
    Upload a document.
    - CSV → PostgreSQL table + metadata registry
    - TXT/DOCX/MD/LOG → Background: Qdrant (semantic chunks) + metadata registry
    - is_shared=true: Stores document once under shared namespace (Super Admin only)

    Set force=true to re-upload a duplicate file.
    """
    filename = file.filename or "unknown.txt"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum 10MB.")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    # ─── Super Admin & Storage Quota Verification ───────────────────────
    if is_shared:
        user_obj = await ChatRepository.get_user(user_id)
        if not user_obj or not settings.is_super_admin(user_obj.email):
            raise HTTPException(status_code=403, detail="Only Super Admins can upload shared demo documents.")
        target_user_id = settings.shared_user_id
    else:
        target_user_id = user_id
        if settings.user_storage_quota_mb > 0:
            user_bytes = await DocumentRegistryRepo.get_user_storage_bytes(user_id)
            existing_docs = await DocumentRegistryRepo.get_all_documents(user_id)
            existing_doc = next((d for d in existing_docs if d["filename"] == filename), None)
            if existing_doc:
                user_bytes -= int(existing_doc.get("metadata", {}).get("file_size", existing_doc.get("metadata", {}).get("char_count", 0)))
            if (user_bytes + len(content)) > settings.user_storage_quota_mb * 1024 * 1024:
                used_mb = user_bytes / (1024 * 1024)
                quota_mb = settings.user_storage_quota_mb
                new_mb = len(content) / (1024 * 1024)
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Storage limit exceeded! You are using {used_mb:.1f} MB of your {quota_mb} MB quota. "
                        f"Uploading '{filename}' ({new_mb:.1f} MB) exceeds this limit. "
                        "Please delete existing documents to free up space."
                    ),
                )

    # ─── Check User API Key ─────────────────────────────────────────────
    user_api_key = await ChatRepository.get_user_api_key(user_id)
    effective_api_key = (user_api_key or settings.gemini_api_key).strip()
    if not effective_api_key:
        raise HTTPException(
            status_code=400,
            detail="Google Gemini API key is missing. Please configure your API key in settings before uploading documents.",
        )

    # ─── Deduplication & Incremental Check ──────────────────────────────
    file_hash = _file_hash(content)
    existing_docs = await DocumentRegistryRepo.get_all_documents(target_user_id)
    existing_doc = next((d for d in existing_docs if d["filename"] == filename), None)

    if existing_doc and not force:
        existing_hash = existing_doc.get("metadata", {}).get("file_hash", "")
        if existing_hash == file_hash:
            # Identical content — skip entirely
            return FileUploadResponse(
                filename=filename,
                chunks_stored=existing_doc.get("metadata", {}).get("chunk_count", 0),
                message=f"'{filename}' is unchanged — no re-processing needed.",
                is_shared=is_shared,
            )

    # Flag: same name exists with different content → use incremental for text files
    is_update = existing_doc is not None and existing_doc["doc_type"] == "text"

    # ─── Cross-file chunk overlap check (for new different-named files) ──
    if not is_update and ext != ".csv" and not force:
        text_preview = await asyncio.to_thread(extract_text, filename, content)
        if text_preview.strip():
            preview_chunks = await asyncio.to_thread(chunk_document, text_preview)
            overlap = await vectorstore.check_chunk_overlap(target_user_id, preview_chunks)
            if overlap["overlap_pct"] >= 50:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"{overlap['overlap_pct']}% of this content already exists in: "
                        f"{', '.join(overlap['matching_files'])}. "
                        f"{overlap['overlapping_count']}/{overlap['total']} chunks are duplicates. "
                        f"Use force=true to upload anyway."
                    ),
                )

    # ─── CSV Path: PostgreSQL ────────────────────────────────────────────
    if ext == ".csv":
        try:
            schema = await load_csv_to_postgres(target_user_id, filename, content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to load CSV: {e}")

        # Generate metadata summary
        import csv as csv_mod
        import io as io_mod
        raw_text = content.decode("utf-8", errors="replace")
        reader = csv_mod.reader(io_mod.StringIO(raw_text))
        all_rows = list(reader)
        sample_rows = all_rows[1:4] if len(all_rows) > 1 else []

        def _get_csv_summary():
            return generate_document_summary(
                filename,
                doc_type="csv",
                columns=[c["name"] for c in schema["columns"]],
                sample_rows=sample_rows,
                row_count=schema["row_count"],
            )
        summary = await asyncio.to_thread(_get_csv_summary)

        await DocumentRegistryRepo.register_document(
            user_id=target_user_id,
            filename=filename,
            doc_type="csv",
            summary=summary,
            metadata={
                "columns": [c["name"] for c in schema["columns"]],
                "column_types": {c["name"]: c["type"] for c in schema["columns"]},
                "row_count": schema["row_count"],
                "file_hash": file_hash,
                "file_size": len(content),
            },
            storage_ref=schema["table_name"],
        )

        logger.info("csv_uploaded", user_id=target_user_id, filename=filename, is_shared=is_shared)
        invalidate_user_cache(user_id)
        shared_tag = " (Shared Demo)" if is_shared else ""
        return FileUploadResponse(
            filename=filename,
            chunks_stored=schema["row_count"],
            message=(
                f"CSV '{filename}'{shared_tag} loaded ({schema['row_count']} rows, "
                f"{len(schema['columns'])} columns). {summary}"
            ),
            is_shared=is_shared,
        )

    # ─── Text Path ─────────────────────────────────────────────────────────
    ext_lower = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    # Use structure-aware extraction for PDFs and DOCX — process entirely in background
    if ext_lower in (".pdf", ".docx"):
        _upload_status.setdefault(target_user_id, {})[filename] = "processing"
        background_tasks.add_task(
            _process_structured_upload_bg, target_user_id, filename, None, None, file_hash, content
        )
        logger.info("structured_upload_queued", user_id=target_user_id, filename=filename, size=len(content), is_shared=is_shared)
        shared_tag = " [Shared Demo]" if is_shared else ""
        return FileUploadResponse(
            filename=filename,
            chunks_stored=0,
            message=(
                f"'{filename}'{shared_tag} queued for processing. "
                f"Structure-aware extraction + embedding in background — searchable in a few minutes."
            ),
            is_shared=is_shared,
        )

    # For plain text files: use existing text extraction
    text_content = await asyncio.to_thread(extract_text, filename, content)
    if not text_content.strip():
        raise HTTPException(status_code=400, detail="No text content found in file.")

    chunks = await asyncio.to_thread(chunk_document, text_content)

    # Large documents (>200 chunks) → process in background to avoid timeout
    BACKGROUND_THRESHOLD = 200
    if len(chunks) > BACKGROUND_THRESHOLD and not is_update:
        _upload_status.setdefault(target_user_id, {})[filename] = "processing"
        background_tasks.add_task(
            _process_text_upload_bg, target_user_id, filename, text_content, file_hash
        )
        logger.info("large_upload_background", user_id=target_user_id, filename=filename, chunks=len(chunks), is_shared=is_shared)
        shared_tag = " [Shared Demo]" if is_shared else ""
        return FileUploadResponse(
            filename=filename,
            chunks_stored=len(chunks),
            message=(
                f"'{filename}'{shared_tag} is large ({len(chunks)} chunks). "
                f"Processing in background — it will be searchable in a few minutes."
            ),
            is_shared=is_shared,
        )

    # Use incremental embedding if this is an update to an existing file
    if is_update:
        stats = await vectorstore.store_chunks_incremental(target_user_id, chunks, filename)
        chunks_stored = stats.total_chunks
        update_msg = (
            f" [Incremental: {stats.new_chunks} new, "
            f"{stats.unchanged_chunks} unchanged, "
            f"{stats.embeddings_saved} embedding calls saved]"
        )
    else:
        chunks_stored = await vectorstore.store_chunks(target_user_id, chunks, filename)
        update_msg = ""

    def _get_text_summary():
        return generate_document_summary(filename, doc_type="text", full_text=text_content)
    summary = await asyncio.to_thread(_get_text_summary)

    await DocumentRegistryRepo.register_document(
        user_id=target_user_id,
        filename=filename,
        doc_type="text",
        summary=summary,
        metadata={
            "chunk_count": chunks_stored,
            "char_count": len(text_content),
            "file_hash": file_hash,
            "file_size": len(content),
        },
        storage_ref=f"qdrant:{vectorstore._collection_name(target_user_id)}",
    )

    logger.info("text_uploaded", user_id=target_user_id, filename=filename, chunks=chunks_stored, is_update=is_update, is_shared=is_shared)
    invalidate_user_cache(user_id)
    shared_tag = " (Shared Demo)" if is_shared else ""
    return FileUploadResponse(
        filename=filename,
        chunks_stored=chunks_stored,
        message=f"'{filename}'{shared_tag} processed into {chunks_stored} chunks.{update_msg} {summary}",
        is_shared=is_shared,
    )



async def _process_text_upload_bg(user_id: str, filename: str, text_content: str, file_hash: str):
    """Background task for processing large text documents with stream embed + upsert."""
    import asyncio
    import time

    try:
        t_start = time.time()

        # Use hierarchical chunking for better context preservation
        hierarchical_chunks = await asyncio.to_thread(chunk_document_hierarchical, text_content)
        child_texts = [c["child_content"] for c in hierarchical_chunks]

        from src.database.repository import ParentChunkRepo

        collection_name = vectorstore._ensure_collection(user_id)
        
        # Parallel Deletion of existing document and parent chunks
        await asyncio.gather(
            vectorstore.delete_document(user_id, filename),
            ParentChunkRepo.delete_parents(user_id, filename)
        )

        document_id = str(uuid.uuid4())

        # Collect unique parents for PostgreSQL
        parents_map: dict[str, dict] = {}
        for chunk in hierarchical_chunks:
            pid = chunk["parent_id"]
            if pid not in parents_map:
                parents_map[pid] = {
                    "id": pid,
                    "content": chunk["parent_content"],
                    "chunk_index": chunk["parent_index"],
                }
        parents_list = list(parents_map.values())

        # ─── Stream embed + upsert: upsert each batch as embeddings arrive ───
        total_upserted = 0

        def _stream_embed_and_upsert():
            """Run in thread: stream embeddings and upsert to Qdrant immediately."""
            nonlocal total_upserted
            from concurrent.futures import ThreadPoolExecutor
            
            UPSERT_BATCH = 256
            
            # Use ThreadPoolExecutor so upserts don't block the next embedding batch
            with ThreadPoolExecutor(max_workers=4) as executor:
                for batch_indices, batch_embeddings in embedder.embed_streaming(child_texts):
                    # Build points for this batch
                    batch_points = [
                        PointStruct(
                            id=str(uuid.uuid4()),
                            vector=emb,
                            payload={
                                "content": hierarchical_chunks[idx]["child_content"],
                                "parent_id": hierarchical_chunks[idx]["parent_id"],
                                "filename": filename,
                                "document_id": document_id,
                                "chunk_index": idx,
                                "content_hash": _content_hash(hierarchical_chunks[idx]["child_content"]),
                            },
                        )
                        for idx, emb in zip(batch_indices, batch_embeddings)
                    ]
                    # Submit upserts in background threads
                    futures = []
                    for start in range(0, len(batch_points), UPSERT_BATCH):
                        futures.append(executor.submit(
                            vectorstore.client.upsert,
                            collection_name=collection_name,
                            points=batch_points[start:start + UPSERT_BATCH],
                        ))
                    
                    # Wait and check for exceptions
                    for f in futures:
                        f.result()
                        
                    total_upserted += len(batch_points)
                    logger.debug("stream_upserted", filename=filename, batch=len(batch_points), total=total_upserted)

        # Run independent I/O tasks concurrently
        embed_task = asyncio.create_task(asyncio.to_thread(_stream_embed_and_upsert))
        store_parents_task = asyncio.create_task(ParentChunkRepo.store_parents(user_id, filename, parents_list))
        
        def _get_summary():
            return generate_document_summary(filename, doc_type="text", full_text=text_content)
        summary_task = asyncio.create_task(asyncio.to_thread(_get_summary))

        # Wait for all background tasks to complete
        _, _, summary = await asyncio.gather(embed_task, store_parents_task, summary_task)

        await DocumentRegistryRepo.register_document(
            user_id=user_id,
            filename=filename,
            doc_type="text",
            summary=summary,
            metadata={
                "chunk_count": total_upserted,
                "parent_count": len(parents_list),
                "char_count": len(text_content),
                "file_hash": file_hash,
                "file_size": len(text_content.encode("utf-8")),
                "hierarchical": True,
            },
            storage_ref=f"qdrant:{collection_name}",
        )


        _upload_status.get(user_id, {}).pop(filename, None)
        invalidate_user_cache(user_id)

        t_total = time.time() - t_start
        logger.info(
            "bg_text_uploaded",
            user_id=user_id,
            filename=filename,
            children=total_upserted,
            parents=len(parents_list),
            duration_sec=round(t_total, 1),
        )
    except Exception as e:
        _upload_status.get(user_id, {})[filename] = f"error: {e}"
        logger.error("bg_upload_failed", user_id=user_id, filename=filename, error=str(e))


async def _process_structured_upload_bg(
    user_id: str, filename: str, elements: list[dict] | None, text_content: str | None, file_hash: str, raw_content: bytes = None
):
    """Background task for structure-aware document processing with stream embed + upsert."""
    import asyncio
    import time

    try:
        t_start = time.time()

        # ─── Phase 1: Structured Extraction ───────────────────────────
        t_extract_start = time.time()
        if elements is None and raw_content:
            elements = await asyncio.to_thread(extract_structured, filename, raw_content)
            text_content = "\n\n".join(el["text"] for el in elements if el.get("text", "").strip())
        t_extract_end = time.time()

        if not elements or not text_content:
            _upload_status.get(user_id, {})[filename] = "error: No content extracted"
            logger.error("bg_structured_no_content", user_id=user_id, filename=filename)
            return

        # Count element types
        tables = sum(1 for e in elements if e["type"] == "Table")
        titles = sum(1 for e in elements if e["type"] == "Title")
        texts = sum(1 for e in elements if e["type"] == "NarrativeText")

        logger.info(
            "phase1_extraction_done",
            filename=filename,
            duration_sec=round(t_extract_end - t_extract_start, 1),
            total_elements=len(elements),
            tables=tables,
            titles=titles,
            narrative_texts=texts,
            text_chars=len(text_content),
        )

        # ─── Phase 2: Chunking ────────────────────────────────────────
        t_chunk_start = time.time()
        
        def _do_chunking():
            res = chunk_structured_document(
                elements, parent_size=2000, parent_overlap=400, child_size=1000, min_chunk_size=200
            )
            if not res:
                res = chunk_document_hierarchical(text_content)
            return res

        hierarchical_chunks = await asyncio.to_thread(_do_chunking)
        t_chunk_end = time.time()

        unique_parents = len(set(c["parent_id"] for c in hierarchical_chunks))

        logger.info(
            "phase2_chunking_done",
            filename=filename,
            duration_sec=round(t_chunk_end - t_chunk_start, 1),
            total_children=len(hierarchical_chunks),
            unique_parents=unique_parents,
        )

        # ─── Phase 3+4: Stream Embed + Upsert (pipelined) ────────────
        # Instead of waiting for all embeddings, upsert each batch as it arrives
        t_pipeline_start = time.time()

        from src.database.repository import ParentChunkRepo

        collection_name = vectorstore._ensure_collection(user_id)
        
        # Parallel Deletion
        await asyncio.gather(
            vectorstore.delete_document(user_id, filename),
            ParentChunkRepo.delete_parents(user_id, filename)
        )

        document_id = str(uuid.uuid4())

        # Collect unique parents for PostgreSQL
        parents_map: dict[str, dict] = {}
        for chunk in hierarchical_chunks:
            pid = chunk["parent_id"]
            if pid not in parents_map:
                parents_map[pid] = {
                    "id": pid,
                    "content": chunk["parent_content"],
                    "chunk_index": chunk["parent_index"],
                }
        parents_list = list(parents_map.values())

        child_texts = [c["child_content"] for c in hierarchical_chunks]
        total_upserted = 0
        batches_completed = 0

        def _stream_embed_and_upsert():
            """Run in thread: embed batches and upsert to Qdrant as each batch completes."""
            nonlocal total_upserted, batches_completed
            from concurrent.futures import ThreadPoolExecutor
            
            UPSERT_BATCH = 256

            with ThreadPoolExecutor(max_workers=4) as executor:
                for batch_indices, batch_embeddings in embedder.embed_streaming(child_texts):
                    # Build Qdrant points for this batch immediately
                    batch_points = [
                        PointStruct(
                            id=str(uuid.uuid4()),
                            vector=emb,
                            payload={
                                "content": hierarchical_chunks[idx]["child_content"],
                                "parent_id": hierarchical_chunks[idx]["parent_id"],
                                "filename": filename,
                                "document_id": document_id,
                                "chunk_index": idx,
                                "content_hash": _content_hash(hierarchical_chunks[idx]["child_content"]),
                            },
                        )
                        for idx, emb in zip(batch_indices, batch_embeddings)
                    ]

                    # Submit upserts in background threads
                    futures = []
                    for start in range(0, len(batch_points), UPSERT_BATCH):
                        futures.append(executor.submit(
                            vectorstore.client.upsert,
                            collection_name=collection_name,
                            points=batch_points[start:start + UPSERT_BATCH],
                        ))

                    # Wait and check for exceptions
                    for f in futures:
                        f.result()

                    total_upserted += len(batch_points)
                    batches_completed += 1
                    logger.debug(
                        "stream_upserted",
                        filename=filename,
                        batch_num=batches_completed,
                        batch_size=len(batch_points),
                        total=total_upserted,
                        progress_pct=round(total_upserted / len(child_texts) * 100),
                    )

        # Run independent I/O tasks concurrently (Embeddings, DB Parents, Summary)
        embed_task = asyncio.create_task(asyncio.to_thread(_stream_embed_and_upsert))
        store_parents_task = asyncio.create_task(ParentChunkRepo.store_parents(user_id, filename, parents_list))
        
        def _get_summary():
            return generate_document_summary(filename, doc_type="text", full_text=text_content)
        summary_task = asyncio.create_task(asyncio.to_thread(_get_summary))

        _, _, summary = await asyncio.gather(embed_task, store_parents_task, summary_task)
        
        t_pipeline_end = time.time()

        logger.info(
            "phase3_4_pipeline_done",
            filename=filename,
            duration_sec=round(t_pipeline_end - t_pipeline_start, 1),
            chunks_embedded=total_upserted,
            batches=batches_completed,
            avg_per_chunk_ms=round((t_pipeline_end - t_pipeline_start) / max(total_upserted, 1) * 1000, 1),
        )

        # ─── Phase 5: PostgreSQL parents + Metadata ───────────────────
        t_meta_start = time.time()

        await DocumentRegistryRepo.register_document(
            user_id=user_id,
            filename=filename,
            doc_type="text",
            summary=summary,
            metadata={
                "chunk_count": total_upserted,
                "parent_count": len(parents_list),
                "char_count": len(text_content),
                "file_hash": file_hash,
                "file_size": len(raw_content) if raw_content else len(text_content.encode("utf-8")),
                "hierarchical": True,
                "structured": True,
            },
            storage_ref=f"qdrant:{collection_name}",
        )

        t_meta_end = time.time()

        _upload_status.get(user_id, {}).pop(filename, None)
        invalidate_user_cache(user_id)

        t_total = time.time() - t_start
        logger.info(
            "bg_structured_uploaded",
            user_id=user_id,
            filename=filename,
            children=total_upserted,
            parents=len(parents_list),
            total_duration_sec=round(t_total, 1),
            extraction_sec=round(t_extract_end - t_extract_start, 1),
            chunking_sec=round(t_chunk_end - t_chunk_start, 1),
            pipeline_sec=round(t_pipeline_end - t_pipeline_start, 1),
            metadata_sec=round(t_meta_end - t_meta_start, 1),
        )
    except Exception as e:
        _upload_status.get(user_id, {})[filename] = f"error: {e}"
        logger.error("bg_structured_upload_failed", user_id=user_id, filename=filename, error=str(e))


@router.get("/upload-status/{user_id}")
async def get_upload_status(user_id: str):
    """Check status of background uploads."""
    return {"user_id": user_id, "pending": _upload_status.get(user_id, {})}


@router.delete("/upload-status/{user_id}/{filename}")
async def clear_upload_status(user_id: str, filename: str):
    """Clear a failed upload status."""
    if user_id in _upload_status:
        _upload_status[user_id].pop(filename, None)
    return {"cleared": True}


@router.post("/reupload")
async def reupload_document(
    user_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Re-upload an updated document. Uses incremental embedding —
    only re-embeds chunks whose content actually changed.
    Returns stats showing how many embeddings were saved.
    """
    filename = file.filename or "unknown.txt"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == ".csv":
        raise HTTPException(status_code=400, detail="CSV re-upload uses the regular /upload endpoint (replaces table).")

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    # Extract text
    try:
        text_content = await asyncio.to_thread(extract_text, filename, content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract text: {e}")

    if not text_content.strip():
        raise HTTPException(status_code=400, detail="No text content found.")

    # Chunk the updated document
    chunks = await asyncio.to_thread(chunk_document, text_content)

    # Incremental update — only embed new/changed chunks
    stats = await vectorstore.store_chunks_incremental(user_id, chunks, filename)

    # Update registry
    file_hash = _file_hash(content)
    def _get_reupload_summary():
        return generate_document_summary(filename, doc_type="text", full_text=text_content)
    summary = await asyncio.to_thread(_get_reupload_summary)
    await DocumentRegistryRepo.register_document(
        user_id=user_id,
        filename=filename,
        doc_type="text",
        summary=summary,
        metadata={
            "chunk_count": stats.total_chunks,
            "char_count": len(text_content),
            "file_hash": file_hash,
        },
        storage_ref=f"qdrant:{vectorstore._collection_name(user_id)}",
    )

    logger.info(
        "document_reuploaded",
        user_id=user_id,
        filename=filename,
        new_chunks=stats.new_chunks,
        unchanged=stats.unchanged_chunks,
        removed=stats.removed_chunks,
        saved=stats.embeddings_saved,
    )

    return {
        "filename": filename,
        "stats": {
            "total_chunks": stats.total_chunks,
            "new_embedded": stats.new_chunks,
            "unchanged_skipped": stats.unchanged_chunks,
            "removed": stats.removed_chunks,
            "embedding_calls_saved": stats.embeddings_saved,
        },
        "message": stats.to_log(),
    }


# ─── Synchronous Chat (REST) ─────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Synchronous chat endpoint — runs the agent and returns the answer.
    Auto-creates a session if none provided. Simpler and more reliable than WebSocket.
    """
    from src.database.repository import ChatRepository, ChatSessionRepo
    from src.graph.workflow import build_graph
    from src.graph.answer_cache import get_cached_answer, set_cached_answer
    from langchain_core.messages import HumanMessage, AIMessage

    user_id = req.user_id
    user_content = req.message.strip()
    session_id = req.session_id
    session_title = None

    if not user_content:
        raise HTTPException(status_code=400, detail="Empty message.")

    # ─── Check API key ────────────────────────────────────────────────
    user_api_key = await ChatRepository.get_user_api_key(user_id)
    effective_api_key = (user_api_key or settings.gemini_api_key).strip()
    if not effective_api_key:
        return ChatResponse(
            answer=(
                "⚠️ **Google Gemini API Key Required**\n\n"
                "Please configure your free Gemini API key in the sidebar settings to start chatting. "
                "Get one instantly at [Google AI Studio](https://aistudio.google.com/apikey)."
            ),
            session_id=session_id or "none",
        )

    # ─── Daily limit check ────────────────────────────────────────────
    daily_count = await ChatRepository.get_daily_message_count(user_id)
    if daily_count >= settings.daily_message_limit:
        return ChatResponse(
            answer=(
                f"⚠️ You've reached your daily message limit "
                f"({settings.daily_message_limit} messages/day). Try again tomorrow."
            ),
            session_id=session_id or "none",
        )

    # ─── Check cache early ────────────────────────────────────────────
    cached = get_cached_answer(user_id, user_content)

    # ─── Auto-create session if needed ────────────────────────────────
    if not session_id:
        new_session = await ChatSessionRepo.create_session(user_id)
        session_id = new_session["id"]
        session_title = user_content[:50] + ("..." if len(user_content) > 50 else "")
        asyncio.create_task(ChatSessionRepo.update_title(session_id, session_title))

    asyncio.create_task(ChatRepository.save_message(user_id, "user", user_content, session_id=session_id))

    if cached:
        asyncio.create_task(ChatRepository.save_message(user_id, "assistant", cached, "agent", session_id=session_id))
        return ChatResponse(answer=cached, session_id=session_id, session_title=session_title)

    # ─── Load recent history for context ──────────────────────────────
    history = await ChatRepository.load_history(user_id, 10, session_id=session_id)
    messages = []
    for msg in history[:-1]:  # Exclude the message we just saved
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=user_content))

    # ─── Run agent ────────────────────────────────────────────────────
    agent = build_graph(user_id=user_id, api_key=effective_api_key, include_shared=req.include_shared)
    trace_steps = []
    final_answer = ""


    try:
        async for event in agent.astream_events(
            {"messages": messages},
            version="v2",
            config={
                "recursion_limit": 40,
                "metadata": {"user_id": user_id},
                "tags": [f"user:{user_id}"],
            },
        ):
            kind = event.get("event", "")
            if kind == "on_tool_start":
                tool_name = event.get("name", "")
                trace_steps.append(f"🔧 {tool_name}")
            elif kind == "on_chat_model_end":
                output = event.get("data", {}).get("output")
                if output and hasattr(output, "content"):
                    content = output.content
                    extracted = ""
                    if isinstance(content, list):
                        parts = []
                        for part in content:
                            if isinstance(part, str):
                                parts.append(part)
                            elif isinstance(part, dict) and part.get("type") == "text":
                                parts.append(part["text"])
                        extracted = " ".join(parts).strip()
                    elif isinstance(content, str):
                        extracted = content.strip()
                    if extracted:
                        final_answer = extracted

        if not final_answer:
            final_answer = "I couldn't generate an answer. Please try again."

    except Exception as e:
        logger.error("chat_agent_error", error=str(e), user_id=user_id)
        final_answer = "Sorry, something went wrong. Please try again."

    # ─── Save + cache ─────────────────────────────────────────────────
    asyncio.create_task(ChatRepository.save_message(user_id, "assistant", final_answer, "agent", session_id=session_id))
    if "went wrong" not in final_answer and "try again" not in final_answer:
        set_cached_answer(user_id, user_content, final_answer, "general")

    return ChatResponse(
        answer=final_answer,
        session_id=session_id,
        session_title=session_title,
        trace=" → ".join(trace_steps),
    )


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming chat endpoint via Server-Sent Events (SSE).
    Emits live status updates as the agent works, then the final answer.
    """
    from fastapi.responses import StreamingResponse
    from src.database.repository import ChatRepository, ChatSessionRepo
    from src.graph.workflow import build_graph
    from src.graph.answer_cache import get_cached_answer, set_cached_answer
    from langchain_core.messages import HumanMessage, AIMessage

    async def event_generator():
        user_id = req.user_id
        user_content = req.message.strip()
        session_id = req.session_id
        session_title = None

        if not user_content:
            yield f"data: {json.dumps({'type': 'answer', 'content': 'Empty message.', 'session_id': session_id or 'none'})}\n\n"
            return

        # Daily limit
        daily_count = await ChatRepository.get_daily_message_count(user_id)
        if daily_count >= settings.daily_message_limit:
            msg = f"⚠️ Daily message limit reached ({settings.daily_message_limit}/day). Try again tomorrow."
            yield f"data: {json.dumps({'type': 'answer', 'content': msg, 'session_id': session_id or 'none'})}\n\n"
            return

        # Cache check early
        cached = get_cached_answer(user_id, user_content)

        # Auto-create session
        if not session_id:
            new_session = await ChatSessionRepo.create_session(user_id)
            session_id = new_session["id"]
            session_title = user_content[:50] + ("..." if len(user_content) > 50 else "")
            asyncio.create_task(ChatSessionRepo.update_title(session_id, session_title))
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id, 'title': session_title})}\n\n"

        asyncio.create_task(ChatRepository.save_message(user_id, "user", user_content, session_id=session_id))

        if cached:
            asyncio.create_task(ChatRepository.save_message(user_id, "assistant", cached, "agent", session_id=session_id))
            yield f"data: {json.dumps({'type': 'status', 'content': '⚡ Found in cache'})}\n\n"
            yield f"data: {json.dumps({'type': 'answer', 'content': cached, 'session_id': session_id})}\n\n"
            return

        # Load history for context
        history = await ChatRepository.load_history(user_id, 10, session_id=session_id)
        messages = []
        for m in history[:-1]:
            if m["role"] == "user":
                messages.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                messages.append(AIMessage(content=m["content"]))
        messages.append(HumanMessage(content=user_content))

        # ─── Check API key ────────────────────────────────────────────────
        user_api_key = await ChatRepository.get_user_api_key(user_id)
        effective_api_key = (user_api_key or settings.gemini_api_key).strip()
        if not effective_api_key:
            msg = (
                "⚠️ **Google Gemini API Key Required**\n\n"
                "Please configure your free Gemini API key in the sidebar settings to start chatting. "
                "Get one instantly at [Google AI Studio](https://aistudio.google.com/apikey)."
            )
            yield f"data: {json.dumps({'type': 'answer', 'content': msg, 'session_id': session_id or 'none'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'status', 'content': '🧠 Understanding your question...'})}\n\n"

        agent = build_graph(user_id=user_id, api_key=effective_api_key, include_shared=req.include_shared)
        trace_steps = []
        final_answer = ""


        try:
            async for event in agent.astream_events(
                {"messages": messages},
                version="v2",
                config={
                    "recursion_limit": 40,
                    "metadata": {"user_id": user_id},
                    "tags": [f"user:{user_id}"],
                },
            ):
                kind = event.get("event", "")
                if kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    friendly = _tool_friendly(tool_name)
                    trace_steps.append(f"🔧 {tool_name}")
                    yield f"data: {json.dumps({'type': 'status', 'content': friendly})}\n\n"
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    yield f"data: {json.dumps({'type': 'status', 'content': f'✓ {tool_name} done'})}\n\n"
                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content"):
                        content = chunk.content
                        text_val = ""
                        if isinstance(content, str):
                            text_val = content
                        elif isinstance(content, list):
                            text_val = "".join([c.get("text", "") for c in content if isinstance(c, dict) and "text" in c])
                        
                        # Only stream if it has text and is not making a tool call
                        if text_val and not getattr(chunk, "tool_calls", None):
                            yield f"data: {json.dumps({'type': 'token', 'content': text_val})}\n\n"
                elif kind == "on_chat_model_end":
                    output = event.get("data", {}).get("output")
                    if output and hasattr(output, "content"):
                        content = output.content
                        extracted = ""
                        if isinstance(content, list):
                            parts = []
                            for part in content:
                                if isinstance(part, str):
                                    parts.append(part)
                                elif isinstance(part, dict) and part.get("type") == "text":
                                    parts.append(part["text"])
                            extracted = " ".join(parts).strip()
                        elif isinstance(content, str):
                            extracted = content.strip()
                        # Only overwrite when we got real text (tool-call turns have empty text)
                        if extracted:
                            final_answer = extracted

            if not final_answer:
                final_answer = "I couldn't generate an answer. Please try again."

        except Exception as e:
            logger.error("chat_stream_error", error=str(e), user_id=user_id)
            final_answer = "Sorry, something went wrong. Please try again."

        asyncio.create_task(ChatRepository.save_message(user_id, "assistant", final_answer, "agent", session_id=session_id))
        if "went wrong" not in final_answer and "try again" not in final_answer:
            set_cached_answer(user_id, user_content, final_answer, "general")

        payload = {
            "type": "answer",
            "content": final_answer,
            "session_id": session_id,
            "trace": " → ".join(trace_steps),
        }
        yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _tool_friendly(tool_name: str) -> str:
    """User-friendly status for tool calls."""
    mapping = {
        "get_data_schema": "📂 Checking your data tables...",
        "run_sql_query": "🗄️ Querying your data...",
        "search_documents": "📖 Searching your documents...",
        "calculator": "🧮 Calculating...",
    }
    return mapping.get(tool_name, f"⚙️ Using {tool_name}...")


# ─── Session Management ──────────────────────────────────────────────────────

@router.post("/sessions/{user_id}")
async def create_session(user_id: str):
    """Create a new chat session for a user."""
    from src.database.repository import ChatSessionRepo
    session = await ChatSessionRepo.create_session(user_id)
    return session


@router.get("/sessions/{user_id}")
async def list_sessions(user_id: str):
    """List all chat sessions for a user."""
    from src.database.repository import ChatSessionRepo
    sessions = await ChatSessionRepo.list_sessions(user_id)
    return {"user_id": user_id, "sessions": sessions}


@router.delete("/sessions/{user_id}/{session_id}")
async def delete_session(user_id: str, session_id: str):
    """Delete a chat session and its messages."""
    from src.database.repository import ChatSessionRepo
    await ChatSessionRepo.delete_session(user_id, session_id)
    return {"deleted": True, "session_id": session_id}


@router.get("/sessions/{user_id}/{session_id}/history")
async def get_session_history(user_id: str, session_id: str):
    """Get chat history for a specific session."""
    history = await ChatRepository.load_history(user_id, limit=50, session_id=session_id)
    return {"session_id": session_id, "messages": history}


@router.get("/documents/{user_id}", response_model=DocumentListResponse)
async def list_documents(user_id: str):
    """List all documents for a user, plus shared demo documents and storage usage."""
    user_docs = await DocumentRegistryRepo.get_all_documents(user_id)
    shared_docs = await DocumentRegistryRepo.get_shared_documents()

    user_bytes = sum(
        int(d.get("metadata", {}).get("file_size", d.get("metadata", {}).get("char_count", 0)))
        for d in user_docs
    )
    user_obj = await ChatRepository.get_user(user_id)
    is_admin = settings.is_super_admin(user_obj.email if user_obj else None)

    # Format user documents
    user_display = []
    for d in user_docs:
        if d["doc_type"] == "csv":
            cols = d.get("metadata", {}).get("columns", [])
            rows = d.get("metadata", {}).get("row_count", 0)
            user_display.append(f"📊 {d['filename']} — CSV ({rows} rows, {len(cols)} cols)")
        else:
            chunks = d.get("metadata", {}).get("chunk_count", 0)
            user_display.append(f"📄 {d['filename']} — Text ({chunks} chunks)")

    # Format shared documents
    shared_display = []
    for d in shared_docs:
        if d["doc_type"] == "csv":
            cols = d.get("metadata", {}).get("columns", [])
            rows = d.get("metadata", {}).get("row_count", 0)
            shared_display.append(f"📊 {d['filename']} — CSV ({rows} rows) (Shared Demo)")
        else:
            chunks = d.get("metadata", {}).get("chunk_count", 0)
            shared_display.append(f"📄 {d['filename']} — Text ({chunks} chunks) (Shared Demo)")

    return DocumentListResponse(
        user_id=user_id,
        documents=user_display,
        shared_documents=shared_display,
        storage_used_bytes=user_bytes,
        storage_used_mb=round(user_bytes / (1024 * 1024), 2),
        storage_quota_mb=settings.user_storage_quota_mb,
        is_super_admin=is_admin,
    )


@router.delete("/documents/{user_id}/{filename}", response_model=DocumentDeleteResponse)
async def delete_document(user_id: str, filename: str, is_shared: bool = False):
    """Delete a document from both storage and registry."""
    from src.database.repository import ParentChunkRepo

    target_user_id = user_id
    if is_shared:
        user_obj = await ChatRepository.get_user(user_id)
        if not user_obj or not settings.is_super_admin(user_obj.email):
            raise HTTPException(status_code=403, detail="Only Super Admins can delete shared demo documents.")
        target_user_id = settings.shared_user_id

    docs = await DocumentRegistryRepo.get_all_documents(target_user_id)
    target = next((d for d in docs if d["filename"] == filename), None)

    if not target:
        return DocumentDeleteResponse(filename=filename, deleted=False, message="Not found.")

    if target["doc_type"] == "csv":
        await drop_user_table(target_user_id, filename)
    else:
        await vectorstore.delete_document(target_user_id, filename)
        await ParentChunkRepo.delete_parents(target_user_id, filename)

    await DocumentRegistryRepo.delete_document(target_user_id, filename)
    invalidate_user_cache(user_id)
    return DocumentDeleteResponse(filename=filename, deleted=True, message=f"Deleted '{filename}'.")



@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, token: str = ""):
    """WebSocket endpoint. Requires valid JWT token as query param."""
    from src.api.auth import verify_ws_token

    if token:
        verified_user = verify_ws_token(token)
        if verified_user and verified_user != user_id:
            await websocket.close(code=4001, reason="Token doesn't match user_id")
            return
        if not verified_user:
            await websocket.close(code=4001, reason="Invalid token")
            return

    await handle_websocket(websocket, user_id)


@router.get("/graph-image")
async def get_graph_image():
    """Returns the graph workflow as a PNG image."""
    from fastapi.responses import Response
    from src.graph.workflow import build_graph
    agent = build_graph(user_id="viewer")
    png_bytes = agent.get_graph().draw_mermaid_png()
    return Response(content=png_bytes, media_type="image/png")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        active_connections=manager.count,
        model=settings.gemini_model,
    )
