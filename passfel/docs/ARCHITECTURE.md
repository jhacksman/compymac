# PASSFEL Architecture

## Overview

PASSFEL (Personal ASSistant For Everyday Life) is designed as a modular, extensible AI-powered assistant with a focus on privacy, open-source solutions, and seamless multi-device integration.

## System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interfaces                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Mobile  │  │  Voice   │  │ Desktop  │  │   TV     │   │
│  │   App    │  │Interface │  │  Client  │  │ Display  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┘
                          │
        ┌─────────────────▼─────────────────┐
        │      API Gateway / Router         │
        └─────────────────┬─────────────────┘
                          │
        ┌─────────────────▼─────────────────┐
        │     Core Assistant Engine         │
        │  ┌─────────────────────────────┐  │
        │  │   Natural Language          │  │
        │  │   Processing (LLM)          │  │
        │  └─────────────┬───────────────┘  │
        │                │                   │
        │  ┌─────────────▼───────────────┐  │
        │  │   Intent Recognition &      │  │
        │  │   Context Management        │  │
        │  └─────────────┬───────────────┘  │
        └────────────────┼───────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                  │
┌───────▼────────┐              ┌─────────▼──────────┐
│   Information  │              │   Action           │
│   Services     │              │   Services         │
│                │              │                    │
│ • News         │              │ • Calendar Mgmt    │
│ • Weather      │              │ • Reminders        │
│ • Financial    │              │ • Task Management  │
│ • Q&A/Research │              │ • Smart Home       │
└────────────────┘              └────────────────────┘
```

## Core Components

### 1. Assistant Engine

The brain of PASSFEL, responsible for:
- Natural language understanding via LLM integration
- Intent recognition and classification
- Context management across conversations
- Response generation
- Multi-turn dialogue handling

**Technology Options:**
- OpenAI API
- Anthropic Claude
- Local LLM (Llama, Mistral)
- Venice.ai API (as used in CompyMac)

### 2. Information Services Layer

#### News Service
- RSS feed aggregation
- News API integration
- Article summarization
- Personalized news filtering

**APIs:**
- NewsAPI
- RSS feeds from trusted sources
- Custom aggregation

#### Weather Service
- Current conditions
- Forecasts
- Weather alerts
- Location-based queries

**APIs:**
- OpenWeatherMap
- NOAA
- Weather.gov

#### Financial Service
- Stock quotes
- Market indices
- Currency exchange rates
- Portfolio tracking (future)

**APIs:**
- Alpha Vantage
- Yahoo Finance
- IEX Cloud

#### Q&A/Research Service
- Web search integration
- Knowledge base queries
- Multi-step research
- Source citation

**Implementation:**
- Web search APIs (Bing, Google)
- Wikipedia API
- LLM-powered summarization

### 3. Productivity Services Layer

#### Calendar Management
- Event viewing and creation
- Schedule queries
- Meeting scheduling
- Recurring events

**Backend Options:**
- Google Calendar API
- Apple Calendar (CalDAV)
- Joplin (open-source)
- Custom database

#### Reminder System
- Time-based reminders
- Location-based reminders (future)
- Recurring reminders
- Smart notifications

**Storage:**
- Integrated with calendar backend
- Custom reminder database
- Apple Reminders API

#### Task Management
- To-do list management
- Task prioritization
- Due date tracking
- Task categories/tags

**Backend Options:**
- Joplin with agenda plugin
- Obsidian with plugins
- Custom task database
- Google Tasks / Apple Reminders

### 4. Smart Home Integration Layer

#### Camera Service
- RTSP stream access
- Live feed display
- Multi-camera support
- Recording playback (future)

**Protocols:**
- RTSP
- ONVIF
- Manufacturer-specific APIs

#### Device Control
- Light control
- Thermostat management
- Smart plug control
- Lock control
- Sensor monitoring

**Integration Options:**
- Home Assistant (preferred - open source)
- Apple HomeKit
- Google Home
- Amazon Alexa
- Direct device APIs (MQTT, REST)

#### Display Casting
- Camera feed to TV
- Dashboard display
- Information cards
- Multi-room support

**Technologies:**
- AirPlay (Apple ecosystem)
- Chromecast (Google ecosystem)
- VNC/Remote Desktop
- Custom streaming solution

### 5. Multi-Device Interface Layer

#### Mobile App
- Native iOS/Android app OR
- Progressive Web App (PWA)
- Voice input
- Text chat interface
- Rich media display

**Technologies:**
- React Native / Flutter (native)
- React / Vue (PWA)
- WebRTC for voice

#### Voice Interface
- Wake word detection
- Speech-to-text
- Text-to-speech
- Continuous conversation

**Technologies:**
- Porcupine (wake word)
- Whisper (STT)
- ElevenLabs / Coqui TTS (TTS)

#### Desktop Client
- System tray integration
- Quick access shortcuts
- Full-featured interface
- Notification support

**Technologies:**
- Electron
- Native (Swift for macOS)

#### TV Display
- Large screen UI
- Remote control support
- Voice control
- Auto-display triggers

**Technologies:**
- Web-based UI
- Apple TV app
- Android TV app
- Raspberry Pi + browser

## Data Flow

### Typical User Interaction

1. **User Input**: User speaks or types a query
2. **Interface Layer**: Captures input, sends to API Gateway
3. **Assistant Engine**: 
   - Receives query
   - Analyzes intent using LLM
   - Retrieves relevant context
   - Determines required services
4. **Service Layer**: 
   - Executes required actions
   - Fetches information
   - Controls devices
5. **Response Generation**:
   - Aggregates results
   - Formats response
   - Generates natural language
6. **Interface Layer**: 
   - Displays/speaks response
   - Shows rich media if needed

### Example: "What's on my schedule today?"

```
User → Mobile App → API Gateway → Assistant Engine
                                        ↓
                                  Intent: calendar_query
                                  Context: today's date
                                        ↓
                                  Calendar Service
                                        ↓
                                  Fetch today's events
                                        ↓
                                  Format response
                                        ↓
