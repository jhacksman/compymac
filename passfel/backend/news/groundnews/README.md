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
- Headless Chrome automation via Selenium

## Installation

Requires:
- Python 3.8+
- Selenium
- BeautifulSoup4
- Chrome/Chromium browser
- ChromeDriver

```bash
pip install selenium beautifulsoup4
```

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

- **Headless Chrome**: Uses Selenium with headless Chrome for automation
- **Anti-detection**: Configured with realistic User-Agent and window size
- **Polite delays**: 2-3 second random delays between requests
- **Overlay handling**: Automatically dismisses subscription modals
- **Robust parsing**: Uses BeautifulSoup for HTML parsing with fallbacks
- **Error handling**: Graceful degradation when elements are missing

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
