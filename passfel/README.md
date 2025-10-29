# PASSFEL - Personal ASSistant For Everyday Life

An AI-powered personal assistant that integrates seamlessly into daily life, providing a unified interface for information, productivity, and home automation.

## Vision

PASSFEL aims to be the comprehensive personal assistant that technology enthusiasts have dreamed about for years - a single, intelligent interface that handles all aspects of daily life through natural language interaction.

**Planning Document**: See [Planning-an-AI-Powered-Personal-Assistant.pdf](docs/Planning-an-AI-Powered-Personal-Assistant.pdf) for the complete project vision and requirements.

## Core Features

The following features are numbered 1-6 for tracking and implementation purposes:

### 1. Real-time News and Weather Updates
- **News Aggregation**: Personalized news briefings from trusted sources (RSS feeds, Ground.news)
- **Weather Forecasts**: Location-specific weather information and alerts (NOAA, Open-Meteo)
- **Research Documentation**: [DATA_SOURCES_RESEARCH.md](docs/DATA_SOURCES_RESEARCH.md)

### 2. Calendar Management, Reminders, and Tasks
- **Calendar Integration**: Google Calendar, Apple Calendar (CalDAV), or open-source solutions
- **Task Management**: Joplin, Notion, Obsidian integration
- **Reminders**: Set and receive timely reminders for important tasks
- **Research Documentation**: [CALENDAR_TASK_RESEARCH.md](docs/CALENDAR_TASK_RESEARCH.md)

### 3. On-the-fly Q&A and Research Capabilities
- **Knowledge Base**: Wikipedia API, arXiv API, Wikidata integration
- **RAG System**: Vector-based retrieval with pgvector
- **LLM Integration**: Venice.ai API for natural language understanding
- **Research Documentation**: [QA_RESEARCH.md](docs/QA_RESEARCH.md)

### 4. Financial Information (Stocks and Currency)
- **Stock Market Data**: yfinance (Yahoo Finance) for real-time stock prices
- **Cryptocurrency**: CoinGecko API for crypto prices and market data
- **Currency Exchange**: Frankfurter API for FX rates
- **Research Documentation**: [FINANCIAL_DATA_RESEARCH.md](docs/FINANCIAL_DATA_RESEARCH.md)

### 5. Smart Home Integration (Cameras, IoT Devices, Displays)
- **Home Automation**: Home Assistant, Apple HomeKit integration
- **Camera Access**: RTSP/ONVIF protocol support for security cameras
- **Device Control**: MQTT, Zigbee, Z-Wave protocol support
- **Casting**: Chromecast and AirPlay for multi-room display
- **Research Documentation**: [SMART_HOME_RESEARCH.md](docs/SMART_HOME_RESEARCH.md)

### 6. Multi-Device Access (Mobile, Desktop, TV)
- **Progressive Web App**: Primary access method for all devices
- **Voice Interface**: Push-to-talk and wake-word detection for hands-free operation
- **Mobile Apps**: Optional Capacitor wrapper for app store presence
- **Desktop Apps**: Electron or Tauri for native desktop experience
- **TV Display**: Chromecast/AirPlay casting integration, remote desktop fallback (Jump Desktop/VNC)
- **Research Documentation**: [MULTI_DEVICE_ACCESS_RESEARCH.md](docs/MULTI_DEVICE_ACCESS_RESEARCH.md)

## Architecture

### Backend
- AI/LLM integration for natural language processing
- API integrations for news, weather, financial data
- Smart home device communication (MQTT, REST APIs)
- Calendar and task storage (supporting multiple backends)

### Frontend
- Mobile app (native or web-based)
- Voice interface with wake-word detection
- Desktop client
- TV/display casting capabilities

### Integration Options
- **Calendar**: Google Calendar, Apple Calendar, or open-source solutions (Joplin, Obsidian)
- **Smart Home**: Home Assistant, Apple HomeKit, Google Home, or direct device APIs
- **News**: RSS feeds, news aggregator APIs
- **Weather**: OpenWeatherMap, NOAA
- **Financial**: Alpha Vantage, Yahoo Finance

## Design Principles

1. **Open Source First**: Prefer open-source solutions for privacy and control
2. **Privacy Focused**: Keep sensitive data local when possible
3. **Unified Interface**: All features accessible through one conversational interface
4. **Cross-Platform**: Seamless experience across all devices
5. **Extensible**: Modular architecture for easy feature additions

## Project Structure

```
passfel/
├── backend/          # Backend services and AI integration
├── frontend/         # User interfaces (mobile, web, desktop)
├── docs/            # Documentation and architecture diagrams
├── tests/           # Test suites
└── config/          # Configuration files and templates
```

## Getting Started

(To be added as development progresses)

## Roadmap

### Phase 1: Core Infrastructure
- Set up backend framework
- Implement basic AI/LLM integration
- Create simple conversational interface

### Phase 2: Information Services
- News aggregation
- Weather integration
- Financial data APIs
- General Q&A capabilities

### Phase 3: Productivity Features
- Calendar integration
- Reminder system
- Task management

### Phase 4: Smart Home Integration
- Camera feed access
- Device control
- Home automation hub integration

### Phase 5: Multi-Device Support
- Mobile app development
- Voice interface
- TV/display casting

## Contributing

(To be defined)

## License

(To be determined)

---

*"The assistant that takes care of the little things while you focus on what matters."*