Mobile App ← API Gateway ← "You have 3 events today:
                            9 AM - Team meeting
                            1 PM - Lunch with Alice
                            3 PM - Project review"
```

### Example: "Show me the front door camera"

```
User → Mobile App → API Gateway → Assistant Engine
                                        ↓
                                  Intent: camera_view
                                  Device: front_door
                                        ↓
                                  Smart Home Service
                                        ↓
                                  Retrieve RTSP stream URL
                                        ↓
                                  Stream to display
                                        ↓
Mobile App ← Video Stream ← Camera feed displayed
```

## Technology Stack

### Backend
- **Language**: Python (for AI/ML integration) or Node.js
- **Framework**: FastAPI / Flask (Python) or Express (Node.js)
- **Database**: PostgreSQL (structured data) + Vector DB (embeddings)
- **Message Queue**: Redis / RabbitMQ (for async tasks)
- **Cache**: Redis

### Frontend
- **Mobile**: React Native / Flutter / PWA
- **Desktop**: Electron / Native (Swift for macOS)
- **Web**: React / Vue.js
- **Voice**: WebRTC, Whisper, Porcupine

### AI/ML
- **LLM**: OpenAI / Anthropic / Local models
- **Embeddings**: Sentence Transformers / OpenAI
- **STT**: Whisper / Google Speech API
- **TTS**: ElevenLabs / Coqui TTS

### Smart Home
- **Hub**: Home Assistant (preferred)
- **Protocols**: MQTT, REST, WebSocket
- **Camera**: RTSP, ONVIF

### DevOps
- **Containerization**: Docker
- **Orchestration**: Docker Compose / Kubernetes (if needed)
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus + Grafana

## Security & Privacy

### Data Protection
- End-to-end encryption for sensitive data
- Local storage options for privacy-sensitive information
- Secure API key management
- User authentication and authorization

### Privacy Considerations
- Option to use local LLMs instead of cloud APIs
- Self-hosted backend option
- Minimal data retention
- User control over data sharing

### Smart Home Security
- Secure camera stream access
- Device authentication
- Network isolation
- Regular security updates

## Scalability

### Single User Deployment
- Lightweight backend on local server or cloud VM
- SQLite or PostgreSQL database
- Direct API integrations

### Multi-User Deployment (Future)
- User authentication and isolation
- Shared infrastructure
- Load balancing
- Distributed caching

## Development Phases

### Phase 1: Foundation
- Core assistant engine with LLM integration
- Basic conversational interface
- Simple text-based UI

### Phase 2: Information Services
- News, weather, financial APIs
- Q&A capabilities
- Response formatting

### Phase 3: Productivity
- Calendar integration (start with one backend)
- Reminder system
- Task management

### Phase 4: Smart Home
- Home Assistant integration
- Camera feed access
- Device control

### Phase 5: Multi-Device
- Mobile app
- Voice interface
- TV display casting

### Phase 6: Polish & Optimization
- Performance tuning
- UI/UX improvements
- Advanced features
- Proactive notifications

## Integration Patterns

### API Integration Pattern
```python
class ServiceInterface:
    def query(self, params: dict) -> dict:
        """Standard interface for all services"""
        pass
    
    def validate_params(self, params: dict) -> bool:
        """Validate input parameters"""
        pass
    
    def format_response(self, data: dict) -> str:
        """Format response for user"""
        pass
```

### Plugin Architecture
- Services as plugins
- Dynamic loading
- Configuration-based enabling/disabling
- Standardized interfaces

## Configuration Management

### Environment-Based Config
- Development, staging, production environments
- API keys in environment variables
- Feature flags
- Service endpoint configuration

### User Preferences
- Personalization settings
- Service preferences (which calendar, which news sources)
- Notification preferences
- Privacy settings

## Monitoring & Logging

### Metrics
- Request/response times
- API call success rates
- User interaction patterns
- Error rates

### Logging
- Structured logging
- Log levels (debug, info, warning, error)
- Log aggregation
- Privacy-aware logging (no sensitive data)

## Future Enhancements

- Proactive notifications and suggestions
- Learning user preferences over time
- Multi-user support with shared calendars
- Advanced home automation scenarios
- Integration with more services (email, messaging, etc.)
- Voice biometrics for security
- Offline mode with local processing
