from typing import List, Dict, Any
from .graph_model import ConversationState, SessionType, TopicState, UserProfileState


class TopicShiftDetector(TopicShiftDetector):
  def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.cooldown_counter = 0
      self.last_topic_change = None

  def should_check_shift(self, state: ConversationState) -> bool:
      """Enhanced detection with cooldown and engagement awareness"""
      # Cooldown period check
      if self.cooldown_counter > 0:
          self.cooldown_counter -= 1
          return False

      # Existing content checks
      if not super().should_check_shift(state):
          return False

      # Semantic shift detection
      recent_content = self.extract_user_messages(state.conversation_context)
      if len(state.accumulated_content) > 0:
          similarity = self.calculate_similarity(
              state.accumulated_content, 
              recent_content
          )
          if similarity > 0.7:
              return False

      self.cooldown_counter = 3  # Skip next 3 checks
      return True

  def calculate_similarity(self, text1: str, text2: str) -> float:
      """Calculate semantic similarity between text segments"""
      # Implementation using embeddings
      emb1 = self.model.embed_query(text1)
      emb2 = self.model.embed_query(text2)
      return cosine_similarity([emb1], [emb2])[0][0]