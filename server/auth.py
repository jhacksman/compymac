"""Authentication service - OAuth and JWT handling"""
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import Account, SessionToken, User

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings (these should come from env vars in production)
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


class AuthService:
    """Handle authentication operations"""

    def __init__(self, db: Session):
        self.db = db

    # Email/Password Authentication

    def create_user_with_password(
        self, email: str, password: str, name: Optional[str] = None
    ) -> User:
        """Create new user with email/password"""
        # Check if user already exists
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            raise ValueError("User with this email already exists")

        hashed_password = pwd_context.hash(password)
        user = User(
            id=uuid.uuid4(),
            email=email,
            name=name,
            hashed_password=hashed_password,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email/password"""
        user = self.db.query(User).filter(User.email == email).first()
        if not user or not user.hashed_password:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    # OAuth Authentication

    async def handle_google_oauth(self, code: str, redirect_uri: str) -> User:
        """Exchange Google OAuth code for user"""
        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "code": code,
                    "client_id": "YOUR_GOOGLE_CLIENT_ID",  # From env
                    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",  # From env
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            tokens = response.json()

        # Get user info
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            user_info = response.json()

        # Find or create user
        account = (
            self.db.query(Account)
            .filter(
                Account.provider == "google",
                Account.provider_account_id == user_info["id"],
            )
            .first()
        )

        if account:
            user = account.user
            # Update tokens
            account.access_token = tokens.get("access_token")
            account.refresh_token = tokens.get("refresh_token")
            account.expires_at = (
                datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
            )
            self.db.commit()
        else:
            # Create new user and account
            user = User(
                email=user_info["email"],
                name=user_info.get("name"),
                avatar_url=user_info.get("picture"),
                email_verified=datetime.utcnow(),
            )
            self.db.add(user)
            self.db.flush()

            account = Account(
                user_id=user.id,
                provider="google",
                provider_account_id=user_info["id"],
                access_token=tokens.get("access_token"),
                refresh_token=tokens.get("refresh_token"),
                expires_at=datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600)),
            )
            self.db.add(account)
            self.db.commit()
            self.db.refresh(user)

        return user

    async def handle_github_oauth(self, code: str, redirect_uri: str) -> User:
        """Exchange GitHub OAuth code for user"""
        # Exchange code for tokens
        token_url = "https://github.com/login/oauth/access_token"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                headers={"Accept": "application/json"},
                data={
                    "code": code,
                    "client_id": "YOUR_GITHUB_CLIENT_ID",  # From env
                    "client_secret": "YOUR_GITHUB_CLIENT_SECRET",  # From env
                    "redirect_uri": redirect_uri,
                },
            )
            tokens = response.json()

        # Get user info
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            user_info = response.json()

        # Get primary email
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            emails = response.json()
            primary_email = next((e for e in emails if e["primary"]), emails[0])

        # Find or create user
        account = (
            self.db.query(Account)
            .filter(
                Account.provider == "github",
                Account.provider_account_id == str(user_info["id"]),
            )
            .first()
        )

        if account:
            user = account.user
            account.access_token = tokens.get("access_token")
            self.db.commit()
        else:
            user = User(
                email=primary_email["email"],
                name=user_info.get("name") or user_info.get("login"),
                avatar_url=user_info.get("avatar_url"),
                email_verified=datetime.utcnow() if primary_email.get("verified") else None,
            )
            self.db.add(user)
            self.db.flush()

            account = Account(
                user_id=user.id,
                provider="github",
                provider_account_id=str(user_info["id"]),
                access_token=tokens.get("access_token"),
            )
            self.db.add(account)
            self.db.commit()
            self.db.refresh(user)

        return user

    # JWT Token Management

    def create_access_token(self, user_id: uuid.UUID) -> str:
        """Create JWT access token"""
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

        # Store in database for revocation support
        token_record = SessionToken(
            user_id=user_id, token=encoded_jwt, expires_at=expire
        )
        self.db.add(token_record)
        self.db.commit()

        return encoded_jwt

    def verify_token(self, token: str) -> Optional[uuid.UUID]:
        """Verify JWT token and return user_id"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = uuid.UUID(payload.get("sub"))

            # Check if token is in database and not expired
            token_record = (
                self.db.query(SessionToken)
                .filter(SessionToken.token == token)
                .first()
            )
            if not token_record or token_record.expires_at < datetime.utcnow():
                return None

            return user_id
        except (JWTError, ValueError):
            return None

    def revoke_token(self, token: str) -> None:
        """Revoke a token"""
        self.db.query(SessionToken).filter(SessionToken.token == token).delete()
        self.db.commit()
