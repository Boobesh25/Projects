"""Data access layer for chat persistence."""

from datetime import datetime, timezone
from sqlalchemy import select, update
from src.database.engine import async_session
from src.database.models import User, ChatMessage
from src.config.settings import settings


class ChatRepository:
    """Repository for user and message CRUD operations."""

    @staticmethod
    async def get_user(user_id: str) -> User | None:
        """Find user by user_id."""
        async with async_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_user(user_id: str) -> tuple[bool, User]:

        """
        Get existing user or create new one.
        Returns (existed: bool, user: User).
        """
        async with async_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if user:
                # Update last_active
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(last_active=datetime.now(timezone.utc))
                )
                await session.commit()
                return True, user

            user = User(id=user_id)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return False, user

    @staticmethod
    async def get_or_create_google_user(
        google_id: str,
        email: str,
        display_name: str,
        avatar_url: str = "",
    ) -> tuple[bool, User]:
        """
        Find user by email (Google OAuth) or create new one.
        Uses email as the unique identifier for Google users.
        Returns (existed: bool, user: User).
        """
        async with async_session() as session:
            # Look up by email first
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if user:
                # Update last_active and profile info
                await session.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(
                        last_active=datetime.now(timezone.utc),
                        display_name=display_name,
                        avatar_url=avatar_url,
                    )
                )
                await session.commit()
                return True, user

            # Create new user with google_id as the primary key
            user = User(
                id=google_id,
                email=email,
                display_name=display_name,
                avatar_url=avatar_url,
                auth_provider="google",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return False, user

    @staticmethod
    async def get_user_api_key(user_id: str) -> str | None:
        """Fetch and decrypt the user's Google Gemini API key."""
        from src.config.security import decrypt_api_key

        async with async_session() as session:
            result = await session.execute(
                select(User.encrypted_api_key).where(User.id == user_id)
            )
            encrypted = result.scalar_one_or_none()
            if not encrypted:
                return None
            return decrypt_api_key(encrypted) or None

    @staticmethod
    async def set_user_api_key(user_id: str, plain_api_key: str | None) -> None:
        """Encrypt and store (or clear) the user's Google Gemini API key."""
        from src.config.security import encrypt_api_key

        encrypted = encrypt_api_key(plain_api_key) if plain_api_key else None
        async with async_session() as session:
            # Ensure user exists first
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                user = User(id=user_id, encrypted_api_key=encrypted)
                session.add(user)
            else:
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(encrypted_api_key=encrypted, last_active=datetime.now(timezone.utc))
                )
            await session.commit()

    @staticmethod
    async def get_user_api_key_status(user_id: str) -> tuple[bool, str]:
        """Return (has_key: bool, masked_key: str) for safe UI display."""
        from src.config.security import decrypt_api_key, mask_api_key

        async with async_session() as session:
            result = await session.execute(
                select(User.encrypted_api_key).where(User.id == user_id)
            )
            encrypted = result.scalar_one_or_none()
            if not encrypted:
                return False, ""
            plain = decrypt_api_key(encrypted)
            if not plain:
                return False, ""
            return True, mask_api_key(plain)

    @staticmethod
    async def save_message(
        user_id: str, role: str, content: str, agent_name: str | None = None, session_id: str = "default"
    ) -> ChatMessage:
        """Persist a single chat message."""
        async with async_session() as session:
            msg = ChatMessage(
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=content,
                agent_name=agent_name,
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            return msg

    @staticmethod
    async def get_daily_message_count(user_id: str) -> int:
        """Count user messages sent today (UTC)."""
        from sqlalchemy import func

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        async with async_session() as session:
            result = await session.execute(
                select(func.count(ChatMessage.id))
                .where(
                    ChatMessage.user_id == user_id,
                    ChatMessage.role == "user",
                    ChatMessage.timestamp >= today_start,
                )
            )
            return result.scalar_one()

    @staticmethod
    async def load_history(user_id: str, limit: int | None = None, session_id: str = "default") -> list[dict]:
        """
        Load the most recent messages for a user session.
        Returns list of dicts: [{"role": ..., "content": ..., "agent_name": ...}]
        """
        if limit is None:
            limit = settings.max_context_messages

        async with async_session() as session:
            result = await session.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.user_id == user_id,
                    ChatMessage.session_id == session_id,
                )
                .order_by(ChatMessage.timestamp.desc())
                .limit(limit)
            )
            messages = result.scalars().all()

            return [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "agent_name": msg.agent_name,
                }
                for msg in reversed(messages)
            ]


