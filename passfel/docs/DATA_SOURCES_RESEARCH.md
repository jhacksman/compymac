# Free Real-Time Weather and News Data Sources Research

## Executive Summary

This document provides comprehensive research on free, real-time weather and news data sources for the PASSFEL project. Sources are categorized by implementation complexity to help prioritize development.

## Weather Data Sources

### ✅ SIMPLE - Recommended for Initial Implementation

#### 1. NOAA/NWS Weather API (weather.gov)
**Complexity:** Simple  
**Cost:** Completely free, no API key required  
**Coverage:** United States only  
**Rate Limits:** Generous (not publicly disclosed, but allows typical use)

**Why Simple:**
- Official US government API
- No authentication required (just need User-Agent header)
- Well-documented REST API
- JSON/GeoJSON responses
- Reliable and stable

**Key Features:**
- Current weather conditions
- Hourly forecasts (48 hours)
- 7-day forecasts
- Weather alerts and warnings
- Observation station data
- Radar and satellite data
- Marine forecasts

**API Endpoints:**
- `/points/{lat},{lon}` - Get forecast URLs for a location
- `/gridpoints/{office}/{gridX},{gridY}/forecast` - 7-day forecast
- `/gridpoints/{office}/{gridX},{gridY}/forecast/hourly` - Hourly forecast
- `/alerts/active` - Active weather alerts
- `/stations/{stationId}/observations/latest` - Current observations

**Documentation:** https://www.weather.gov/documentation/services-web-api

**Example Usage:**
```bash
# Get forecast for a location (San Francisco)
curl -H "User-Agent: (PASSFEL, contact@example.com)" \
  https://api.weather.gov/points/37.7749,-122.4194

# Get current observations
curl -H "User-Agent: (PASSFEL, contact@example.com)" \
  https://api.weather.gov/stations/KSFO/observations/latest
```

**Recommendation:** **START HERE** - Best option for US-based users. Simple, reliable, no API key hassle.

---

#### 2. Open-Meteo
**Complexity:** Simple  
**Cost:** Free for non-commercial use, no API key required  
**Coverage:** Global  
**Rate Limits:** 10,000 requests/day, 5,000 requests/hour

**Why Simple:**
- No API key required
- No registration needed
- Simple REST API
- Well-documented
- Open-source

**Key Features:**
- Current weather
- 16-day forecast
- Hourly forecast
- Historical weather data (1940-present)
- Air quality data
- Marine weather
- Multiple weather models

**API Endpoints:**
- `/v1/forecast` - Weather forecast
- `/v1/marine` - Marine weather
- `/v1/air-quality` - Air quality
- `/v1/historical` - Historical data

**Documentation:** https://open-meteo.com/en/docs

**Example Usage:**
```bash
# Get current weather and forecast
curl "https://api.open-meteo.com/v1/forecast?latitude=37.7749&longitude=-122.4194&current=temperature_2m,relative_humidity_2m,weather_code&hourly=temperature_2m,precipitation&daily=temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&timezone=America/Los_Angeles"
```

**Recommendation:** **EXCELLENT ALTERNATIVE** - Best for global coverage, no API key needed.

---

### ⚠️ MODERATE - Consider for Future Enhancement

#### 3. OpenWeatherMap ⭐ (Explicitly mentioned in PDF)
**Complexity:** Moderate  
**Cost:** Free tier: 1,000 calls/day  
**Coverage:** Global  
**Rate Limits:** 60 calls/minute, 1,000 calls/day (free tier)

