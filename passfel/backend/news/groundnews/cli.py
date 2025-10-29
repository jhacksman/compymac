"""
Command-line interface for Ground.news scraper.

Usage:
    python -m passfel.backend.news.groundnews.cli --mode home --limit 5
    python -m passfel.backend.news.groundnews.cli --mode story --url https://ground.news/article/... --out story.json
"""

import argparse
import json
import sys
from typing import Optional

from .scraper import scrape_homepage, scrape_story_detail
from .models import story_to_dict


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Ground.news scraper for PASSFEL project"
    )
    
    parser.add_argument(
        "--mode",
        choices=["home", "story"],
        required=True,
        help="Scraping mode: 'home' for homepage stories, 'story' for story detail"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of stories to scrape from homepage (default: 5)"
    )
    
    parser.add_argument(
        "--url",
        type=str,
        help="Story URL for 'story' mode"
    )
    
    parser.add_argument(
        "--out",
        type=str,
        help="Output JSON file path (default: stdout)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "story" and not args.url:
        parser.error("--url is required for 'story' mode")
    
    try:
        if args.mode == "home":
            result = scrape_homepage_cli(args.limit)
        else:
            result = scrape_story_cli(args.url)
        
        if result:
            output_json(result, args.out)
            return 0
        else:
            print("Error: Scraping failed", file=sys.stderr)
            return 1
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def scrape_homepage_cli(limit: int) -> Optional[dict]:
    """
    Scrape homepage and return JSON-serializable result.
    
    Args:
        limit: Maximum number of stories to scrape
    
    Returns:
        Dictionary with homepage stories
    """
    print(f"Scraping Ground.news homepage (limit: {limit})...", file=sys.stderr)
    
    stories = scrape_homepage(max_stories=limit)
    
    if not stories:
        print("Warning: No stories found", file=sys.stderr)
        return None
    
    print(f"Found {len(stories)} stories", file=sys.stderr)
    
    return {
        "mode": "homepage",
        "story_count": len(stories),
        "stories": [
            {
                "story_id": story.story_id,
                "title": story.title,
                "url": story.url,
                "source_count": story.source_count,
                "bias_hint": story.bias_hint,
            }
            for story in stories
        ]
    }


def scrape_story_cli(url: str) -> Optional[dict]:
    """
    Scrape story detail and return JSON-serializable result.
    
    Args:
        url: Story URL
    
    Returns:
        Dictionary with story detail
    """
    print(f"Scraping story: {url}...", file=sys.stderr)
    
    story = scrape_story_detail(url)
    
    if not story:
        print("Error: Could not scrape story", file=sys.stderr)
        return None
    
    print(f"Successfully scraped story: {story.title}", file=sys.stderr)
    print(f"  Total sources: {story.total_sources}", file=sys.stderr)
    print(f"  Bias distribution: L{story.bias_distribution.left} C{story.bias_distribution.center} R{story.bias_distribution.right}", file=sys.stderr)
    print(f"  Articles extracted: {len(story.articles)}", file=sys.stderr)
    
    return {
        "mode": "story_detail",
        "story": story_to_dict(story)
    }


def output_json(data: dict, output_path: Optional[str] = None):
    """
    Output JSON data to file or stdout.
    
    Args:
        data: Dictionary to serialize
        output_path: Output file path (None for stdout)
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_str)
        print(f"Output written to: {output_path}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    sys.exit(main())