class ChatSessionRepo:
    """Repository for chat session management."""

    @staticmethod
    async def create_session(user_id: str, title: str = "New Chat") -> dict:
        """Create a new chat session for a user."""
        import uuid as _uuid
        from src.database.models import ChatSession

        session_id = str(_uuid.uuid4())[:8]
        async with async_session() as session:
            chat_session = ChatSession(
                id=session_id,
                user_id=user_id,
                title=title,
            )
            session.add(chat_session)
            await session.commit()
            return {"id": session_id, "title": title}

    @staticmethod
    async def list_sessions(user_id: str) -> list[dict]:
        """List all chat sessions for a user, most recent first."""
        from src.database.models import ChatSession

        async with async_session() as session:
            result = await session.execute(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(ChatSession.updated_at.desc())
            )
            sessions = result.scalars().all()
            return [
                {
                    "id": s.id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in sessions
            ]

    @staticmethod
    async def update_title(session_id: str, title: str):
        """Update a session's title (e.g., from first message)."""
        from src.database.models import ChatSession
        from sqlalchemy import update as sql_update

        async with async_session() as session:
            await session.execute(
                sql_update(ChatSession)
                .where(ChatSession.id == session_id)
                .values(title=title)
            )
            await session.commit()

    @staticmethod
    async def delete_session(user_id: str, session_id: str):
        """Delete a session and all its messages."""
        from src.database.models import ChatSession, ChatMessage
        from sqlalchemy import delete

        async with async_session() as session:
            await session.execute(
                delete(ChatMessage).where(
                    ChatMessage.user_id == user_id,
                    ChatMessage.session_id == session_id,
                )
            )
            await session.execute(
                delete(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user_id,
                )
            )
            await session.commit()


class DocumentRegistryRepo:
    """Repository for document metadata operations."""

    @staticmethod
    async def register_document(
        user_id: str,
        filename: str,
        doc_type: str,
        summary: str,
        metadata: dict | None = None,
        storage_ref: str | None = None,
    ):
        """Register a new document in the registry."""
        from src.database.models import DocumentRegistry

        async with async_session() as session:
            # Remove existing entry for same file (re-upload)
            existing = await session.execute(
                select(DocumentRegistry).where(
                    DocumentRegistry.user_id == user_id,
                    DocumentRegistry.filename == filename,
                )
            )
            for doc in existing.scalars().all():
                await session.delete(doc)

            doc = DocumentRegistry(
                user_id=user_id,
                filename=filename,
                doc_type=doc_type,
                summary=summary,
                doc_metadata=metadata or {},
                storage_ref=storage_ref,
            )
            session.add(doc)
            await session.commit()

    @staticmethod
    async def get_all_documents(user_id: str) -> list[dict]:
        """Get all document metadata for a user."""
        from src.database.models import DocumentRegistry

        async with async_session() as session:
            result = await session.execute(
                select(DocumentRegistry)
                .where(DocumentRegistry.user_id == user_id)
                .order_by(DocumentRegistry.uploaded_at.desc())
            )
            docs = result.scalars().all()
            return [
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "doc_type": doc.doc_type,
                    "summary": doc.summary,
                    "metadata": doc.doc_metadata,
                    "storage_ref": doc.storage_ref,
                    "uploaded_at": doc.uploaded_at.isoformat(),
                    "is_shared": False,
                }
                for doc in docs
            ]

    @staticmethod
    async def get_shared_documents() -> list[dict]:
        """Get all shared demo documents uploaded by Super Admin."""
        from src.database.models import DocumentRegistry
        from src.config.settings import settings

        async with async_session() as session:
            result = await session.execute(
                select(DocumentRegistry)
                .where(DocumentRegistry.user_id == settings.shared_user_id)
                .order_by(DocumentRegistry.uploaded_at.desc())
            )
            docs = result.scalars().all()
            return [
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "doc_type": doc.doc_type,
                    "summary": doc.summary,
                    "metadata": doc.doc_metadata,
                    "storage_ref": doc.storage_ref,
                    "uploaded_at": doc.uploaded_at.isoformat(),
                    "is_shared": True,
                }
                for doc in docs
            ]

    @staticmethod
    async def get_user_storage_bytes(user_id: str) -> int:
        """Calculate total cumulative size in bytes for a user's active documents."""
        from src.database.models import DocumentRegistry

        async with async_session() as session:
            result = await session.execute(
                select(DocumentRegistry)
                .where(DocumentRegistry.user_id == user_id)
            )
            docs = result.scalars().all()
            total_bytes = 0
            for doc in docs:
                meta = doc.doc_metadata or {}
                # Prioritize explicit file_size, fallback to char_count
                total_bytes += int(meta.get("file_size", meta.get("char_count", 0)))
            return total_bytes

    @staticmethod
    async def delete_document(user_id: str, filename: str) -> bool:
        """Remove a document from the registry."""
        from src.database.models import DocumentRegistry

        async with async_session() as session:
            result = await session.execute(
                select(DocumentRegistry).where(
                    DocumentRegistry.user_id == user_id,
                    DocumentRegistry.filename == filename,
                )
            )
            doc = result.scalar_one_or_none()
            if doc:
                await session.delete(doc)
                await session.commit()
                return True
            return False



class ParentChunkRepo:
    """Repository for parent chunk storage and retrieval."""

    @staticmethod
    async def store_parents(user_id: str, filename: str, parents: list[dict]):
        """
        Store parent chunks. Each parent dict has: {id, content, chunk_index}.
        Replaces existing parents for the same file.
        """
        from src.database.models import ParentChunk

        async with async_session() as session:
            # Delete existing parents for this file
            from sqlalchemy import delete
            await session.execute(
                delete(ParentChunk).where(
                    ParentChunk.user_id == user_id,
                    ParentChunk.filename == filename,
                )
            )

            # Insert new parents
            for p in parents:
                chunk = ParentChunk(
                    id=p["id"],
                    user_id=user_id,
                    filename=filename,
                    content=p["content"],
                    chunk_index=p["chunk_index"],
                )
                session.add(chunk)

            await session.commit()

    @staticmethod
    async def get_parents_by_ids(parent_ids: list[str]) -> dict[str, str]:
        """
        Fetch parent content by IDs.
        Returns: {parent_id: content}
        """
        if not parent_ids:
            return {}

        from src.database.models import ParentChunk

        async with async_session() as session:
            result = await session.execute(
                select(ParentChunk).where(ParentChunk.id.in_(parent_ids))
            )
            parents = result.scalars().all()
            return {p.id: p.content for p in parents}

    @staticmethod
    async def delete_parents(user_id: str, filename: str):
        """Delete all parent chunks for a file."""
        from src.database.models import ParentChunk
        from sqlalchemy import delete

        async with async_session() as session:
            await session.execute(
                delete(ParentChunk).where(
                    ParentChunk.user_id == user_id,
                    ParentChunk.filename == filename,
                )
            )
            await session.commit()
