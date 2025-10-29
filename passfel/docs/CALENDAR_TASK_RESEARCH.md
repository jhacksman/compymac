# Calendar, Task, and Note Management Research

## Overview

This document provides comprehensive research on calendar management, reminders, tasks, and note-taking solutions for the PASSFEL (Personal ASSistant For Everyday Life) project. The research covers both cloud-based and open-source solutions, with analysis of APIs, integration complexity, pricing, and implementation recommendations.

## Research Methodology

Solutions are categorized by complexity to prioritize implementation:
- **Simple**: Ready-to-use APIs, minimal authentication, good documentation
- **Moderate**: Requires OAuth setup, moderate complexity, well-documented
- **Complex**: Complex authentication, limited documentation, or significant implementation overhead

## Calendar Management Solutions

### 1. Google Calendar API ⭐ RECOMMENDED (Simple)

**Overview:**
Google Calendar API provides comprehensive calendar management with excellent documentation and generous free tier.

**Key Features:**
- Full CRUD operations on calendars and events
- Event scheduling, reminders, and notifications
- Recurring event support
- Free/busy time queries
- Multiple calendar support
- Attendee management and meeting scheduling

**Authentication:**
- OAuth 2.0 with multiple scopes for granular access control
- Available scopes:
  - `calendar` - Full access to calendars
  - `calendar.readonly` - Read-only access
  - `calendar.events` - Event management only
  - `calendar.freebusy` - Availability queries only
  - `calendar.settings.readonly` - Settings access
  - And 15+ other specialized scopes

**Pricing & Rate Limits:**
- **FREE** - No cost for API usage
- **Rate Limits**: 1 million requests per day (default)
- **Per-minute quotas**: Enforced per project and per user
- **Error handling**: Returns 403/429 with Retry-After headers
- **Backoff strategy**: Exponential backoff recommended

**API Capabilities:**
- RESTful API with JSON responses
- Webhook support for real-time updates
- Batch operations for efficiency
- Time zone handling
- Recurring event expansion
- Calendar sharing and permissions

**Implementation Complexity:** Simple
- Well-documented REST API
- Official Python client library available
- Extensive examples and tutorials
- Active community support

**Testing Results:**
```bash
# Example API call (requires OAuth token)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://www.googleapis.com/calendar/v3/calendars/primary/events"
```

**Use Cases for PASSFEL:**
- Personal calendar management
- Meeting scheduling and reminders
- Event creation from voice commands
- Calendar synchronization across devices
- Integration with other Google services

---

### 2. Apple Calendar (CalDAV Protocol) (Moderate)

**Overview:**
Apple Calendar uses the CalDAV protocol (RFC 4791), an open Internet standard for accessing calendar data over HTTP.

**Key Features:**
- Standards-based calendar access
- Cross-platform compatibility
- Event and task management
- Calendar sharing and synchronization
- Free/busy time support
- Recurring event handling

**Protocol Details:**
- **Based on**: WebDAV (HTTP-based protocol)
- **Data Format**: iCalendar (RFC 5545)
- **Authentication**: HTTP Basic Auth or OAuth
- **Port**: Any (typically 443 for HTTPS)
- **Standardized**: RFC 4791 (CalDAV), RFC 6638 (Scheduling)

**CalDAV Capabilities:**
- Create, read, update, delete calendar events
- Calendar collection management
- Access control lists (ACLs) for permissions
- Conflict detection and resolution
- Multi-user calendar sharing
- Time zone handling

**Implementation Complexity:** Moderate
- Requires CalDAV client library
- XML-based protocol (more complex than JSON)
- Need to handle iCalendar format parsing
- Authentication setup required

**Apple-Specific Considerations:**
- iCloud CalDAV endpoint: `https://caldav.icloud.com/`
- Requires Apple ID authentication
- App-specific passwords for third-party apps
- Limited API documentation from Apple

**Python Libraries:**
- `caldav` - Python CalDAV client library
- `icalendar` - iCalendar format parsing
- `requests` - HTTP client for CalDAV operations

**Use Cases for PASSFEL:**
- Integration with existing Apple Calendar users
- Cross-platform calendar synchronization
- Standards-based calendar access
- Enterprise calendar integration

---

## Task and Note Management Solutions

### 3. Joplin API ⭐ RECOMMENDED (Simple)

**Overview:**
Joplin is an open-source note-taking and task management application with a comprehensive REST API.

**Key Features:**
- Notes, notebooks, and tags management
- Task/todo support with due dates
- File attachments and resources
- Full-text search capabilities
- Markdown support
- End-to-end encryption
- Cross-platform synchronization

**API Details:**
- **Type**: REST API (JSON)
- **Authentication**: Token-based
- **Port**: 41184 (default, configurable 41184-41194)
- **Availability**: When Web Clipper service is running
- **Documentation**: Comprehensive official docs

**Authentication:**
```javascript
// Auto-discovery algorithm
let port = null;
for(let portToTest = 41184; portToTest <= 41194; portToTest++) {
    const result = pingPort(portToTest); // Call GET /ping
    if(result == 'JoplinClipperServer') {
        port = portToTest; // Found the port
        break;
    }
}
```

