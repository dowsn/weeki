from typing import List
from datetime import datetime
from .graph_model import TopicState
import logging

logger = logging.getLogger(__name__)


class ActualityEngine:
  """
    Manages topic actuality scores during conversation.
    Focuses only on in-conversation relevance, separate from retrieval scoring.
    """

  def __init__(self,
               base_boost: float = 0.3,
               base_decay: float = 0.15,
               max_boost: float = 1.0,
               min_actuality: float = 0.1):
    self.base_boost = base_boost
    self.base_decay = base_decay
    self.max_boost = max_boost
    self.min_actuality = min_actuality

  def adjust_scores(self, pool: List[TopicState],
                    focus_topic: TopicState) -> List[TopicState]:
    """
        Updates actuality scores when conversation focus changes.

        Args:
            pool: List of active topics in conversation
            focus_topic: Currently discussed topic

        Returns:
            Updated and sorted topic pool, ordered by actuality
        """
    try:
      # Dynamic decay based on pool size
      decay_rate = self._calculate_dynamic_decay(len(pool))

      # Update focus topic
      for topic in pool:
        if topic.id == focus_topic.id:
          topic.actuality = min(self.max_boost,
                                topic.actuality + self.base_boost)
          topic.focus_count += 1
        else:
          # Decay other topics
          topic.actuality = max(self.min_actuality,
                                topic.actuality * (1 - decay_rate))

      # Sort by actuality and frequency of focus
      return sorted(pool,
                    key=lambda x: (x.actuality, x.focus_count),
                    reverse=True)

    except Exception as e:
      logger.error(f"Error adjusting actuality scores: {str(e)}")
      return pool  # Return unchanged pool on error

  def _calculate_dynamic_decay(self, pool_size: int) -> float:
    """
        Adjusts decay rate based on pool size.
        Larger pools decay faster to maintain focus.
        """
    return min(0.35, self.base_decay + (pool_size * 0.02))

  def apply_boost(self,
                  topic: TopicState,
                  boost_factor: float = 1.0) -> TopicState:
    """
        Apply a one-time boost to a topic's actuality.
        Useful for manual relevance adjustments.
        """
    topic.actuality = min(self.max_boost,
                          topic.actuality + (self.base_boost * boost_factor))
    return topic