**Why Moderate:**
- Requires API key (free signup at https://openweathermap.org/appid)
- Free tier has limitations but sufficient for personal use
- More complex pricing structure for commercial use

**Key Features:**
- Current weather data (temperature, humidity, pressure, wind, clouds, precipitation)
- 5-day/3-hour forecast (free tier)
- 8-day daily forecast (paid)
- Weather alerts and warnings
- Historical data (paid)
- Weather maps and layers
- Air pollution data
- UV index
- One Call API 3.0 (combines current, forecast, historical in one call)

**API Endpoints:**
- `/data/2.5/weather` - Current weather data
- `/data/2.5/forecast` - 5-day/3-hour forecast
- `/data/2.5/onecall` - One Call API (current + forecast + alerts)
- `/data/2.5/air_pollution` - Air quality data
- `/data/2.5/uvi` - UV index

**Documentation:** https://openweathermap.org/api

**Example Usage:**
```bash
# Get current weather (requires API key)
curl "https://api.openweathermap.org/data/2.5/weather?lat=37.7749&lon=-122.4194&appid=YOUR_API_KEY&units=imperial"

# Get 5-day forecast
curl "https://api.openweathermap.org/data/2.5/forecast?lat=37.7749&lon=-122.4194&appid=YOUR_API_KEY&units=imperial"

# One Call API 3.0 (current + forecast + alerts)
curl "https://api.openweathermap.org/data/3.0/onecall?lat=37.7749&lon=-122.4194&appid=YOUR_API_KEY&units=imperial"
```

**Python Integration:**
```python
import requests

class OpenWeatherMapClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"
    
    def get_current_weather(self, lat, lon, units="imperial"):
        """Get current weather for coordinates"""
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": units
        }
        response = requests.get(f"{self.base_url}/weather", params=params)
        return response.json()
    
    def get_forecast(self, lat, lon, units="imperial"):
        """Get 5-day/3-hour forecast"""
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": units
        }
        response = requests.get(f"{self.base_url}/forecast", params=params)
        return response.json()

# Usage
client = OpenWeatherMapClient("YOUR_API_KEY")
weather = client.get_current_weather(37.7749, -122.4194)
print(f"Temperature: {weather['main']['temp']}°F")
print(f"Conditions: {weather['weather'][0]['description']}")
```

**Recommendation:** **CONSIDER AS PRIMARY OPTION** - The PDF explicitly mentions OpenWeatherMap alongside NOAA. While it requires an API key, the free tier (1,000 calls/day) is sufficient for personal use and provides excellent global coverage with comprehensive weather data. Good alternative to NOAA for non-US locations or when you need features like air quality data.

---

#### 4. Weatherstack
**Complexity:** Moderate  
**Cost:** Free tier: 1,000 calls/month  
**Coverage:** Global  
**Rate Limits:** 1,000 calls/month (free tier)

**Why Moderate:**
- Requires API key
- Very limited free tier (only ~33 calls/day)
- Real-time data only on free tier

**Recommendation:** Too limited for free tier, skip for now.

---

### ❌ COMPLEX - Defer for Future

#### 5. Tomorrow.io
**Complexity:** Complex  
**Cost:** Free tier with limitations  
**Coverage:** Global  
**Rate Limits:** Limited on free tier

**Why Complex:**
- Requires API key and registration
- Complex pricing tiers
- Limited free tier
- More advanced features require payment

**Recommendation:** Skip for initial implementation.

---

#### 6. AccuWeather
**Complexity:** Complex  
**Cost:** Limited free tier (50 calls/day)  
**Coverage:** Global  
**Rate Limits:** 50 calls/day (free tier)

**Why Complex:**
- Requires API key
- Very restrictive free tier
- Complex terms of service
- Note: Free tier was recently reduced/eliminated

**Recommendation:** Skip - too restrictive.

---

## News Data Sources

### ✅ SIMPLE - Recommended for Initial Implementation

#### 1. RSS Feeds (Direct)
**Complexity:** Very Simple  
**Cost:** Free  
**Coverage:** Depends on source  
**Rate Limits:** None (standard HTTP)

**Why Simple:**
- No API key required
- Standard XML format
- Easy to parse
- Widely supported
- No rate limits

**Popular News RSS Feeds:**

**Major News Sources:**
- CNN: http://rss.cnn.com/rss/cnn_topstories.rss
- BBC News: http://feeds.bbci.co.uk/news/rss.xml
- Reuters: https://www.reutersagency.com/feed/
- NPR: https://feeds.npr.org/1001/rss.xml
- Associated Press: https://apnews.com/apf-topnews (RSS available)
- The Guardian: https://www.theguardian.com/world/rss
- New York Times: https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml
- Washington Post: https://feeds.washingtonpost.com/rss/world

**Tech News:**
- TechCrunch: https://techcrunch.com/feed/
- Ars Technica: https://feeds.arstechnica.com/arstechnica/index
- The Verge: https://www.theverge.com/rss/index.xml
- Hacker News: https://news.ycombinator.com/rss
- Wired: https://www.wired.com/feed/rss

**Business/Finance:**
- Bloomberg: https://www.bloomberg.com/feed/podcast/etf-report.xml
- CNBC: https://www.cnbc.com/id/100003114/device/rss/rss.html
- MarketWatch: http://feeds.marketwatch.com/marketwatch/topstories/

**Parsing Libraries:**
- Python: `feedparser` (simple, well-maintained)
- Node.js: `rss-parser`
- Go: `gofeed`

**Example Usage (Python):**
```python
import feedparser

# Parse CNN top stories
feed = feedparser.parse('http://rss.cnn.com/rss/cnn_topstories.rss')

for entry in feed.entries[:5]:
    print(f"Title: {entry.title}")
    print(f"Link: {entry.link}")
    print(f"Published: {entry.published}")
    print(f"Summary: {entry.summary}")
    print("---")
```

**Recommendation:** **START HERE** - Simplest approach, no API keys, no rate limits.

---

#### 2. RSSHub
**Complexity:** Simple  
**Cost:** Free (self-hosted or public instance)  
**Coverage:** Global (generates RSS from any website)  
**Rate Limits:** Depends on instance

**Why Simple:**
- Generates RSS feeds from websites that don't have them
- Open-source
- Can self-host or use public instance
- No API key required

**Key Features:**
- Generates RSS from social media, news sites, blogs
- Supports 1000+ sources
- Active community

**Documentation:** https://docs.rsshub.app/

**Recommendation:** Great for sources that don't have native RSS feeds.

---

#### 3. Ground.news (Web Scraping)
**Complexity:** Moderate  
**Cost:** Free (with permission for personal use)  
**Coverage:** Global news aggregation  
**Rate Limits:** None (polite scraping with delays)

**Why Moderate:**
- Requires web scraping (Selenium/headless Chrome)
- No official API available
- Need to implement proper scraping etiquette
- User has permission for personal use only (not for resale)

**Key Features:**
- News story aggregation from 50,000+ sources
- **Political bias analysis** - Shows Left/Center/Right coverage percentages
- **Source diversity metrics** - Total sources covering each story
- **Bias distribution visualization** - See which outlets cover which stories
- **Blindspot detection** - Stories disproportionately covered by one side
- Article listings with source names, bias labels, and timestamps
- Topic categorization and tagging
- Geographic source distribution

**Data Available Without Login:**
- Story titles, summaries, and URLs
- Political bias distribution (Left/Center/Right percentages)
- Total source count and breakdown by bias (e.g., "77 Left, 165 Center, 27 Right")
- Individual article listings with:
  - Source name and logo
  - Source bias label (Left, Lean Left, Center, Lean Right, Right)
  - Article headline and summary
  - Publication timestamp and location
  - Link to original article
- Similar topics and related stories
- Story metadata (publish date, update time, location)

**Data Requiring Premium/Vantage Subscription:**
- Factuality ratings for sources (requires Premium)
- Ownership data for news organizations (requires Vantage)
- Podcast mentions and timestamps (requires Vantage)
- Full historical data access

**Implementation Approach:**
- Use Selenium with headless Chrome for scraping
- Implement polite delays between requests (2-3 seconds minimum)
- Cache results to minimize requests
- Use realistic User-Agent headers
- Focus on homepage and story detail pages
- Parse HTML structure for bias metrics and source lists

**Example Data Structure:**
```python
{
    "story_id": "f2bf3034-bd03-4e59-adb6-1770ed4f7e0e",
    "title": "States sue Trump administration to keep SNAP benefits...",
    "summary": "A coalition of 25 states and DC sued to block...",
    "url": "https://ground.news/article/f2bf3034-bd03-4e59-adb6-1770ed4f7e0e",
    "published": "2025-10-28T...",
    "updated": "2025-10-29T...",
    "total_sources": 374,
    "bias_distribution": {
        "left": 77,
        "center": 165,
        "right": 27,
        "left_percent": 21,
        "center_percent": 61,
        "right_percent": 7
    },
    "articles": [
        {
            "source": "Fox News",
            "bias": "Right",
            "headline": "States sue Trump admin over billions...",
            "url": "https://www.foxnews.com/politics/...",
            "published": "2025-10-29T...",
            "location": "New York, United States"
        },
        ...
    ],
    "topics": ["SNAP", "Donald Trump", "Government Shutdown"]
}
```

**Robots.txt Compliance:**
- Checked: https://ground.news/robots.txt
- Most paths allowed except `/mediaopoly`
- Respectful scraping is permitted

**Recommendation:** **EXCELLENT FOR BIAS ANALYSIS** - Unique value proposition with political bias metrics and source diversity data. Implement with Selenium for personal use. Provides context that RSS feeds alone cannot offer.

**Use Cases:**
- Identify media bias in news coverage
- Detect "blindspot" stories (covered by only one side)
- Track source diversity across political spectrum
- Aggregate multiple perspectives on same story
- Analyze geographic distribution of news sources

---

### ⚠️ MODERATE - Consider for Future Enhancement

#### 3. NewsAPI.org
**Complexity:** Moderate  
**Cost:** Free tier: 100 requests/day  
**Coverage:** Global (80,000+ sources)  
**Rate Limits:** 100 requests/day (free tier)

**Why Moderate:**
- Requires API key
- Limited free tier (only 100 calls/day)
- Free tier restricted to development use only
- Cannot use in production without paid plan

**Key Features:**
- Search news articles
- Top headlines by country/category
- Filter by source, date, language
- JSON responses

**Documentation:** https://newsapi.org/docs

**Recommendation:** Good for prototyping, but too limited for production use on free tier.

---

#### 4. NewsData.io
**Complexity:** Moderate  
**Cost:** Free tier: 200 requests/day  
**Coverage:** Global  
**Rate Limits:** 200 requests/day (free tier)

**Why Moderate:**
- Requires API key
- Limited free tier
- Historical data requires paid plan

**Recommendation:** Similar to NewsAPI, consider for future if RSS feeds insufficient.

---

#### 5. GNews API
**Complexity:** Moderate  
**Cost:** Free tier: 100 requests/day  
**Coverage:** Global  
**Rate Limits:** 100 requests/day (free tier)

**Why Moderate:**
- Requires API key
- Limited free tier
- Similar limitations to NewsAPI

**Recommendation:** Alternative to NewsAPI with similar limitations.

---

### ❌ COMPLEX - Defer for Future

#### 6. Bing News Search API
**Complexity:** Complex  
**Cost:** Free tier with Azure account  
**Coverage:** Global  
**Rate Limits:** 1,000 transactions/month (free tier)

**Why Complex:**
- Requires Azure account
- Complex setup
- Limited free tier
- Overkill for basic news aggregation

**Recommendation:** Skip - too complex for initial implementation.

---

## Implementation Recommendations

### Phase 1: Start Simple (Recommended for Immediate Implementation)

**Weather:**
1. **Primary:** NOAA/NWS API (for US users)
2. **Secondary:** Open-Meteo (for global coverage or as fallback)

**News:**
1. **Primary:** Direct RSS feeds from major news sources
2. **Use:** Python `feedparser` library or similar

**Why This Approach:**
- No API keys required
- No rate limit concerns
- Simple to implement
- Reliable and stable
- Can be implemented in a few hours

**Implementation Steps:**
1. Create a list of RSS feed URLs for desired news sources
2. Use feedparser to fetch and parse feeds
3. Cache results to avoid excessive requests
4. For weather: Implement NOAA API client with proper User-Agent
5. Add Open-Meteo as fallback for non-US locations

---

### Phase 2: Enhance (Future Consideration)

**If RSS feeds prove insufficient:**
- Add NewsAPI.org for search capabilities
- Consider paid tier if budget allows

**If weather needs expand:**
- Add OpenWeatherMap for additional features
- Consider weather maps and radar

---

## Testing Recommendations

### Weather APIs to Test First:
1. **NOAA API** - Test with US locations
   ```bash
   curl -H "User-Agent: (PASSFEL, test@example.com)" \
     "https://api.weather.gov/points/37.7749,-122.4194"
   ```

2. **Open-Meteo** - Test with any location
   ```bash
   curl "https://api.open-meteo.com/v1/forecast?latitude=37.7749&longitude=-122.4194&current=temperature_2m,weather_code&temperature_unit=fahrenheit"
   ```

### News Sources to Test First:
1. **CNN RSS Feed**
   ```bash
   curl "http://rss.cnn.com/rss/cnn_topstories.rss"
   ```

2. **BBC News RSS Feed**
   ```bash
   curl "http://feeds.bbci.co.uk/news/rss.xml"
   ```

---

## Summary Table

### Weather APIs

| Source | Complexity | Cost | API Key | Rate Limit | Coverage | Recommendation |
|--------|-----------|------|---------|------------|----------|----------------|
| NOAA/NWS | Simple | Free | No | Generous | US Only | ✅ Start Here (US) |
| Open-Meteo | Simple | Free | No | 10k/day | Global | ✅ Start Here (Global) |
| OpenWeatherMap | Moderate | Free tier | Yes | 1k/day | Global | ⚠️ Future |
| Weatherstack | Moderate | Free tier | Yes | 1k/month | Global | ⚠️ Skip (too limited) |
| Tomorrow.io | Complex | Limited free | Yes | Limited | Global | ❌ Defer |
| AccuWeather | Complex | Limited free | Yes | 50/day | Global | ❌ Skip |

### News Sources

| Source | Complexity | Cost | API Key | Rate Limit | Coverage | Recommendation |
|--------|-----------|------|---------|------------|----------|----------------|
| RSS Feeds | Very Simple | Free | No | None | Varies | ✅ Start Here |
| RSSHub | Simple | Free | No | Varies | Global | ✅ Great Addition |
| Ground.news | Moderate | Free* | No | Polite scraping | Global | ✅ Excellent for Bias Analysis |
| NewsAPI.org | Moderate | Free tier | Yes | 100/day | Global | ⚠️ Future (dev only) |
| NewsData.io | Moderate | Free tier | Yes | 200/day | Global | ⚠️ Future |
| GNews API | Moderate | Free tier | Yes | 100/day | Global | ⚠️ Future |
| Bing News | Complex | Free tier | Yes | 1k/month | Global | ❌ Skip |

*Ground.news: Web scraping with user permission for personal use only (not for resale)

---

## Next Steps

1. **Immediate:** Implement NOAA API + RSS feeds (can be done today)
2. **This Week:** Add Open-Meteo as global weather fallback
3. **This Week:** Implement Ground.news scraper for bias analysis and story aggregation
4. **Future:** Evaluate paid tiers if free options prove insufficient

---

## Additional Resources

### Weather
- NOAA API Documentation: https://www.weather.gov/documentation/services-web-api
- Open-Meteo Documentation: https://open-meteo.com/en/docs
- OpenWeatherMap Documentation: https://openweathermap.org/api

### News
- RSS Feed Validator: https://validator.w3.org/feed/
- Feedparser Documentation: https://feedparser.readthedocs.io/
- RSSHub Documentation: https://docs.rsshub.app/

### Tools
- Python feedparser: `pip install feedparser`
- Python requests: `pip install requests`
- JSON formatter: https://jsonformatter.org/

---

## Personalized Morning Briefing Pipeline

As mentioned in the PDF, a key use case is providing personalized briefings that combine news, weather, and other information in a concise format with support for follow-up questions.

### Briefing Architecture

```python
class MorningBriefingService:
    def __init__(self, weather_client, news_client, calendar_client=None, financial_client=None):
        self.weather = weather_client
        self.news = news_client
        self.calendar = calendar_client
        self.financial = financial_client
        self.user_preferences = {}
    
    def generate_briefing(self, user_id, location):
        """Generate personalized morning briefing"""
        briefing = {
            "timestamp": datetime.now().isoformat(),
            "sections": []
        }
        
        # Weather section
        weather_data = self.weather.get_current_weather(location['lat'], location['lon'])
        weather_summary = self._format_weather(weather_data)
        briefing["sections"].append({
            "type": "weather",
            "content": weather_summary,
            "data": weather_data
        })
        
        # News section
        news_items = self.news.get_top_stories(limit=5)
        news_summary = self._format_news(news_items)
        briefing["sections"].append({
            "type": "news",
            "content": news_summary,
            "data": news_items
        })
        
        # Calendar section (if available)
        if self.calendar:
            events = self.calendar.get_today_events(user_id)
            if events:
                calendar_summary = self._format_calendar(events)
                briefing["sections"].append({
                    "type": "calendar",
                    "content": calendar_summary,
                    "data": events
                })
        
        # Financial section (if available and user interested)
        if self.financial and self._user_wants_financial(user_id):
            market_data = self.financial.get_market_summary()
            financial_summary = self._format_financial(market_data)
            briefing["sections"].append({
                "type": "financial",
                "content": financial_summary,
                "data": market_data
            })
        
        # Generate natural language summary
        briefing["summary"] = self._generate_summary(briefing["sections"])
        
        return briefing
    
    def _format_weather(self, weather_data):
        """Format weather data into natural language"""
        temp = weather_data.get('main', {}).get('temp', 'unknown')
        conditions = weather_data.get('weather', [{}])[0].get('description', 'unknown')
        
        return f"Today's forecast is {temp}°F and {conditions}."
    
    def _format_news(self, news_items):
        """Format news items into natural language"""
        if not news_items:
            return "No major news updates today."
        
        headlines = [item['title'] for item in news_items[:3]]
        summary = "In the news: " + "; ".join(headlines[:2])
        
        if len(headlines) > 2:
            summary += f", and {len(news_items) - 2} other stories."
        
        return summary
    
    def _format_calendar(self, events):
        """Format calendar events into natural language"""
        if not events:
            return "You have no events scheduled today."
        
        count = len(events)
        if count == 1:
            return f"You have 1 event today: {events[0]['title']} at {events[0]['time']}."
        else:
            return f"You have {count} events today, starting with {events[0]['title']} at {events[0]['time']}."
    
    def _format_financial(self, market_data):
        """Format financial data into natural language"""
        if not market_data:
            return ""
        
        summary_parts = []
        if 'sp500' in market_data:
            change = market_data['sp500']['change_percent']
            direction = "up" if change > 0 else "down"
            summary_parts.append(f"The S&P 500 is {direction} {abs(change):.1f}%")
        
        return ". ".join(summary_parts) + "." if summary_parts else ""
    
    def _generate_summary(self, sections):
        """Generate complete natural language summary"""
        parts = [section['content'] for section in sections if section['content']]
        return " ".join(parts)
    
    def _user_wants_financial(self, user_id):
        """Check if user wants financial info in briefing"""
        return self.user_preferences.get(user_id, {}).get('include_financial', False)

# Usage Example
briefing_service = MorningBriefingService(
    weather_client=OpenWeatherMapClient("API_KEY"),
    news_client=RSSNewsClient(),
    calendar_client=CalendarClient(),
    financial_client=FinancialClient()
)

# Generate briefing
briefing = briefing_service.generate_briefing(
    user_id="user123",
    location={"lat": 37.7749, "lon": -122.4194}
)

print(briefing["summary"])
# Output: "Today's forecast is 75°F and sunny. In the news: Stock market hits new high; 
# Local event causing traffic downtown. You have 2 events today, starting with Team 
# meeting at 9:00 AM. The S&P 500 is up 0.8%."
```

### Follow-Up Question Support

The PDF emphasizes supporting follow-up questions like "Tell me more about the local event." This requires maintaining conversation context:

```python
class ConversationalBriefingService(MorningBriefingService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_context = {}
    
    def handle_followup(self, user_id, question, last_briefing):
        """Handle follow-up questions about briefing content"""
        
        # Store context from last briefing
        if user_id not in self.conversation_context:
            self.conversation_context[user_id] = {
                "last_briefing": last_briefing,
                "timestamp": datetime.now()
            }
        
        # Parse question intent
        question_lower = question.lower()
        
        # Weather follow-ups
        if any(word in question_lower for word in ['weather', 'temperature', 'rain', 'forecast']):
            return self._detailed_weather_response(last_briefing)
        
        # News follow-ups
        if any(word in question_lower for word in ['news', 'story', 'article', 'event']):
            return self._detailed_news_response(question, last_briefing)
        
        # Calendar follow-ups
        if any(word in question_lower for word in ['schedule', 'meeting', 'event', 'calendar']):
            return self._detailed_calendar_response(last_briefing)
        
        # Financial follow-ups
        if any(word in question_lower for word in ['stock', 'market', 'price']):
            return self._detailed_financial_response(last_briefing)
        
        return "I'm not sure what you're asking about. Could you be more specific?"
    
    def _detailed_weather_response(self, briefing):
        """Provide detailed weather information"""
        weather_section = next(
            (s for s in briefing['sections'] if s['type'] == 'weather'),
            None
        )
        
        if not weather_section:
            return "I don't have weather information available."
        
        data = weather_section['data']
        temp = data.get('main', {}).get('temp')
        feels_like = data.get('main', {}).get('feels_like')
        humidity = data.get('main', {}).get('humidity')
        wind = data.get('wind', {}).get('speed')
        
        return (f"The temperature is {temp}°F, feels like {feels_like}°F. "
                f"Humidity is {humidity}% with winds at {wind} mph.")
    
    def _detailed_news_response(self, question, briefing):
        """Provide detailed news information"""
        news_section = next(
            (s for s in briefing['sections'] if s['type'] == 'news'),
            None
        )
        
        if not news_section:
            return "I don't have news information available."
        
        # Try to match question to specific story
        news_items = news_section['data']
        
        # Simple keyword matching (could be enhanced with NLP)
        for item in news_items:
            if any(word in item['title'].lower() for word in question.lower().split()):
                return f"{item['title']}: {item.get('description', 'No details available.')}"
        
        # If no match, return all headlines
        headlines = [f"- {item['title']}" for item in news_items]
        return "Here are today's top stories:\n" + "\n".join(headlines)
    
    def _detailed_calendar_response(self, briefing):
        """Provide detailed calendar information"""
        calendar_section = next(
            (s for s in briefing['sections'] if s['type'] == 'calendar'),
            None
        )
        
        if not calendar_section:
            return "You have no events scheduled today."
        
        events = calendar_section['data']
        event_list = [f"- {e['time']}: {e['title']}" for e in events]
        return "Your schedule for today:\n" + "\n".join(event_list)
    
    def _detailed_financial_response(self, briefing):
        """Provide detailed financial information"""
        financial_section = next(
            (s for s in briefing['sections'] if s['type'] == 'financial'),
            None
        )
        
        if not financial_section:
            return "I don't have financial information available."
        
        data = financial_section['data']
        details = []
        
        for symbol, info in data.items():
            price = info.get('price', 'N/A')
            change = info.get('change_percent', 0)
            direction = "up" if change > 0 else "down"
            details.append(f"{symbol}: ${price} ({direction} {abs(change):.2f}%)")
        
        return "Market update:\n" + "\n".join(details)

# Usage with follow-ups
conv_service = ConversationalBriefingService(
    weather_client=OpenWeatherMapClient("API_KEY"),
    news_client=RSSNewsClient()
)

# Initial briefing
briefing = conv_service.generate_briefing("user123", {"lat": 37.7749, "lon": -122.4194})
print(briefing["summary"])

# Follow-up question
response = conv_service.handle_followup("user123", "Tell me more about the weather", briefing)
print(response)
# Output: "The temperature is 75°F, feels like 73°F. Humidity is 65% with winds at 8 mph."
```

### Personalization Features

```python
class PersonalizedBriefingPreferences:
    def __init__(self):
        self.preferences = {}
    
    def set_user_preferences(self, user_id, preferences):
        """Set user preferences for briefings"""
        self.preferences[user_id] = {
            "news_categories": preferences.get("news_categories", ["general"]),
            "news_sources": preferences.get("news_sources", []),
            "include_financial": preferences.get("include_financial", False),
            "financial_symbols": preferences.get("financial_symbols", []),
            "weather_units": preferences.get("weather_units", "imperial"),
            "briefing_time": preferences.get("briefing_time", "08:00"),
            "include_calendar": preferences.get("include_calendar", True)
        }
    
    def get_user_preferences(self, user_id):
        """Get user preferences"""
        return self.preferences.get(user_id, {})

# Example: User wants tech news and stock prices
prefs = PersonalizedBriefingPreferences()
prefs.set_user_preferences("user123", {
    "news_categories": ["technology", "business"],
    "include_financial": True,
    "financial_symbols": ["AAPL", "GOOGL", "MSFT"]
})
```

### Key Features Aligned with PDF

1. **Concise Summary**: Briefing combines multiple data sources into one natural language response
2. **Follow-up Questions**: Conversational context allows drilling into specific topics
3. **Personalization**: User preferences tailor content (news categories, financial interests)
4. **Multi-domain Integration**: Weather + News + Calendar + Financial in one briefing
5. **Natural Language**: Responses formatted as conversational text, not raw data

This implementation directly addresses the PDF's example: *"Today's forecast is 75°F and sunny. In the news: the stock market hit a new high, and a local event is causing traffic downtown."* with support for follow-ups like *"Tell me more about the local event."*

---

*Last Updated: 2025-10-29*
*Research conducted for PASSFEL project*