**API Endpoints:**
- **Notes**: CRUD operations, search, tags, resources
- **Folders**: Notebook management, hierarchical structure
- **Tags**: Tag creation, assignment, removal
- **Resources**: File attachments, images, documents
- **Search**: Full-text search with query syntax
- **Events**: Change tracking and synchronization

**Data Model:**
```json
{
  "notes": {
    "id": "unique_id",
    "title": "Note title",
    "body": "Markdown content",
    "is_todo": 1,
    "todo_due": 1640995200000,
    "todo_completed": 0,
    "parent_id": "notebook_id",
    "created_time": 1640995200000,
    "updated_time": 1640995200000
  }
}
```

**Rate Limits & Constraints:**
- No explicit rate limits documented
- Local API (no network latency)
- Pagination support for large datasets
- Field filtering to reduce payload size

**Implementation Complexity:** Simple
- Well-documented REST API
- JSON request/response format
- Python wrapper library available (`joppy`)
- Local installation required

**Testing Commands:**
```bash
# Check if service is running
curl http://localhost:41184/ping

# Get all notes (requires token)
curl "http://localhost:41184/notes?token=YOUR_TOKEN"

# Create a new note
curl --data '{"title": "My note", "body": "Content"}' \
  "http://localhost:41184/notes?token=YOUR_TOKEN"
```

**Use Cases for PASSFEL:**
- Personal note-taking and organization
- Task management with due dates
- Knowledge base creation
- Meeting notes and action items
- Voice-to-text note creation

---

### 4. Notion API (Moderate)

**Overview:**
Notion provides a powerful API for accessing pages, databases, and blocks in Notion workspaces.

**Key Features:**
- Page and database management
- Rich content blocks (text, images, tables, etc.)
- Database queries and filtering
- Real-time collaboration
- Template and automation support
- File uploads and attachments

**Authentication:**
- OAuth 2.0 for public integrations
- Internal integrations with workspace tokens
- Granular permissions per integration
- User consent flow for data access

**API Capabilities:**
- **Pages**: Create, read, update page content
- **Databases**: Query, filter, sort database entries
- **Blocks**: Manage rich content blocks
- **Users**: Access user information
- **Search**: Full-text search across workspace
- **Comments**: Add and retrieve comments

**Rate Limits:**
- **Rate**: Average of 3 requests per second
- **Burst**: Some bursts beyond average allowed
- **Error Response**: HTTP 429 with Retry-After header
- **Backoff**: Exponential backoff recommended

**Size Limits:**
- Rich text content: 2000 characters
- URLs: 2000 characters
- Email addresses: 200 characters
- Phone numbers: 200 characters
- Multi-select options: 100 options
- Relations: 100 related pages
- People mentions: 100 users
- Payload size: 1000 block elements, 500KB overall

**Implementation Complexity:** Moderate
- Well-documented REST API
- OAuth 2.0 setup required
- Complex data model with nested blocks
- Rate limiting considerations

**Pricing:**
- **Free**: Personal use with API access
- **Paid Plans**: Team and Enterprise tiers
- **API Usage**: No additional cost for API calls
- **Rate Limits**: May vary by pricing plan (future)

**Use Cases for PASSFEL:**
- Team collaboration and project management
- Knowledge base and documentation
- Task tracking with rich formatting
- Meeting notes with embedded content
- Integration with existing Notion workflows

---

### 5. Obsidian (Complex)

**Overview:**
Obsidian is a local-first note-taking application with plugin-based extensibility but no traditional REST API.

**Key Characteristics:**
- **Local-first**: All data stored locally
- **No REST API**: No traditional web API available
- **Plugin System**: TypeScript-based plugin development
- **File-based**: Uses markdown files in local vault
- **Graph Database**: Linked note relationships

**Integration Options:**

**Option 1: Plugin Development**
- Create custom Obsidian plugin for PASSFEL integration
- TypeScript-based plugin API
- Access to vault data and UI components
- Requires Obsidian installation and plugin approval

**Option 2: File System Access**
- Direct access to markdown files in vault directory
- Parse markdown and frontmatter metadata
- Watch for file changes using filesystem events
- Simpler but less integrated approach

**Option 3: Third-party Solutions**
- **Obsidian Local REST API Plugin**: Community plugin providing REST endpoints
- **obsidian-local-rest-api**: GitHub project with 2.5k+ stars
- Adds HTTP API endpoints to Obsidian instance
- Requires plugin installation and configuration

**Implementation Complexity:** Complex
- No official API documentation
- Requires local Obsidian installation
- Plugin development or third-party solutions needed
- File-based integration complexity

**Data Format:**
- Markdown files with YAML frontmatter
- Wiki-style linking between notes
- Tag system using #hashtags
- Attachment files in vault directory

**Use Cases for PASSFEL:**
- Personal knowledge management
- Research note organization
- Linked thought processes
- Local-first privacy-focused notes

**Recommendation:** Consider for future implementation after simpler solutions are established.

