"""Feed fetchers for different platforms"""

from .base import BaseFetcher
from .slack_fetcher import SlackFetcher
from .mastodon_fetcher import MastodonFetcher
from .bluesky_fetcher import BlueskyFetcher

__all__ = [
    'BaseFetcher',
    'SlackFetcher',
    'MastodonFetcher',
    'BlueskyFetcher'
]
