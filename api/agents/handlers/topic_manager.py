from api.agents.models.conversation_models import ConversationState, TopicState
from typing import List
import numpy as np
from api.agents.handlers.pinecone_manager import PineconeManager


class TopicManager:

  def __init__(self, pinecone_manager: PineconeManager):
    self.char_threshold = 500
    self.message_char_threshold = 100
    self.similarity_threshold = 0.7
    self.confidence_threshold = 0.5
    self.pinecone_manager = pinecone_manager

  # where is this called
  async def check_topics(self, state: ConversationState) -> ConversationState:
    # Early return if thresholds not met
    if not (state.chars_since_check < self.char_threshold
            and len(state.current_message) < self.message_char_threshold):
      return state

    # Check cached topics

    if state.embedding is not None:
      matched_topics = self._compare_cached_topics(state.cached_topics,
                                                   state.embedding)
    else:
      # Handle the None case
      matched_topics = []

    # Query Pinecone if needed
    if len(matched_topics) == 0 and state.embedding:
      new_topics = await self.pinecone_manager.retrieve_topics(
          embedding=state.embedding, user_id=state.user_id)
      state.cached_topics.extend(new_topics)
      matched_topics = new_topics

    state.current_topics = matched_topics

    # Filter by confidence
    return state

  def _compare_cached_topics(
      self, cached_topics: List[TopicState],
      context_embedding: List[float]) -> List[TopicState]:
    matched = []

    # goes through all cached topics and compares them to the context embedding and updates confidence and appends if needed
    for topic in cached_topics:

      # maybe different comparing
      # ????
      similarity = self._cosine_similarity(context_embedding, topic.embedding)
      if similarity > self.similarity_threshold:
        topic.confidence = (topic.confidence * 0.7) + (similarity * 0.3)
        matched.append(topic)
      else:
        topic.confidence *= 0.9  # Decay confidence
    return matched

  def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