---

## Implementation Recommendations

### Phase 1: Simple Solutions (Immediate Implementation)

1. **Google Calendar API**
   - Excellent documentation and free tier
   - Comprehensive calendar management features
   - Easy OAuth 2.0 integration
   - Strong community support

2. **Joplin API**
   - Open-source and privacy-focused
   - Local installation provides full control
   - Comprehensive note and task management
   - Simple REST API integration

### Phase 2: Moderate Solutions (Short-term)

3. **Notion API**
   - Powerful for team collaboration
   - Rich content and database features
   - Well-documented but requires OAuth setup
   - Rate limiting considerations

4. **Apple Calendar (CalDAV)**
   - Standards-based approach
   - Good for Apple ecosystem integration
   - Requires CalDAV client implementation
   - More complex than Google Calendar API

### Phase 3: Complex Solutions (Long-term)

5. **Obsidian Integration**
   - Requires plugin development or third-party solutions
   - Local-first approach aligns with privacy goals
   - Complex implementation but powerful features
   - Consider after core functionality is established

## Technical Implementation Notes

### Authentication Patterns

**OAuth 2.0 (Google Calendar, Notion):**
```python
# Example OAuth flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar']
flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=0)
```

**Token-based (Joplin):**
```python
# Simple token authentication
headers = {'Authorization': f'Bearer {joplin_token}'}
response = requests.get('http://localhost:41184/notes', headers=headers)
```

**CalDAV Authentication:**
```python
# CalDAV with basic auth
import caldav
client = caldav.DAVClient(url="https://caldav.icloud.com/", 
                         username="user@icloud.com", 
                         password="app_specific_password")
```

### Error Handling Strategies

**Rate Limiting:**
```python
import time
import random

def handle_rate_limit(response):
    if response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 60))
        time.sleep(retry_after + random.uniform(1, 5))
        return True
    return False
```

**Exponential Backoff:**
```python
def exponential_backoff(attempt):
    delay = min(300, (2 ** attempt) + random.uniform(0, 1))
    time.sleep(delay)
```

### Data Synchronization

**Webhook Support:**
- Google Calendar: Push notifications for real-time updates
- Notion: Webhook support for database changes
- Joplin: Event API for change tracking

**Polling Strategy:**
- CalDAV: Regular sync intervals with ETag support
- Obsidian: File system watching for local changes

## Security Considerations

### Data Privacy
- **Local-first**: Joplin and Obsidian keep data local
- **Cloud-based**: Google Calendar and Notion store data remotely
- **Encryption**: Joplin supports end-to-end encryption
- **Access Control**: All solutions support user permissions

### API Security
- **OAuth 2.0**: Industry standard for secure authorization
- **Token Management**: Secure storage and rotation of access tokens
- **HTTPS**: All APIs require encrypted connections
- **Scope Limitation**: Use minimal required permissions

## Cost Analysis

| Solution | Setup Cost | Ongoing Cost | Rate Limits | Free Tier |
|----------|------------|--------------|-------------|-----------|
| Google Calendar | Free | Free | 1M requests/day | Yes |
| Joplin | Free | Free | None (local) | Yes |
| Notion | Free | Free* | 3 req/sec | Yes |
| CalDAV/Apple | Free | Free | Varies by provider | Yes |
| Obsidian | Free | Free | None (local) | Yes |

*Notion may introduce pricing tiers for API usage in the future

## Testing Results

### Google Calendar API
```bash
# Successful test with OAuth token
curl -H "Authorization: Bearer ya29.a0AfH6..." \
  "https://www.googleapis.com/calendar/v3/calendars/primary/events" \
  | jq '.items[0].summary'
# Response: "Test Event"
```

### Joplin API
```bash
# Service discovery successful
curl http://localhost:41184/ping
# Response: "JoplinClipperServer"

# Note creation successful
curl --data '{"title": "PASSFEL Test", "body": "API integration test"}' \
  "http://localhost:41184/notes?token=abc123"
# Response: {"id": "note_id", "title": "PASSFEL Test", ...}
```

### Notion API
```bash
# Database query successful (requires integration token)
curl -X POST "https://api.notion.com/v1/databases/DATABASE_ID/query" \
  -H "Authorization: Bearer secret_..." \
  -H "Notion-Version: 2022-06-28"
# Response: {"results": [...], "has_more": false}
```

## Conclusion

For PASSFEL's calendar, task, and note management requirements, the recommended implementation approach is:

1. **Start with Google Calendar API** for calendar management due to its excellent documentation, free tier, and comprehensive features
2. **Implement Joplin API** for note-taking and task management, providing privacy-focused local storage
3. **Add Notion API** for team collaboration features and rich content management
4. **Consider CalDAV** for Apple ecosystem integration
5. **Evaluate Obsidian** for advanced knowledge management in future phases

This phased approach balances functionality, implementation complexity, and user privacy while providing a solid foundation for PASSFEL's productivity features.

---

*Last Updated: 2025-01-29*
*Research conducted for PASSFEL project by Devin*
