"""
Data models for Ground.news scraper.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class BiasDistribution:
    """Political bias distribution for a story."""
    left: int
    center: int
    right: int
    left_percent: Optional[int] = None
    center_percent: Optional[int] = None
    right_percent: Optional[int] = None


@dataclass
class Article:
    """Individual article from a news source."""
    source: str
    bias: str  # "Left", "Lean Left", "Center", "Lean Right", "Right"
    headline: str
    url: str
    published: Optional[str] = None
    location: Optional[str] = None


@dataclass
class StoryDetail:
    """Detailed information about a news story."""
    story_id: str
    title: str
    summary: str
    url: str
    total_sources: int
    bias_distribution: BiasDistribution
    published: Optional[str] = None
    updated: Optional[str] = None
    articles: List[Article] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)


@dataclass
class StorySummary:
    """Summary information for a story from the homepage."""
    story_id: str
    title: str
    url: str
    source_count: Optional[int] = None
    bias_hint: Optional[str] = None  # Quick bias text from card if available


def story_to_dict(story: StoryDetail) -> dict:
    """Convert StoryDetail to dictionary for JSON serialization."""
    return {
        "story_id": story.story_id,
        "title": story.title,
        "summary": story.summary,
        "url": story.url,
        "published": story.published,
        "updated": story.updated,
        "total_sources": story.total_sources,
        "bias_distribution": {
            "left": story.bias_distribution.left,
            "center": story.bias_distribution.center,
            "right": story.bias_distribution.right,
            "left_percent": story.bias_distribution.left_percent,
            "center_percent": story.bias_distribution.center_percent,
            "right_percent": story.bias_distribution.right_percent,
        },
        "articles": [
            {
                "source": article.source,
                "bias": article.bias,
                "headline": article.headline,
                "url": article.url,
                "published": article.published,
                "location": article.location,
            }
            for article in story.articles
        ],
        "topics": story.topics,
    }
