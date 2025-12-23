"""Session management - workspace isolation and conversation persistence"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from .database import AgentSession, Conversation, User


class SessionManager:
    """Manage agent sessions with workspace isolation"""

    def __init__(self, db: Session, workspaces_root: Path):
        self.db = db
        self.workspaces_root = workspaces_root
        self.workspaces_root.mkdir(parents=True, exist_ok=True)

    # Session Management

    def create_session(
        self, user_id: uuid.UUID, title: str = "New Chat"
    ) -> AgentSession:
        """Create new agent session with isolated workspace"""
        session_id = uuid.uuid4()
        workspace_path = self.workspaces_root / str(user_id) / str(session_id)
        workspace_path.mkdir(parents=True, exist_ok=True)

        session = AgentSession(
            id=session_id,
            user_id=user_id,
            title=title,
            workspace_path=str(workspace_path),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[AgentSession]:
        """Get session by ID, verifying ownership"""
        return (
            self.db.query(AgentSession)
            .filter(
                AgentSession.id == session_id,
                AgentSession.user_id == user_id,
                AgentSession.is_archived == False,
            )
            .first()
        )

    def list_sessions(self, user_id: uuid.UUID) -> List[AgentSession]:
        """List all sessions for a user"""
        return (
            self.db.query(AgentSession)
            .filter(
                AgentSession.user_id == user_id, AgentSession.is_archived == False
            )
            .order_by(AgentSession.last_active.desc())
            .all()
        )

    def update_session_title(
        self, session_id: uuid.UUID, user_id: uuid.UUID, title: str
    ) -> bool:
        """Update session title"""
        session = self.get_session(session_id, user_id)
        if not session:
            return False
        session.title = title
        self.db.commit()
        return True

    def archive_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Archive a session (soft delete)"""
        session = self.get_session(session_id, user_id)
        if not session:
            return False
        session.is_archived = True
        self.db.commit()
        return True

    def touch_session(self, session_id: uuid.UUID) -> None:
        """Update last_active timestamp"""
        self.db.query(AgentSession).filter(AgentSession.id == session_id).update(
            {"last_active": datetime.utcnow()}
        )
        self.db.commit()

    # Conversation Management

    def add_message(
        self, session_id: uuid.UUID, user_id: uuid.UUID, role: str, content: str
    ) -> Optional[Conversation]:
        """Add message to conversation"""
        # Verify session ownership
        session = self.get_session(session_id, user_id)
        if not session:
            return None

        message = Conversation(
            agent_session_id=session_id, role=role, content=content
        )
        self.db.add(message)
        self.touch_session(session_id)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_conversation_history(
        self, session_id: uuid.UUID, user_id: uuid.UUID, limit: Optional[int] = None
    ) -> List[Conversation]:
        """Get conversation history for a session"""
        # Verify session ownership
        session = self.get_session(session_id, user_id)
        if not session:
            return []

        query = (
            self.db.query(Conversation)
            .filter(Conversation.agent_session_id == session_id)
            .order_by(Conversation.created_at.asc())
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def clear_conversation(self, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Clear conversation history for a session"""
        # Verify session ownership
        session = self.get_session(session_id, user_id)
        if not session:
            return False

        self.db.query(Conversation).filter(
            Conversation.agent_session_id == session_id
        ).delete()
        self.db.commit()
        return True

    # Workspace Management

    def get_workspace_path(self, session_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Path]:
        """Get workspace path for a session"""
        session = self.get_session(session_id, user_id)
        if not session:
            return None
        return Path(session.workspace_path)
