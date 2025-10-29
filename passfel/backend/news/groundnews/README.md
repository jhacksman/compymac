# Ground.news Scraper

Web scraper for Ground.news that extracts news stories with political bias analysis and source diversity metrics.

**Permission:** User has permission for personal use only (not for resale).

## Features

- Scrape homepage for top stories
- Extract detailed story information including:
  - Political bias distribution (Left/Center/Right percentages and counts)
  - Source diversity metrics
  - Individual article listings with source names and bias labels
  - Topic tags
- Polite scraping with delays (2-3 seconds between requests)
- Headless Chrome automation via Selenium (current implementation)
- **Recommended**: Migrate to Playwright for better performance and reliability

## Installation

### Current Implementation (Selenium)

Requires:
- Python 3.8+
- Selenium
- BeautifulSoup4
- Chrome/Chromium browser
- ChromeDriver

```bash
pip install selenium beautifulsoup4
```

### Recommended: Playwright (Future Migration)

**Note:** User has explicitly granted permission to use Playwright for Ground.news scraping (personal use only, not for resale).

Playwright offers several advantages over Selenium:
- Better JavaScript rendering support (important for Ground.news Next.js app)
- More reliable element waiting and interaction
- Built-in browser management (no separate ChromeDriver needed)
- Better performance and stability
- Easier debugging with screenshots and traces

```bash
pip install playwright beautifulsoup4
playwright install chromium
```

**Migration Priority:** High - Playwright will significantly improve bias distribution extraction from Ground.news's JavaScript-heavy Next.js application.

## Usage

### Scrape Homepage

Get top 5 stories from the homepage:

```bash
python -m passfel.backend.news.groundnews.cli --mode home --limit 5
```

Output to file:

```bash
python -m passfel.backend.news.groundnews.cli --mode home --limit 10 --out homepage.json
```

### Scrape Story Detail

Get detailed information for a specific story:

```bash
python -m passfel.backend.news.groundnews.cli --mode story --url "https://ground.news/article/..." --out story.json
```

## Output Format

### Homepage Mode

```json
{
  "mode": "homepage",
  "story_count": 5,
  "stories": [
    {
      "story_id": "f2bf3034-bd03-4e59-adb6-1770ed4f7e0e",
      "title": "States sue Trump administration...",
      "url": "https://ground.news/article/...",
      "source_count": null,
      "bias_hint": null
    }
  ]
}
```

### Story Detail Mode

```json
{
  "mode": "story_detail",
  "story": {
    "story_id": "f2bf3034-bd03-4e59-adb6-1770ed4f7e0e",
    "title": "States sue Trump administration to keep SNAP benefits...",
    "summary": "A coalition of 25 states and DC sued to block...",
    "url": "https://ground.news/article/...",
    "published": null,
    "updated": null,
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
      }
    ],
    "topics": ["SNAP", "Donald Trump", "Government Shutdown"]
  }
}
```

## Implementation Details

### Current Implementation (Selenium)
- **Headless Chrome**: Uses Selenium with headless Chrome for automation
- **Anti-detection**: Configured with realistic User-Agent and window size
- **Polite delays**: 2-3 second random delays between requests
- **Overlay handling**: Automatically dismisses subscription modals
- **Robust parsing**: Uses BeautifulSoup for HTML parsing with fallbacks
- **Error handling**: Graceful degradation when elements are missing

### Recommended Migration to Playwright

**Why Playwright is Preferred:**

As mentioned in the PDF and confirmed by user permission, Playwright should be used for Ground.news scraping. Key advantages:

1. **Better JavaScript Rendering**: Ground.news uses Next.js with heavy client-side rendering. Playwright handles this more reliably than Selenium.

2. **Improved Bias Distribution Extraction**: The current Selenium implementation returns zeros for bias distribution because the data is embedded in Next.js JSON. Playwright's better JavaScript support will enable proper extraction.

3. **No Driver Management**: Playwright includes browser binaries, eliminating ChromeDriver version mismatches.

4. **Better Debugging**: Built-in screenshot, video recording, and trace viewer for troubleshooting.

5. **More Reliable**: Better handling of dynamic content, overlays, and async operations.

**Example Playwright Implementation:**

```python
from playwright.async_api import async_playwright
import asyncio

async def scrape_groundnews_story(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        # Navigate to story
        await page.goto(url, wait_until='networkidle')
        
        # Wait for content to load
        await page.wait_for_selector('article', timeout=10000)
        
        # Dismiss overlays
        try:
            close_button = await page.query_selector('[aria-label="Close"]')
            if close_button:
                await close_button.click()
                await asyncio.sleep(1)
        except:
            pass
        
        # Extract data from Next.js JSON
        # Next.js embeds data in <script id="__NEXT_DATA__">
        next_data = await page.evaluate('''() => {
            const script = document.getElementById('__NEXT_DATA__');
            return script ? JSON.parse(script.textContent) : null;
        }''')
        
        if next_data:
            # Extract bias distribution from Next.js data
            story_data = next_data.get('props', {}).get('pageProps', {}).get('story', {})
            bias_dist = story_data.get('bias_distribution', {})
            print(f"Bias distribution: {bias_dist}")
        
        # Get page content for BeautifulSoup parsing
        content = await page.content()
        
        await browser.close()
        
        return content, next_data

# Usage
asyncio.run(scrape_groundnews_story('https://ground.news/article/...'))
```

**Migration Recommendation:** Migrate to Playwright in next iteration to resolve bias distribution extraction issues and improve overall reliability.

## Current Limitations (v0.1.0)

This is a proof-of-concept implementation with the following known limitations:

- **Bias distribution extraction**: Currently returns zeros. Ground.news uses heavy JavaScript rendering with Next.js, and the bias counts are embedded in client-side JSON that requires more sophisticated extraction.
- **Article listings**: Limited extraction due to complex DOM structure. Currently extracts minimal article data.
- **Total sources count**: Not reliably extracted from the "X Articles" header.

**What works well:**
- Homepage story link extraction
- Story title and summary extraction
- Basic scraper infrastructure with polite delays and anti-detection

**Future improvements needed:**
- Parse Next.js embedded JSON data for bias distribution
- Improve article listing extraction with better selectors
- Add retry logic for failed extractions
- Implement caching to reduce requests

## Data Available

### Without Login (Free)
- Story titles, summaries, and URLs
- Political bias distribution (Left/Center/Right percentages and counts)
- Total source count
- Individual article listings with source names, bias labels, headlines, timestamps, locations
- Topic tags

### Requires Premium/Vantage Subscription
- Factuality ratings for sources
- Ownership data for news organizations
- Podcast mentions and timestamps
- Full historical data access

## Robots.txt Compliance

Checked: https://ground.news/robots.txt
- Most paths allowed except `/mediaopoly`
- Respectful scraping is permitted

## Use Cases

- Identify media bias in news coverage
- Detect "blindspot" stories (covered by only one side)
- Track source diversity across political spectrum
- Aggregate multiple perspectives on same story
- Analyze geographic distribution of news sources
