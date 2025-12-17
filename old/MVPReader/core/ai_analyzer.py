"""
AI Analyzer
Uses LLM to analyze feed events and generate summaries and suggestions
"""

import asyncio
from typing import List, Dict, Any
from datetime import datetime

from ..core.models import FeedEvent, AISummary
from ..config.settings import Settings
from .venice_llm_client import VeniceLLMClient


class AIAnalyzer:
    """
    Analyzes feed events using LLM
    Generates summaries and actionable suggestions
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize AI analyzer
        
        Args:
            settings: Settings object with API credentials
        """
        self.settings = settings
        self.llm_client = VeniceLLMClient(
            api_key=settings.venice_api_key,
            base_url=settings.venice_base_url,
            model=settings.ai_model
        )
    
    def analyze_events(self, events: List[FeedEvent]) -> AISummary:
        """
        Analyze events and generate summary with suggestions
        
        Args:
            events: List of FeedEvents to analyze
            
        Returns:
            AISummary object with highlights and suggestions
        """
        if not events:
            return AISummary(
                timestamp=datetime.now(),
                highlights=[],
                suggestions=[],
                event_count=0,
                sources_analyzed=[]
            )
        
        prompt = self._build_prompt(events)
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            content = loop.run_until_complete(
                self.llm_client.chat(
                    messages=[
                        {
                            "role": "system",
                            "content": self._get_system_prompt()
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )
            )
            
            loop.close()
            highlights, suggestions = self._parse_response(content)
            
            sources = list(set(e.source.value for e in events))
            
            return AISummary(
                timestamp=datetime.now(),
                highlights=highlights,
                suggestions=suggestions,
                event_count=len(events),
                sources_analyzed=sources
            )
            
        except Exception as e:
            print(f"Error analyzing events with AI: {e}")
            return AISummary(
                timestamp=datetime.now(),
                highlights=[f"Error analyzing events: {str(e)}"],
                suggestions=[],
                event_count=len(events),
                sources_analyzed=[]
            )
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for the LLM"""
        keywords = ", ".join(self.settings.user_keywords)
        topics = ", ".join(self.settings.user_topics)
        
        return f"""You are an AI assistant that monitors communication feeds and alerts the user to important information.

The user is mainly interested in: {keywords}
Topics of interest: {topics}

Your task is to:
1. Identify the most important and relevant events from the feed
2. Summarize key highlights in a concise, actionable format
3. Suggest appropriate actions or responses where applicable

Focus on items that require the user's attention or align with their interests. Ignore noise and irrelevant chatter.

Format your response as:
HIGHLIGHTS:
- [Highlight 1]
- [Highlight 2]
...

SUGGESTIONS:
- [Suggestion 1]
- [Suggestion 2]
..."""
    
    def _build_prompt(self, events: List[FeedEvent]) -> str:
        """Build prompt from events"""
        prompt_parts = ["Here are the recent events from your feeds:\n"]
        
        by_source = {}
        for event in events:
            source = event.source.value
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(event)
        
        for source, source_events in by_source.items():
            prompt_parts.append(f"\n=== {source.upper()} ===")
            
            for event in source_events[:20]:  # Limit to 20 per source
                timestamp = event.timestamp.strftime("%I:%M%p")
                channel_info = f" in #{event.channel}" if event.channel else ""
                mention_flag = " [MENTIONS YOU]" if event.mentions_user else ""
                
                prompt_parts.append(
                    f"[{timestamp}] @{event.author}{channel_info}{mention_flag}: {event.content[:200]}"
                )
        
        prompt_parts.append("\n\nPlease analyze the above and provide highlights and suggestions.")
        
        return "\n".join(prompt_parts)
    
    def _parse_response(self, content: str) -> tuple:
        """
        Parse LLM response into highlights and suggestions
        
        Returns:
            Tuple of (highlights, suggestions)
        """
        highlights = []
        suggestions = []
        
        lines = content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            if 'HIGHLIGHTS:' in line.upper():
                current_section = 'highlights'
                continue
            elif 'SUGGESTIONS:' in line.upper():
                current_section = 'suggestions'
                continue
            
            if line.startswith('-') or line.startswith('•'):
                item = line[1:].strip()
                
                if current_section == 'highlights':
                    highlights.append(item)
                elif current_section == 'suggestions':
                    suggestions.append({
                        'id': f"sug_{len(suggestions)}",
                        'text': item
                    })
        
        return highlights, suggestions
