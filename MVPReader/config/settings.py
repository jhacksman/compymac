"""
Configuration settings for MVPReader
Manages API credentials, user interests, and system preferences
"""

import os
import json
from typing import List, Dict, Any
from pathlib import Path


class Settings:
    """Manages configuration settings for the feed aggregator"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize settings from config file or environment variables
        
        Args:
            config_path: Path to JSON config file (optional)
        """
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), 'config.json'
        )
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "api_credentials": {
                "slack": {
                    "token": os.getenv("SLACK_BOT_TOKEN", ""),
                    "workspace": "CtrlH"
                },
                "mastodon": {
                    "access_token": os.getenv("MASTODON_ACCESS_TOKEN", ""),
                    "instance_url": os.getenv("MASTODON_INSTANCE_URL", "https://mastodon.social")
                },
                "bluesky": {
                    "username": os.getenv("BLUESKY_USERNAME", ""),
                    "password": os.getenv("BLUESKY_PASSWORD", "")
                },
                "venice": {
                    "api_key": os.getenv("VENICE_API_KEY", ""),
                    "base_url": os.getenv("VENICE_BASE_URL", "https://api.venice.ai")
                }
            },
            "user_interests": {
                "keywords": ["AI", "coding", "machine learning", "python", "LLM"],
                "topics": ["AI research", "software development", "technology"],
                "priority_channels": [],
                "ignore_keywords": ["sports", "weather"]
            },
            "feed_settings": {
                "retention_hours": 48,
                "max_events_per_source": 100,
                "polling_interval_minutes": 5
            },
            "ai_settings": {
                "model": "qwen3-next-80b",
                "max_tokens": 1000,
                "temperature": 0.7
            }
        }
    
    def save_config(self):
        """Save current configuration to file"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    @property
    def slack_token(self) -> str:
        return self.config["api_credentials"]["slack"]["token"]
    
    @property
    def mastodon_token(self) -> str:
        return self.config["api_credentials"]["mastodon"]["access_token"]
    
    @property
    def mastodon_instance(self) -> str:
        return self.config["api_credentials"]["mastodon"]["instance_url"]
    
    @property
    def bluesky_username(self) -> str:
        return self.config["api_credentials"]["bluesky"]["username"]
    
    @property
    def bluesky_password(self) -> str:
        return self.config["api_credentials"]["bluesky"]["password"]
    
    @property
    def venice_api_key(self) -> str:
        return self.config["api_credentials"]["venice"]["api_key"]
    
    @property
    def venice_base_url(self) -> str:
        return self.config["api_credentials"]["venice"]["base_url"]
    
    @property
    def user_keywords(self) -> List[str]:
        return self.config["user_interests"]["keywords"]
    
    @property
    def user_topics(self) -> List[str]:
        return self.config["user_interests"]["topics"]
    
    @property
    def ignore_keywords(self) -> List[str]:
        return self.config["user_interests"]["ignore_keywords"]
    
    @property
    def retention_hours(self) -> int:
        return self.config["feed_settings"]["retention_hours"]
    
    @property
    def max_events_per_source(self) -> int:
        return self.config["feed_settings"]["max_events_per_source"]
    
    @property
    def ai_model(self) -> str:
        return self.config["ai_settings"]["model"]
