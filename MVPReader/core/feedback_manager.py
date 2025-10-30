"""
Feedback Manager
Handles user feedback on AI suggestions
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from ..core.models import Feedback


class FeedbackManager:
    """
    Manages user feedback on suggestions
    Logs feedback for future analysis and improvement
    """
    
    def __init__(self, feedback_file: str = None):
        """
        Initialize feedback manager
        
        Args:
            feedback_file: Path to feedback log file
        """
        if feedback_file is None:
            feedback_dir = Path.home() / ".mvpreader"
            feedback_dir.mkdir(parents=True, exist_ok=True)
            feedback_file = feedback_dir / "feedback.jsonl"
        
        self.feedback_file = str(feedback_file)
    
    def record_feedback(
        self, 
        suggestion_id: str, 
        vote: int, 
        comment: str = None
    ) -> Feedback:
        """
        Record user feedback on a suggestion
        
        Args:
            suggestion_id: ID of the suggestion
            vote: 1 for upvote, -1 for downvote
            comment: Optional comment
            
        Returns:
            Feedback object
        """
        feedback = Feedback(
            suggestion_id=suggestion_id,
            vote=vote,
            timestamp=datetime.now(),
            comment=comment
        )
        
        with open(self.feedback_file, 'a') as f:
            f.write(json.dumps(feedback.to_dict()) + '\n')
        
        return feedback
    
    def get_all_feedback(self) -> List[Feedback]:
        """Get all recorded feedback"""
        feedback_list = []
        
        try:
            with open(self.feedback_file, 'r') as f:
                for line in f:
                    data = json.loads(line.strip())
                    feedback = Feedback(
                        suggestion_id=data['suggestion_id'],
                        vote=data['vote'],
                        timestamp=datetime.fromisoformat(data['timestamp']),
                        comment=data.get('comment')
                    )
                    feedback_list.append(feedback)
        except FileNotFoundError:
            pass
        
        return feedback_list
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get statistics on feedback"""
        all_feedback = self.get_all_feedback()
        
        if not all_feedback:
            return {
                'total': 0,
                'upvotes': 0,
                'downvotes': 0,
                'ratio': 0.0
            }
        
        upvotes = sum(1 for f in all_feedback if f.vote > 0)
        downvotes = sum(1 for f in all_feedback if f.vote < 0)
        
        return {
            'total': len(all_feedback),
            'upvotes': upvotes,
            'downvotes': downvotes,
            'ratio': upvotes / len(all_feedback) if all_feedback else 0.0
        }
