# CompyMac Web UI Setup Guide

Multi-user authentication system with Google, GitHub, Apple OAuth, email/password registration, and session persistence.

## Quick Start

### 1. Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for local development)
- Python 3.11+ (for local development)

### 2. Clone and Configure

```bash
cd /home/user/compymac

# Copy environment files
cp server/.env.example server/.env
cp web/.env.example web/.env
```

### 3. Configure OAuth Providers

#### Google OAuth
1. Go to https://console.cloud.google.com/
2. Create new project
3. Enable Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URI: `http://localhost:3000/api/auth/callback/google`
6. Copy Client ID and Secret to `web/.env`:
   ```
   GOOGLE_CLIENT_ID=your-client-id
   GOOGLE_CLIENT_SECRET=your-client-secret
   ```

#### GitHub OAuth
1. Go to https://github.com/settings/developers
2. New OAuth App
3. Set callback URL: `http://localhost:3000/api/auth/callback/github`
4. Copy Client ID and Secret to `web/.env`:
   ```
   GITHUB_CLIENT_ID=your-client-id
   GITHUB_CLIENT_SECRET=your-client-secret
   ```

#### Apple Sign In (Optional)
1. Go to https://developer.apple.com/account/resources/identifiers/list/serviceId
2. Create new Service ID
3. Configure Sign in with Apple
4. Copy credentials to `web/.env`:
   ```
   APPLE_CLIENT_ID=your-client-id
   APPLE_CLIENT_SECRET=your-client-secret
   ```

### 4. Generate Secrets

```bash
# Generate AUTH_SECRET
openssl rand -base64 32

# Add to web/.env
AUTH_SECRET=<generated-secret>
```

### 5. Start Services

```bash
# Using Docker Compose (recommended)
docker-compose up -d

# Or manually:

# Terminal 1 - Database
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=compymac postgres:16

# Terminal 2 - Backend
cd server
pip install -r requirements.txt
uvicorn main:app --reload

# Terminal 3 - Frontend
cd web
npm install
npm run dev
```

### 6. Access

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Architecture

### Backend (FastAPI)

```
server/
├── main.py           # FastAPI app with WebSocket
├── database.py       # SQLAlchemy models
├── auth.py           # OAuth + JWT authentication
├── sessions.py       # Session management
└── requirements.txt
```

**Database Schema:**
- `users` - User accounts
- `accounts` - OAuth provider linkage
- `agent_sessions` - Agent sessions with isolated workspaces
- `conversations` - Chat message history
- `session_tokens` - JWT tokens for revocation

**API Endpoints:**
- `POST /api/auth/register` - Email/password registration
- `POST /api/auth/login` - Email/password login
- `POST /api/auth/oauth/google` - Google OAuth
- `POST /api/auth/oauth/github` - GitHub OAuth
- `POST /api/sessions` - Create session
- `GET /api/sessions` - List sessions
- `GET /api/sessions/{id}/messages` - Get conversation
- `WS /ws/{session_id}` - WebSocket for real-time chat

### Frontend (Next.js 15)

```
web/src/
├── app/
│   ├── auth/signin/page.tsx    # Sign-in page with OAuth + email
│   ├── page.tsx                # Main chat interface
│   └── api/auth/[...nextauth]/ # Auth.js API routes
├── lib/
│   └── auth.ts                 # Auth.js configuration
└── middleware.ts               # Route protection
```

**Features:**
- Google, GitHub OAuth sign-in
- Email/password registration and login
- Protected routes with middleware
- Session management UI
- Real-time WebSocket chat
- Conversation persistence

## Development

### Backend Development

```bash
cd server

# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest
```

### Frontend Development

```bash
cd web

# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build
npm start
```

## Database Management

### Create Tables

Tables are created automatically on first run. To manually create:

```bash
cd server
python -c "from database import Database; db = Database('postgresql://compymac:compymac@localhost:5432/compymac'); db.create_tables()"
```

### Reset Database

```bash
# Stop services
docker-compose down

# Remove volumes
docker volume rm compymac_postgres_data

# Restart
docker-compose up -d
```

## Production Deployment

### Environment Variables

**Backend (`server/.env`):**
```bash
DATABASE_URL=postgresql://user:pass@host:5432/db
WORKSPACES_ROOT=/var/compymac/workspaces
```

**Frontend (`web/.env`):**
```bash
DATABASE_URL=postgresql://user:pass@host:5432/db
AUTH_SECRET=<long-random-string>
NEXTAUTH_URL=https://your-domain.com

GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...

NEXT_PUBLIC_API_URL=https://api.your-domain.com
```

### Security Checklist

- [ ] Use strong DATABASE_URL with secure password
- [ ] Generate new AUTH_SECRET for production
- [ ] Configure OAuth redirect URIs for production domain
- [ ] Enable HTTPS (required for OAuth)
- [ ] Set up CORS properly in `server/main.py`
- [ ] Use environment-specific secrets (not .env files)
- [ ] Enable rate limiting on auth endpoints
- [ ] Set up database backups
- [ ] Configure session token expiration
- [ ] Enable PostgreSQL SSL connections

### Deployment Options

#### Option 1: Docker Compose
```bash
docker-compose -f docker-compose.prod.yml up -d
```

#### Option 2: Kubernetes
See `k8s/` directory for manifests

#### Option 3: Serverless
- Frontend: Vercel
- Backend: AWS Lambda + API Gateway
- Database: AWS RDS PostgreSQL

## Integration with CompyMac Agent

To integrate with the existing CompyMac agent:

```python
# In server/main.py WebSocket handler

from compymac.session import Session as CompyMacSession
from compymac.local_harness import LocalHarness

# Inside websocket_endpoint function:
workspace_path = session_manager.get_workspace_path(session_id, user_id)

# Create CompyMac session
compymac_session = CompyMacSession(
    workspace_path=str(workspace_path),
    # ... other config
)

harness = LocalHarness()

# Process user message through CompyMac
async for event in compymac_session.run(data['content'], harness):
    if event.type == "assistant_message":
        # Save to database
        session_manager.add_message(
            session_id, user_id, "assistant", event.content
        )
        # Send to WebSocket
        await websocket.send_json({
            "type": "message",
            "role": "assistant",
            "content": event.content,
            "created_at": datetime.utcnow().isoformat(),
        })
```

## Troubleshooting

### Database Connection Errors
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Check connection
psql postgresql://compymac:compymac@localhost:5432/compymac
```

### OAuth Errors
- Verify redirect URIs match exactly
- Check client ID/secret are correct
- Ensure HTTPS in production (OAuth requirement)
- Check provider console for error messages

### WebSocket Connection Fails
- Verify JWT token is valid
- Check CORS settings
- Ensure WebSocket URL uses `ws://` (or `wss://` in production)
- Check session exists and belongs to user

## Next Steps

1. **Run baseline tests**: Follow `IMPLEMENTATION_COMPLETE.md` Week 4-5 plan
2. **Integrate with CompyMac agent**: Connect WebSocket to actual agent execution
3. **Add file upload**: For workspace file management
4. **Add trace visualization**: Display TraceStore data in UI
5. **Add admin dashboard**: User management, usage stats
6. **Mobile responsive**: Optimize for mobile devices
7. **Dark mode**: Add theme switcher
8. **Notifications**: Email notifications for long-running tasks

## Support

- Issues: https://github.com/jhacksman/compymac/issues
- Documentation: See `docs/` directory
- Architecture: See `docs/WEB_UI_IMPLEMENTATION_PLAN.md`
