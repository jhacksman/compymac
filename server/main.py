"""FastAPI server with WebSocket support for CompyMac"""
import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .auth import AuthService
from .database import Database
from .sessions import SessionManager

# Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://compymac:compymac@localhost:5432/compymac"
)
WORKSPACES_ROOT = Path(os.getenv("WORKSPACES_ROOT", "/tmp/compymac-workspaces"))

# Initialize database
db_manager = Database(DATABASE_URL)
db_manager.create_tables()

# Initialize FastAPI
app = FastAPI(
    title="CompyMac API",
    description="Multi-user agent session management with authentication",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()


# Dependency injection
def get_db():
    """Get database session"""
    return next(db_manager.get_session())


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    """Get current user from JWT token"""
    token = credentials.credentials
    auth_service = AuthService(db)
    user_id = auth_service.verify_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user_id


# Pydantic models
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OAuthRequest(BaseModel):
    code: str
    redirect_uri: str


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: str
    last_active: str


class MessageRequest(BaseModel):
    role: str
    content: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


# Authentication endpoints
@app.post("/api/auth/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register new user with email/password"""
    try:
        auth_service = AuthService(db)
        user = auth_service.create_user_with_password(
            email=request.email, password=request.password, name=request.name
        )
        token = auth_service.create_access_token(user.id)
        return TokenResponse(access_token=token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email/password"""
    auth_service = AuthService(db)
    user = auth_service.authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = auth_service.create_access_token(user.id)
    return TokenResponse(access_token=token)


@app.post("/api/auth/oauth/google", response_model=TokenResponse)
async def google_oauth(request: OAuthRequest, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    auth_service = AuthService(db)
    user = await auth_service.handle_google_oauth(request.code, request.redirect_uri)
    token = auth_service.create_access_token(user.id)
    return TokenResponse(access_token=token)


@app.post("/api/auth/oauth/github", response_model=TokenResponse)
async def github_oauth(request: OAuthRequest, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback"""
    auth_service = AuthService(db)
    user = await auth_service.handle_github_oauth(request.code, request.redirect_uri)
    token = auth_service.create_access_token(user.id)
    return TokenResponse(access_token=token)


@app.post("/api/auth/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Logout and revoke token"""
    auth_service = AuthService(db)
    auth_service.revoke_token(credentials.credentials)
    return {"message": "Logged out successfully"}


# Session endpoints
@app.post("/api/sessions", response_model=SessionResponse)
async def create_session(
    title: str = "New Chat",
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create new agent session"""
    session_manager = SessionManager(db, WORKSPACES_ROOT)
    session = session_manager.create_session(user_id, title)
    return SessionResponse(
        id=str(session.id),
        title=session.title,
        created_at=session.created_at.isoformat(),
        last_active=session.last_active.isoformat(),
    )


@app.get("/api/sessions", response_model=List[SessionResponse])
async def list_sessions(
    user_id: uuid.UUID = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List all sessions for current user"""
    session_manager = SessionManager(db, WORKSPACES_ROOT)
    sessions = session_manager.list_sessions(user_id)
    return [
        SessionResponse(
            id=str(s.id),
            title=s.title,
            created_at=s.created_at.isoformat(),
            last_active=s.last_active.isoformat(),
        )
        for s in sessions
    ]


@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get session by ID"""
    session_manager = SessionManager(db, WORKSPACES_ROOT)
    session = session_manager.get_session(session_id, user_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return SessionResponse(
        id=str(session.id),
        title=session.title,
        created_at=session.created_at.isoformat(),
        last_active=session.last_active.isoformat(),
    )


@app.delete("/api/sessions/{session_id}")
async def archive_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Archive a session"""
    session_manager = SessionManager(db, WORKSPACES_ROOT)
    success = session_manager.archive_session(session_id, user_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"message": "Session archived"}


# Conversation endpoints
@app.get("/api/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_conversation(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get conversation history"""
    session_manager = SessionManager(db, WORKSPACES_ROOT)
    messages = session_manager.get_conversation_history(session_id, user_id)
    return [
        MessageResponse(
            id=str(m.id),
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@app.post("/api/sessions/{session_id}/messages", response_model=MessageResponse)
async def add_message(
    session_id: uuid.UUID,
    request: MessageRequest,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add message to conversation"""
    session_manager = SessionManager(db, WORKSPACES_ROOT)
    message = session_manager.add_message(session_id, user_id, request.role, request.content)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return MessageResponse(
        id=str(message.id),
        role=message.role,
        content=message.content,
        created_at=message.created_at.isoformat(),
    )


# WebSocket endpoint for real-time agent communication
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: uuid.UUID):
    """WebSocket connection for real-time agent communication"""
    await websocket.accept()

    # Authenticate via query params (token passed in URL)
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return

    # Get database session
    db = next(db_manager.get_session())
    try:
        # Verify token
        auth_service = AuthService(db)
        user_id = auth_service.verify_token(token)
        if not user_id:
            await websocket.close(code=1008, reason="Invalid or expired token")
            return

        # Verify session ownership
        session_manager = SessionManager(db, WORKSPACES_ROOT)
        session = session_manager.get_session(session_id, user_id)
        if not session:
            await websocket.close(code=1008, reason="Session not found or access denied")
            return

        # Load conversation history
        messages = session_manager.get_conversation_history(session_id, user_id)
        await websocket.send_json(
            {
                "type": "history",
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in messages
                ],
            }
        )

        # Handle messages
        try:
            while True:
                data = await websocket.receive_json()

                if data.get("type") == "message":
                    # Save user message
                    user_message = session_manager.add_message(
                        session_id, user_id, "user", data["content"]
                    )

                    # TODO: Integrate with CompyMac agent here
                    # For now, echo back
                    await websocket.send_json(
                        {
                            "type": "message",
                            "role": "user",
                            "content": data["content"],
                            "created_at": user_message.created_at.isoformat(),
                        }
                    )

                    # Mock assistant response
                    assistant_message = session_manager.add_message(
                        session_id,
                        user_id,
                        "assistant",
                        f"Received: {data['content']}",
                    )
                    await websocket.send_json(
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": assistant_message.content,
                            "created_at": assistant_message.created_at.isoformat(),
                        }
                    )

        except WebSocketDisconnect:
            pass
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
