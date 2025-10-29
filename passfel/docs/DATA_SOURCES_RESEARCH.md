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

#### 3. OpenWeatherMap
**Complexity:** Moderate  
**Cost:** Free tier: 1,000 calls/day  
**Coverage:** Global  
**Rate Limits:** 60 calls/minute, 1,000 calls/day (free tier)

**Why Moderate:**
- Requires API key (need to sign up)
- Free tier has limitations
- More complex pricing structure

**Key Features:**
- Current weather
- 5-day/3-hour forecast (free)
- 8-day daily forecast (paid)
- Weather alerts
- Historical data (paid)
- Weather maps

**Documentation:** https://openweathermap.org/api

**Recommendation:** Consider if you need features not available in NOAA/Open-Meteo.

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
| NewsAPI.org | Moderate | Free tier | Yes | 100/day | Global | ⚠️ Future (dev only) |
| NewsData.io | Moderate | Free tier | Yes | 200/day | Global | ⚠️ Future |
| GNews API | Moderate | Free tier | Yes | 100/day | Global | ⚠️ Future |
| Bing News | Complex | Free tier | Yes | 1k/month | Global | ❌ Skip |

---

## Next Steps

1. **Immediate:** Implement NOAA API + RSS feeds (can be done today)
2. **This Week:** Add Open-Meteo as global weather fallback
3. **Future:** Evaluate paid tiers if free options prove insufficient

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

*Last Updated: 2025-10-29*
*Research conducted for PASSFEL project*
